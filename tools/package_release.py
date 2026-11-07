"""Package source selected by Git ignore rules, excluding local runtime artifacts."""
import hashlib
import json
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
    ).decode("utf-8").split("\0")
    selected = []
    for name in sorted(set(filter(None, files))):
        path = ROOT / name
        if not path.is_file():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError("Release files must be regular files inside the project")
        parts = Path(name).parts
        if any(part in {"data", ".git", ".venv", "node_modules", "__pycache__", "dist"} for part in parts):
            raise ValueError(f"Runtime artifact unexpectedly selected: {name}")
        if path.name.startswith(".env") and path.name != ".env.example":
            raise ValueError("Private environment configuration cannot enter the release")
        if name.startswith("tools/bin/"):
            raise ValueError("Local tool binaries cannot enter the source release")
        selected.append((name, path))
    if not selected:
        raise ValueError("No source files selected; run from an initialized Git checkout")
    output = ROOT / "data" / "releases"
    output.mkdir(parents=True, exist_ok=True)
    archive = output / "KYRO-source.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name, path in selected:
            bundle.write(path, "KYRO/" + name.replace("\\", "/"))
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "archive": archive.name,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "size_bytes": archive.stat().st_size,
        "files": len(selected),
        "excluded": ["private configuration", "runtime data", "local models and tools", "installed dependencies", "generated builds"],
    }
    (output / "release.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
