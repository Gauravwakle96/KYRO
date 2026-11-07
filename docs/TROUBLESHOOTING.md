# Troubleshooting

**Docker unavailable:** start Docker Desktop's Linux engine and check `docker version`. CLI installation alone is insufficient. Do not execute repository scripts on the host as a fallback.

**Scanner unavailable:** run scanner setup for the exact configured image. Inspect Security → scan execution metadata for version, exit status and stderr. Semgrep uses a writable temporary directory and disabled network metrics/version check. Trivy unpacks its advisory database in its dedicated disk-backed cache; a tiny tmpfs cannot hold it.

**Partial/failed scan:** successful scanner results remain, but coverage is incomplete. Check advisory service reachability, memory/disk and timeout. Rerun after correcting the actual failure.

**Local model unavailable:** confirm the model server is running and `/v1/models` responds. Use its actual ID and include `/v1` in the endpoint. llama.cpp is not started automatically. A Docker-host endpoint needs the inference server to accept the gateway connection. Local-only rejects external providers.

**Plan/schema/hash failure:** inspect the job error and bounded context. A small model can emit invalid JSON or propose out-of-scope files. Replan after inspection; do not remove boundaries or fabricate a plan. Token limits can require narrower context or a reviewed operator budget change.

**Tests fail because dependencies are missing:** the default trusted image provides Python/pytest/Node/npm, not every framework. Build a project-specific trusted image. Never permit unrestricted host installs or networked repository scripts to bypass isolation.

**Worker interrupted:** eligible read jobs recover automatically after restart within the three-attempt/default execution deadline. Inspect Agent Workspace for the original failure, scheduled delay and recovery history. Agent edits/verification/delivery require checkpoint review and explicit retry. Do not treat a prior patch or incomplete rescan as VERIFIED.

**Import/analysis failed:** Retry import/analysis preserves the failed job and resumes a downloaded commit-pinned snapshot. An incomplete archive without a commit is preserved for review. An empty GitHub repository needs actual commits before import; repeated retries cannot create missing source.

**NOT_APPLICABLE scanner:** OSV/Trivy found no supported dependency inputs. This is unavailable coverage, not a clean result. Semgrep parser limitations remain PARTIAL with actual diagnostics; repeating them is not automatic repair.

**GitHub blocked:** configure a selected-repository App/OAuth/PAT on the backend. Verify permissions and authorized branch. If the base branch moved after verification, re-ingest and re-verify; delivery refuses stale parents. Draft PR creation is not automatic merge approval.

**Frontend 404:** build frontend/dist and check the backend static path. Browser tests verify the actual root route as well as health. **403 mutation:** obtain a valid session CSRF token and use a configured origin. **409 delete:** cancel and wait for active project jobs first.
