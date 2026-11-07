# Research and component decisions

Primary repository READMEs and metadata were retrieved on 2026-11-07 before integrations were implemented. The 21 source URLs, repository push times, archived flags and GitHub-reported licenses are retained in `research/sources.json`. None was archived at retrieval. Recent activity is evidence of activity, not a security endorsement. API/CLI documentation, including failed URLs, is recorded in `research/primary-docs.json`.

Downloaded upstream documentation and website assets remain ignored local research snapshots. The source publication includes KYRO's decisions and URL/license metadata; `tools/research.py` and `tools/primary_docs.py` can retrieve the primary documentation again. Those downloaded assets are not KYRO runtime code or re-licensed as KYRO source.

| Reference | Documented pattern studied | KYRO decision |
|---|---|---|
| OpenHands vulnerability-fixer, OpenHands, Software Agent SDK | Repository workspaces, task execution, verification and GitHub delivery | Implement one bounded state machine; no embedded OpenHands service or SDK dependency |
| Aider, SWE-agent, mini-SWE-agent | Relevant context, structured editing, iterative tool feedback and bounded execution | Hash-bound approved replacements, test feedback and checkpoints; no arbitrary model shell tool |
| DefectDojo, Dependency-Track, Faraday | Finding ingestion, deduplication, evidence, advisory/component management | Preserve raw scanner provenance and normalized findings; no embedded competing platform |
| Semgrep, OSV-Scanner, Trivy | Structured CLI results, tool exit semantics and advisory coverage | Separate pinned Docker adapters; accurate partial/failure records; sequential scanning |
| Syft, Grype, Gitleaks | SBOM, dependency and secret scanning | Optional adapters planned; no claimed implementation |
| ZAP, Nuclei | Dynamic security testing | No dynamic scanner integration; explicit target authorization required for future work |
| Tree-sitter | Language parsers and AST queries | Python AST plus Tree-sitter JavaScript/TypeScript; conservative symbols/references |
| Docker/Moby, gVisor | Execution isolation and resource boundaries | Docker first, no credentials/socket in repository execution; gVisor remains untested |
| LangGraph | Stateful graph orchestration and checkpoints | Not added: one DB-backed worker/state machine meets current needs |

Snyk's official Open Source documentation describes dependency vulnerability identification and remediation workflows. GitHub's official Advanced Security documentation describes code scanning, dependency/security and secret protection capabilities. Semgrep documents rule-driven analysis and structured findings; DefectDojo documents finding aggregation; OpenHands and Aider document repository engineering agents. These informed provenance, investigation, approval and review flows. KYRO has not performed comparative product benchmarks or established competitor weaknesses. The UI direction comes from the user's workspace requirements and is implemented independently; no competitor layout/brand was copied.

KYRO-owned code is MIT licensed. Research-only references are not runtime dependencies: OpenHands/SWE-agent/mini-SWE-agent/Tree-sitter/LangGraph are reported MIT, Aider/Dependency-Track/Moby/gVisor/OSV/Trivy/Syft/Grype/ZAP Apache-2.0, DefectDojo BSD-3-Clause, Faraday GPL-3.0, Gitleaks/Nuclei MIT. Semgrep's repository reports LGPL-2.1. These metadata summaries do not replace each upstream distribution's actual notices and terms.

Scanner images are separately downloaded upstream executables, not source copied into KYRO's modules. Keep upstream licenses/notices with any redistributed scanner binaries/images, especially LGPL components; KYRO's MIT license does not relicense those components. Docker Desktop has its own usage terms. Local Qwen model weights have their own model license and are not distributed by KYRO. The official llama.cpp binary includes bundled runtime notices; it is optional and ignored from source control.

Python dependencies are pinned by `backend/uv.lock` and exported in `backend/requirements.txt`; Node dependencies are locked in `frontend/package-lock.json`. Transitive package terms remain applicable. Inter and JetBrains Mono fonts are locally bundled with SIL Open Font License notices under `frontend/public/licenses/`. React/Vite/TanStack/Lucide/FastAPI/SQLAlchemy packages remain their own upstream works. No full scanner or competing product was recreated to claim coverage.

The API reference bundles Swagger UI Dist 5.31.0 with its Apache-2.0 LICENSE/NOTICE under `backend/static/api-docs/`. Its npm distribution SHA-512 integrity was verified; metadata is in `docs/evidence/api-docs-assets.json`. Assets and initialization are served locally so the strict CSP remains in place and no external schema validation is performed.
