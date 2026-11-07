# Automatic recovery

KYRO retries temporary failures in imports, indexing, scans and vulnerability enrichment. It resumes interrupted read operations after the backend restarts. Recovery is enabled by default, uses the existing persistent job queue and never substitutes fabricated findings or successful test results.

The default limit is three total attempts, with delays of two and four seconds. Provider Retry-After values can increase the delay, capped at 60 seconds. The original job execution deadline still applies. Configuration: `KYRO_AUTOMATIC_RECOVERY`, `KYRO_JOB_MAX_ATTEMPTS` (1–5), and `KYRO_JOB_RETRY_DELAY` (1–60 seconds).

Attempt numbers, scheduled times and failure history persist in `Job.payload.automatic_recovery`. Events and audit records explain each recovery. Scheduled jobs remain PENDING; completed work becomes SUCCEEDED only after its handler and quality gates pass. Exhausted recovery remains FAILED. Missing coverage and evidence remain INCONCLUSIVE. Cancellation prevents another attempt. Delayed retries do not block other ready jobs.

| Failure | Handling |
|---|---|
| Connection/read/write timeout or temporary transport failure | Bounded retry for eligible read operations |
| GitHub 408/429/5xx or explicit primary rate limit | Bounded retry; honor a numeric Retry-After within the configured ceiling |
| Backend restart while downloading/indexing | Resume an already downloaded, commit-pinned snapshot; retry retrieval only if no snapshot exists |
| Partially extracted archive without a completed commit | Preserve it and report that a new snapshot is required; never overwrite unknown partial evidence |
| Interrupted baseline scan | Preserve previous scanner records, mark unfinished runs FAILED, then run a new scan attempt |
| Scanner execution/availability timeout | Retry through the job policy; retain original execution evidence |
| No supported dependency manifests | Report NOT_APPLICABLE and unavailable dependency coverage; never invent packages or a clean security result |
| Semgrep parsing/analysis errors | Preserve PARTIAL coverage and affected-file diagnostics; repeating a deterministic parser limitation is not a repair |
| GitHub authentication/permission denial, empty repository or malformed input | Report the actual problem; no automated permission escalation or source fabrication |
| Failed tests, quality gates, agent edits, verification or GitHub delivery | Preserve review/approval controls; never automatically replay consequential actions |

Repository content, model output and scanner messages cannot request recovery actions. Only trusted exception types and adapter-produced failure classifications drive the policy. Error strings and recovery history pass through secret redaction. No LLM rewrites KYRO, changes credentials, increases sandbox permissions, merges a PR or deploys code as part of recovery.

Two real edge cases were found during the authorized repository audit: Tree-sitter 0.26.0 corrupted memory above line 256, and Trivy validly omitted its optional Results field when no supported package files existed. KYRO pins Tree-sitter 0.25.2, uses tuple line-number access, and validates Trivy's report envelope before accepting an omitted Results field. An empty/malformed JSON object is still rejected. Scanner raw evidence remains stored.

This mechanism covers known recoverable failures. It cannot guarantee repair of arbitrary product bugs, third-party parser limitations, unavailable credentials, missing source code or failing repository tests. User-facing output and the final verification outcome reflect the evidence actually obtained.

Tests: `backend/app/tests/test_automatic_recovery.py`, `test_repository_recovery.py`, `test_contracts.py`, and `frontend/src/pages/Activity.test.tsx`. Live deployment recovery evidence is recorded separately from controlled unit fixtures.
