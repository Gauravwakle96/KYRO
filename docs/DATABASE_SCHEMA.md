# Database schema

Alembic revision `0001` creates relational tables compatible with SQLite/PostgreSQL.

| Table | Purpose / boundary |
|---|---|
| users | Unique email, Argon2 password hash; closed first-owner bootstrap |
| sessions | SHA-256 opaque token hash, CSRF token, expiry, owner FK |
| credentials | Encrypted GitHub OAuth token, account login; never serialized |
| projects | Owned project metadata |
| repositories | Project FK, branch, immutable commit SHA, source and analysis JSON |
| repository_files | Unique repository/path, content hash, language and AST facts |
| scan_runs | Repository/commit/purpose/status/timestamps |
| scanner_executions | Tool version/exit/stdout/stderr/duration plus original normalized results |
| findings | Repository/fingerprint uniqueness; provenance, risk, reachability, enrichment |
| remediation_tasks | Finding/repository, validated plan, approval hash, checkpoints/evidence/report/PR |
| jobs | Owner, task kind/resource, lifecycle, events, result, cancellation flag |
| model_usage | Owner/task, reported input/output tokens, provider, duration, estimated cost/status |
| audit_logs | Owned action history; retained after project deletion |

Foreign keys cascade project-dependent data. Audit owner identifiers intentionally have no cascading FK. JSON avoids dozens of premature symbol/evidence tables; every source relationship includes a path/line or scanner reference. Credential ciphertext is encrypted by an ignored backend-owned key. Back up the DB, key and source snapshots together. SQLite concurrency is constrained to one process/worker; multi-node dispatch is not implemented.
