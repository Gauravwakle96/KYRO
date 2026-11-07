# Repository intelligence

Ingestion retrieves GitHub's archive for a validated branch/commit; no git hooks, repository scripts or credentials run during ingestion. Limits: 100 MB compressed, 200 MB extracted, 10,000 files, 10 MB per extracted file. Links/special files and path traversal are rejected; `.git`, `.env`, `.ssh`, `.aws` are omitted.

Indexing caps directory entries at 20,000 and individual text files at 2 MB. Vendor/build/environment directories are skipped. Python AST extracts named functions/classes, imports (including aliases) and call expressions. Tree-sitter extracts JS/TS function/class declarations, imports and call expressions. Parse errors are recorded. Rust/Go/Java/C-family files are identified but do not yet receive AST symbol extraction.

Dependencies come from requirements files, PEP 621 pyproject metadata, npm package/lock manifests and Cargo.lock. Version constraints remain constraints when no installed version is known. Scanner package evidence supplies installed-version information where available. Frameworks and candidate entry points are evidence-based heuristics, not assertions of public exposure.

File hashes support incremental replacement and removal of stale index records. Finding context selects the affected file, relevant dependency imports/manifests and up to four known test files. Whole files exceeding the remaining context budget are omitted rather than misleadingly supplied as complete replacement context. The agent can modify only existing files included in that bounded context and its approved plan.
