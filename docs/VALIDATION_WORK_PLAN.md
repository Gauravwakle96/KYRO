# Repository validation and automatic recovery

User-authorized scope: inspect and scan all accessible user repositories sequentially on their default branches. Preserve existing projects, snapshots, credentials and failed evidence. Repository scripts run only in the approved sandbox. Remote code changes, draft pull requests, merges and deployment retain their approval controls.

| Work | State | Evidence / next action |
|---|---|---|
| Diagnose interrupted INHERIA imports | VERIFIED | Docker recorded exit 139 twice; isolated threaded indexing reproduced it; upstream Tree-sitter issue #505 identifies defective Point getters |
| Fix large-file native parser crash | VERIFIED | Stable 0.25.2 pin, tuple line-number access; three isolated real-source runs indexed 86 files and 297 dependencies |
| Manual import retry with preserved history | TESTED | Authenticated API recovery tests, duplicate prevention, path boundaries and non-replay of agent actions; first deployed INHERIA retry succeeded |
| Repository-by-repository scan/intelligence audit | VERIFIED | All 19 processed sequentially; 17 indexed, 8 complete scans, 9 INCONCLUSIVE and 2 empty; 347 findings; final audit JSON and readable repository report |
| Bounded automatic recovery | VERIFIED | Actual read-job restart recovery plus transient-error tests; three attempts, original deadline and preserved failure history; no agent/write replay |
| Recovery fault-injection and regression tests | VERIFIED | Actual abrupt indexing restart completed same job on attempt 2; 1,504 files; cancellation/exhaustion/permanent-error/approval boundaries pass |
| Browser/API/security/deployment verification | TESTED | 132 backend, 9 frontend and 14 deployed browser checks; latest fixture model/patch/build/four tests/three rescans VERIFIED 22→21; six security regression tests and sandbox probes passed |
| Real repository model plan/enrichment | VERIFIED for read-only planning/enrichment | Local calculator plan awaits approval; no tests discovered and compatibility review needed; actual OSV/NVD/EPSS/KEV enrichment returned four sources without errors |
| Evidence/checklist/documentation | IMPLEMENTED | Per-repository report and explicit feature acceptance states; actual GitHub PR remains unrun |
| Source package | TESTED | Rebuilt archive passed ZIP integrity/required-file checks and exact private-value/runtime exclusion checks; `data/releases/KYRO-source.zip` and runtime release-validation.json |

Current checks: 132 backend tests, nine frontend unit tests and 14 deployed browser tests pass. Ruff/mypy, frontend lint/types/build and both dependency audits pass. Fresh live workflow evidence is under `docs/evidence/recovery-workflow/`. Full GitHub-to-PR acceptance awaits an approved verified real-repository fix and remote-write authorization, not missing repository access. Optional cloud inference remains blocked by provider client policy.
