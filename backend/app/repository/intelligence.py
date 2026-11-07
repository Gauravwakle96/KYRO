import ast
import json
import re
import tomllib
from collections import Counter
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from sqlalchemy import select
from sqlalchemy.orm import Session
from tree_sitter import Language, Parser

from app.core.security import digest, safe_path
from app.database import FileRecord, Repository

LANGUAGES = {".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".rs": "Rust", ".go": "Go", ".java": "Java", ".c": "C", ".cpp": "C++", ".cs": "C#", ".rb": "Ruby"}
SKIP = {".git", "node_modules", ".venv", "venv", "vendor", "dist", "build", "__pycache__", ".pytest_cache"}


def python_facts(text: str) -> dict:
    facts: dict = {"symbols": [], "imports": [], "calls": [], "errors": []}
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                facts["symbols"].append({"name": node.name, "kind": "class" if isinstance(node, ast.ClassDef) else "function", "line": node.lineno, "end_line": node.end_lineno})
            elif isinstance(node, ast.Import):
                facts["imports"].extend({"name": alias.name, "alias": alias.asname or alias.name, "line": node.lineno} for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                facts["imports"].extend({"name": f"{node.module or ''}.{alias.name}", "alias": alias.asname or alias.name, "line": node.lineno} for alias in node.names)
            elif isinstance(node, ast.Call):
                facts["calls"].append({"name": ast.unparse(node.func), "line": node.lineno})
    except (SyntaxError, RecursionError, ValueError) as error:
        facts["errors"].append(type(error).__name__)
    return facts


def tree_facts(text: str, extension: str) -> dict:
    import tree_sitter_javascript
    import tree_sitter_python
    import tree_sitter_typescript

    grammar = tree_sitter_python.language() if extension == ".py" else tree_sitter_typescript.language_tsx() if extension == ".tsx" else tree_sitter_typescript.language_typescript() if extension == ".ts" else tree_sitter_javascript.language()
    parser = Parser(Language(grammar))
    source = text.encode()
    tree = parser.parse(source)
    root = tree.root_node
    facts: dict = {"symbols": [], "imports": [], "calls": [], "errors": ["AST contains parse errors"] if root.has_error else [], "parser": "tree-sitter"}
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type in {"function_declaration", "method_definition", "class_declaration", "function_definition", "class_definition"}:
            name = node.child_by_field_name("name")
            if name:
                # Tuple access also avoids the defective Point getters in tree-sitter 0.26.0.
                facts["symbols"].append({"name": source[name.start_byte:name.end_byte].decode(), "kind": "class" if "class" in node.type else "function", "line": node.start_point[0] + 1, "end_line": node.end_point[0] + 1})
        if node.type == "import_statement":
            child = node.child_by_field_name("source")
            if child:
                facts["imports"].append({"name": source[child.start_byte:child.end_byte].decode().strip("\"'"), "line": node.start_point[0] + 1})
        if node.type == "call_expression":
            child = node.child_by_field_name("function")
            if child:
                call_name = source[child.start_byte:child.end_byte].decode()
                facts["calls"].append({"name": call_name, "line": node.start_point[0] + 1})
                if call_name == "require" or call_name == "import":
                    args = node.child_by_field_name("arguments")
                    if args:
                        match = re.search(r"[\"']([^\"']+)[\"']", source[args.start_byte:args.end_byte].decode())
                        if match:
                            facts["imports"].append({"name": match[1], "line": node.start_point[0] + 1})
        stack.extend(reversed(node.children))
    return facts


def dependencies(path: str, text: str) -> list[dict]:
    name = Path(path).name
    result = []
    if name.startswith("requirements") and name.endswith(".txt"):
        for line in text.splitlines():
            try:
                req = Requirement(line.split(" #")[0].strip())
                pinned = [s.version for s in req.specifier if s.operator == "==" and "*" not in s.version]
                result.append({"name": req.name, "version": pinned[0] if pinned else None, "constraint": str(req.specifier), "ecosystem": "PyPI", "manifest": path, "direct": True})
            except InvalidRequirement:
                continue
    elif name == "pyproject.toml":
        try:
            doc = tomllib.loads(text)
            for spec in doc.get("project", {}).get("dependencies", []):
                result.extend(dependencies("requirements.txt", spec))
            for dep in result:
                dep["manifest"] = path
        except (tomllib.TOMLDecodeError, InvalidRequirement):
            pass
    elif name in {"package.json", "package-lock.json"}:
        try:
            doc = json.loads(text)
            if name == "package.json":
                for group in ["dependencies", "devDependencies"]:
                    for package, version in doc.get(group, {}).items():
                        result.append({"name": package, "version": version if re.fullmatch(r"\d+\.\d+\.\d+(?:-[\w.]+)?", version) else None, "constraint": version, "ecosystem": "npm", "manifest": path, "direct": True, "development": group == "devDependencies"})
            else:
                for key, data in doc.get("packages", {}).items():
                    if "node_modules/" in key:
                        result.append({"name": data.get("name") or key.rsplit("node_modules/", 1)[-1], "version": data.get("version"), "ecosystem": "npm", "manifest": path, "direct": False, "development": data.get("dev", False)})
        except (ValueError, TypeError):
            pass
    elif name == "Cargo.lock":
        try:
            for package in tomllib.loads(text).get("package", []):
                result.append({"name": package["name"], "version": package["version"], "ecosystem": "crates.io", "manifest": path, "direct": False})
        except (KeyError, tomllib.TOMLDecodeError):
            pass
    return result


def index_repository(db: Session, repo: Repository, root: Path, progress=lambda _: None) -> dict:
    existing = {record.path: record for record in db.scalars(select(FileRecord).where(FileRecord.repository_id == repo.id))}
    counts: Counter = Counter()
    deps: list[dict] = []
    files: list[dict] = []
    frameworks: set[str] = set()
    entry_points: list[str] = []
    tests: list[str] = []
    errors: list[dict] = []
    seen = set()
    paths = sorted(root.rglob("*"))
    if len(paths) > 20000:
        raise ValueError("Repository exceeds the 20,000 entry index limit")
    for path in paths:
        rel = path.relative_to(root).as_posix()
        if any(p in SKIP or p == ".env" or p.startswith(".env.") for p in path.relative_to(root).parts):
            continue
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = safe_path(root, rel, allow_new=False).read_text(encoding="utf-8")
        except (UnicodeDecodeError, ValueError):
            continue
        seen.add(rel)
        language = LANGUAGES.get(path.suffix, "Configuration")
        if language != "Configuration":
            counts[language] += 1
        hash_value = digest(text)
        record = existing.get(rel)
        if record is None or record.digest != hash_value:
            progress(f"Indexing {rel}")
            facts = python_facts(text) if path.suffix == ".py" else tree_facts(text, path.suffix) if path.suffix in {".js", ".jsx", ".ts", ".tsx"} else {"symbols": [], "imports": [], "calls": [], "errors": []}
            if record is None:
                record = FileRecord(repository_id=repo.id, path=rel, digest=hash_value, language=language, facts=facts)
                db.add(record)
            else:
                record.digest, record.language, record.facts = hash_value, language, facts
        files.append({"path": rel, "language": language, "hash": hash_value, "symbols": len(record.facts["symbols"]), "size": path.stat().st_size})
        errors.extend({"file": rel, "error": e} for e in record.facts.get("errors", []))
        deps.extend(dependencies(rel, text))
        for framework, pattern in {"FastAPI": r"\bfastapi\b", "Django": r"\bdjango\b", "Flask": r"\bflask\b", "React": r"[\"']react[\"']", "Next.js": r"[\"']next[\"']", "Express": r"[\"']express[\"']"}.items():
            if re.search(pattern, text):
                frameworks.add(framework)
        if path.name in {"main.py", "app.py", "server.py", "manage.py", "index.ts", "main.tsx", "index.js", "server.js"}:
            entry_points.append(rel)
        if any(p in {"test", "tests", "__tests__"} for p in path.parts) or path.name.startswith("test_") or ".test." in path.name:
            tests.append(rel)
    for key, record in existing.items():
        if key not in seen:
            db.delete(record)
    analysis = {"files": files, "languages": dict(counts), "frameworks": sorted(frameworks), "dependencies": deps, "entry_points": entry_points, "tests": tests, "errors": errors, "limitations": ["Static references do not establish runtime exploitability.", "Dynamic imports, reflection and dependency injection may be missed.", "Python, JavaScript and TypeScript have symbol analysis; other languages have manifest and file analysis."]}
    repo.analysis, repo.status = analysis, "READY"
    db.commit()
    progress(f"Indexed {len(files)} files and {len(deps)} dependency records")
    return analysis


def relevant_context(db: Session, repo: Repository, root: Path, finding: dict, max_chars=24000) -> list[dict]:
    preferred = [finding.get("file_path"), *repo.analysis.get("tests", [])[:4], *[d["manifest"] for d in repo.analysis.get("dependencies", []) if d["name"] == finding.get("package_name")]]
    package = finding.get("package_name", "")
    if package:
        for record in db.scalars(select(FileRecord).where(FileRecord.repository_id == repo.id)):
            if any(package.replace("-", "_") in imp["name"] for imp in record.facts.get("imports", [])):
                preferred.append(record.path)
    context = []
    for relative in dict.fromkeys(p for p in preferred if p):
        try:
            path = safe_path(root, relative, allow_new=False)
            text = path.read_text(encoding="utf-8")
        except (ValueError, UnicodeDecodeError, OSError):
            continue
        if len(text) > max_chars:
            continue
        context.append({"path": relative, "hash": digest(text), "content": text})
        max_chars -= len(text)
    return context
