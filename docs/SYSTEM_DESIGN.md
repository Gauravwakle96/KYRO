# System design

The browser uses a credentialed HTTP-only session plus per-session CSRF token. State-changing requests validate origin, CSRF, typed input and object ownership. SQLite uses WAL, foreign keys and bounded busy waits. Database migrations run before the one worker starts.

GitHub ingestion pins a commit SHA, downloads a bounded archive and rejects traversal, links and special entries. Source snapshots live at managed `repositories/<UUID>`. Indexes store hashes and compact AST facts. Source content is retrieved only for owned files and selected model context.

Long operations enqueue database jobs. One worker executes scanners sequentially and persists actual events. SSE uses event IDs including the latest timestamp, heartbeat and a finite stream; polling continues when SSE disconnects. Pending/running job duplication is checked. Eligible read jobs retry trusted transient failures and resume after restart within attempt/deadline limits; incomplete evidence stays visible. Interrupted agent/edit/verification/write jobs require review and explicit retry. See [automatic recovery](AUTOMATIC_RECOVERY.md).

Remediation validates structured model output, records a plan and exact source hashes, then awaits approval. Execution copies an immutable source to `workspaces/<task UUID>`, applies bounded replacements and runs approved commands in Docker. Checkpoint JSON preserves each step, diff and logs. Token/step/command/job budgets stop excessive execution.

Verification runs separately from the agent, with its own builds, tests and scanner records. Findings are compared against the target's complete baseline. Reports distinguish verified, partial, failed and inconclusive. PR delivery checks verified hashes and the live GitHub base SHA before publishing a dedicated draft branch.

The monolith separates API, database, repository indexing, scanners, intelligence, integration, agent, jobs and verification modules. Redis, a graph server and multiple model agents are unnecessary for the initial workload. Horizontal job dispatch and team authorization are future work.
