# Product architecture

KYRO implements understand → detect → investigate → prioritize → plan → approve → remediate → test → independently verify → deliver.

React/TypeScript/Vite browser client talks to a FastAPI modular monolith. SQLAlchemy/Alembic persist users, hashed sessions, owned projects, immutable repository snapshots, indexes, scanner executions, findings, jobs, remediation evidence, model usage and audit events. SQLite is the local default; PostgreSQL uses the same schema through psycopg.

One database-backed worker executes jobs sequentially to suit the 16 GB workstation. Scanner adapters invoke real tools in restricted containers in production. No untrusted repository script runs on the host. Scanner failures remain failures and produce partial or failed scan states.

Repository snapshots use GitHub's authenticated archive API, commit SHA pinning, bounded extraction and no symlinks. Pull requests use GitHub Git database APIs; approval is separate from execution approval. No repository hooks or credentialed git subprocess is required.

A bounded agent requests structured plans and exact file replacements through an OpenAI-compatible local endpoint. Approval binds the plan, repository SHA, file hashes and command arrays. Every execution uses a disposable workspace. Verification is deterministic code outside the agent, with independent scans and conservative outcomes. The agent never supplies its own certification.

Risk scores are KYRO priorities with explicit factors, separate from CVSS. References and potential paths are recorded without claiming runtime exploitability. Core source indexing uses Tree-sitter and Python AST; dynamic language limitations remain visible.

Consequential stack choices: plain CSS design tokens avoid unnecessary UI framework dependencies; TanStack Query handles live API state; relational graph storage avoids a graph server; an explicit persisted state machine avoids a second orchestration framework. Optional scanners and external intelligence are adapters, not nested deployments of competing platforms.

This is an implementation design. Actual acceptance status and evidence are maintained in IMPLEMENTATION_STATUS.md.
