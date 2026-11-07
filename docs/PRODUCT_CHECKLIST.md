# Whole-product checklist

Updated 2026-11-07. IMPLEMENTED means code exists; TESTED means the named checks passed; VERIFIED means actual evidence supports the specific integration/workflow, not a security certification. BLOCKED denotes missing external acceptance. A controlled fixture does not establish live GitHub completion.

## P0 mandatory product

| Item | State | Evidence / remaining work |
|---|---|---|
| React/TypeScript frontend and all core navigation screens | TESTED | Actual API screens, states, mobile layouts; 9 unit and 14 deployed browser tests |
| FastAPI backend, validation, errors and health | TESTED | 132 backend tests; Ruff/mypy; live HTTP operation |
| Persistent DB and migrations | TESTED | SQLite live persistence; PostgreSQL 18.3 constraints/migrations; full PostgreSQL application workflow unrun |
| Authentication, sessions, CSRF and ownership | TESTED | Closed first-owner signup, Argon2, hashed sessions, origin/object permission tests |
| Actual GitHub connection | VERIFIED | Live authentication HTTP 200; deployed KYRO adapter listed 19 repositories; no credential values included in evidence |
| GitHub repository/default-branch retrieval | VERIFIED | PAT-backed immutable snapshots: 17 real repositories; two empty repositories correctly fail; App/OAuth live checks unrun |
| Repository ingestion and analysis | VERIFIED | 1,487 real files and 3,901 dependency records; incremental indexing and patched large-file parser checks |
| Semgrep integration | VERIFIED | Actual 1.184.0 executions; local seven-rule initial configuration |
| OSV-Scanner integration | VERIFIED | Actual 2.7.0 executions and advisory results |
| Trivy integration | VERIFIED | Actual 0.76.2 executions and advisory results |
| Finding normalization and deduplication | TESTED | 46 scanner records normalize to 22 findings; evidence/provenance retained |
| Contextual risk explanations | TESTED | Deterministic factors with evidence; CVSS separate; no unsupported exploit proof |
| Local inference integration | VERIFIED | Actual Ollama qwen2.5-coder:7b and llama.cpp/Qwen3 planning/editing |
| Remediation planning/review/approval | VERIFIED | Schema-validated model plan and hash-bound approved files/commands |
| Controlled agent execution | VERIFIED | Actual state/checkpoint/tool history; bounded retries and rejected failures |
| Docker sandbox | VERIFIED | Actual non-root, networkless, credential/mount/resource/timeout probes |
| Actual code modification | VERIFIED | Approved file hashes/replacements applied inside isolated Docker workspace |
| Actual build and tests | VERIFIED | Fresh updated deployment: build/four original arithmetic tests plus six independent security regression tests |
| Independent rescans and before/after verification | VERIFIED | Fresh updated deployment: all three scanners rerun; selected eval finding removed, 22→21, zero new findings |
| Actual GitHub draft PR creation/status | BLOCKED | Real API implementation and tests exist; no live branch/commit/PR write authorized |
| Docker local deployment | VERIFIED | Initially clean isolated volume and final rebuilt image passed; normal app owner setup remains available |

## Core workflow and support modules

| Module | State | Implemented scope / limit |
|---|---|---|
| Projects/settings/deletion | TESTED | Persistent CRUD, backend ownership, active-job deletion conflict and explicit UI confirmation |
| Vulnerability enrichment | VERIFIED | Real calculator CVE-2026-27205: four actual sources, timestamps and no provider errors; cached/error handling tested |
| Reachability | TESTED | Imports/references and conservative categories; no static proof of runtime safety |
| Attack-path explorer | IMPLEMENTED | Relational evidence graph and interactive browser graph; advanced dataflow graph is future work |
| Context selection | TESTED | Bounded finding/file/dependency/test context with secret/path exclusions |
| Patch quality | TESTED | Scope/hashes/diff, builds/tests, original finding identity and new findings checked; semantics require human review |
| Independent verification | VERIFIED | Separate runner with VERIFIED/PARTIALLY_VERIFIED/FAILED/INCONCLUSIVE outcomes and retained failed cases |
| Local/cloud model router | TESTED | Chat/Responses contracts, local-only boundaries, authorization, task selection and budgets; live cloud BLOCKED by provider 401 |
| Actual usage and cost accounting | TESTED | Provider tokens/duration stored; missing cloud tokens/prices remain unknown; local compute cost unmeasured |
| Background jobs/SSE/cancellation | TESTED | Persistent recovery events/status, duplicate-job constraint, cancellation; SSE retention and browser recovery history checked |
| Automatic read-job recovery | VERIFIED | Real abrupt container restart; same indexing job completed attempt 2; 1,504 files; three-attempt ceiling, deadline, cancellation and permanent-error tests |
| Manual recovery controls | TESTED | Ownership/CSRF/state/path-safe retry; retained original history; consequential operations use approval flow |
| Agent recovery | TESTED | Bounded validation/test retry, unchanged proposals rejected, checkpoints preserved; agent/write jobs never automatically replay after crash |
| Sequential user repository audit | VERIFIED | All 19 processed: 8 complete scans, 9 INCONCLUSIVE, 2 empty; 347 findings; [per-repository report](REPOSITORY_VALIDATION_REPORT.md) |
| GitHub Actions integration | IMPLEMENTED | CI/dependency/security workflow source; hosted Actions execution not observed |
| Threat model/data isolation | TESTED | STRIDE, trust boundaries and meaningful permission/path/sandbox/source-secret checks; Docker daemon remains critical boundary |
| Deployment/documentation/evidence | TESTED | Dockerfiles/Compose, env template, lockfiles, migrations, setup scripts, required docs and execution reports |
| Reproducible benchmark harness | TESTED | Recorded selected task, scanner/dedup outcomes, rejected insecure cases and actual tokens; no general reliability/comparison claim |

## P1 differentiators

| Capability | State | Limit |
|---|---|---|
| Tree-sitter intelligence | TESTED | JS/TS plus Python AST; other languages have file/manifest indexing |
| Advanced reachability | IN_PROGRESS | Reference-level foundation implemented; interprocedural/dataflow proof unavailable |
| Enrichment, local-only, cost routing, job updates | TESTED | Live enrichment/local boundaries; cloud service rejects this client |
| Recovery/quality/evidence graph | VERIFIED for read recovery; controls TESTED; graph IMPLEMENTED | Actual restart recovery; bounded retries/quality gates; graph interaction not exhaustively tested |

## P2 future expansion

| Capability | State |
|---|---|
| Advanced dataflow/full call graphs and attack paths | NOT_STARTED |
| Additional language/scanner adapters | NOT_STARTED |
| Multi-agent orchestration | NOT_STARTED; intentionally one controlled product agent |
| Advanced CI automation/team collaboration/enterprise permissions | NOT_STARTED |
| gVisor/stronger isolation and automated retention | NOT_STARTED; isolation limits documented |

Full GitHub-to-PR acceptance remains BLOCKED by an approved verified real-repository fix and explicit draft PR delivery approval. Real retrieval/scanning are now verified. The recorded validation performed no remote remediation edit, PR, merge or public deployment; publishing KYRO's own source is a separate operator action. The calculator's real local-model plan awaits review: tests are absent and Flask/Werkzeug compatibility must be checked. Optional cloud acceptance remains BLOCKED by the provider's client rejection; local AI is working. Automatic recovery handles known transient failures; it cannot guarantee repair of every product error.
