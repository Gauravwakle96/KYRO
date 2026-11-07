# API documentation

FastAPI's actual OpenAPI schemas are served at `/openapi.json`, interactive docs at `/docs`. All protected routes require `kyro_session` and all protected mutations require `X-CSRF-Token` obtained from login or `/api/auth/me`. Unknown or non-owned objects return 404. Validation failures return 422/400, unauthenticated 401, CSRF/origin 403, conflicts/integration unavailable 409 and queue/rate limits 429.

Auth: GET `/api/auth/setup`, POST `/api/auth/register` (first owner only), POST `/api/auth/login`, GET `/api/auth/me`, POST `/api/auth/logout`.

Projects: GET/POST `/api/projects`, PATCH/DELETE `/api/projects/{id}`. POST body `{name,description}`. Delete explicitly removes snapshots/evidence and refuses active jobs.

GitHub: GET `/api/github/status`, `/repositories`, `/branches?full_name=owner/repo`; POST `/device`, `/device/poll` for backend OAuth; DELETE `/connection`. No token is returned.

Repositories: GET/POST `/api/repositories`; connect body `{project_id,full_name,branch}` returns repository plus a 202 job. POST `/api/repositories/fixture?project_id=...` imports the labelled fixture. GET `/{id}`, `/{id}/files?path=...`, POST `/{id}/analyze`, POST `/{id}/scans`; GET `/api/repository-intelligence/{id}` returns indexed facts.

Security: GET `/api/scanners`, `/api/scans`, `/api/scans/{id}`, `/api/findings`, `/api/findings/{id}`, `/api/dependencies`, `/api/attack-paths/{repository_id}`. Findings support repository_id, severity and search. POST `/api/findings/{id}/enrich` is asynchronous.

Remediation: POST `/api/findings/{id}/remediation` queues a plan. GET `/api/remediation`, `/{id}`; POST `/{id}/approve` requires `{approved:true,plan_digest}`; POST `/{id}/execute`, `/{id}/verify`; GET `/{id}/report`; POST `/{id}/pull-request` requires `{approved:true}`, VERIFIED and a real GitHub repository. POST `/{id}/pull-request/refresh`; GET `/api/pull-requests`.

Models: GET `/api/models` local health, routing, cloud request budget and usage; PUT `/api/models/settings` `{endpoint,model,local_only,routing}` where routing is local/auto/cloud. External local URLs fail validation. Secrets, protocol, pricing and cost authorization remain server configuration.

Jobs: GET `/api/jobs`, `/{id}`, `/{id}/events` (SSE), POST `/{id}/cancel`, POST `/{id}/retry` (202). Retry requires ownership, CSRF, a terminal eligible read job and a valid snapshot; it creates a new job and preserves the original. Completed imports retry as analysis; plan/execute/verify/deliver use their approval flow. Responses include status/events, timestamps/result/error and `payload.automatic_recovery` attempt/history/schedule. Failed quality gates produce FAILED; incomplete outcomes produce INCONCLUSIVE. Scanner PARTIAL and NOT_APPLICABLE remain distinct from complete coverage. `/api/settings` includes the server-managed recovery policy.

Operations: GET `/api/analytics`, `/api/settings`, `/api/audit`, `/api/health`. API requests are capped at 1 MB; source previews at 200 KB. Long work always returns a persisted job ID; acceptance is determined from resulting evidence, never the initial HTTP 202.
