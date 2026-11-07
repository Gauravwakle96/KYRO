# Test execution report

Executed on 2026-11-07 on Windows 11 with Docker Desktop Linux containers and a 6 GB RTX 3050. Source, unit fixtures, browser response fixtures and actual integration evidence are distinguished below. Full GitHub-to-PR acceptance remains BLOCKED; this report does not certify public or multi-tenant deployment.

## Automated checks

| Check | Actual result | Evidence / command |
|---|---|---|
| Backend unit/integration/security tests | 132 passed, zero skipped/failures/errors | `evidence/automatic-recovery-backend-tests.xml`; `uv run pytest --junitxml=../docs/evidence/automatic-recovery-backend-tests.xml` |
| Previous backend line coverage | 69.87% (1,853 / 2,652 statements) on earlier code; below the 80% target; not recomputed for recovery changes | `backend-coverage.json`; no current coverage figure claimed |
| Python lint and types | Ruff and mypy passed | `uv run ruff check app migrations`; `uv run mypy app` |
| Frontend unit tests | 9 passed | `evidence/automatic-recovery-frontend-tests.json`; `npm run test` |
| Frontend lint/types/production build | Passed | `npm run lint`; `npm run typecheck`; `npm run build` |
| Deployed browser critical flows | 14 passed, no skipped/flaky/unexpected outcomes; includes retained real recovery history and policy controls | `evidence/browser-test-results.json`; `npm run test:e2e` against isolated 8789 |
| Browser accessibility/responsiveness | No axe violations in tested views at 390x844, 768x1024 and 1440x900; no document overflow; mobile Escape focus recovery and reduced-motion checks passed | `evidence/browser/axe-*.json`; `evidence/ui-evidence.json` |
| Node dependency audit | Zero reported vulnerabilities | `evidence/npm-audit.json` |
| Python locked runtime dependency audit | Zero reported vulnerabilities | `python-audit.json` |
| Source secret scan | Latest Gitleaks 8.30.1 scan passed on 315 Git-selected source files; exact configured private values had zero matches | `evidence/release-hygiene.json`; private configuration/runtime data excluded; older `source-secrets.json` retained |
| PostgreSQL migrations/constraints | Actual PostgreSQL 18.3 migration, FK, unique active-job index and transaction checks passed | `evidence/postgres-acceptance.json`; full PostgreSQL app acceptance was not run |
| Swagger assets | Self-hosted assets load under CSP; package SHA-512 verified and license/notice bundled; OSV query returned no advisories | `evidence/api-docs-assets.json`; `evidence/api-docs-vulnerability-audit.json` |

Mocked external contracts in unit tests establish request/error behavior, not live GitHub access or successful cloud inference. Security audits are observations against current advisory databases, not proof that no vulnerabilities exist.

## Latest repository audit and recovery

All 19 authorized repositories were processed sequentially on their default branches. Seventeen indexed successfully (1,487 files; 3,901 dependency records); KYRO and OPTICORE correctly failed because GitHub returned 409 for repositories without commits. Actual Semgrep, OSV-Scanner and Trivy operations produced 347 normalized findings. Eight runs had complete scanner coverage; nine remained INCONCLUSIVE because of Semgrep parser limitations or missing supported dependency inputs. The audit uses deployed backend jobs, not browser login fixtures. It does not establish every repository's build/test success or remediation.

The INHERIA backend segmentation fault was reproduced in isolated threaded indexing. Docker recorded exit 139, not OOM. The Tree-sitter 0.26.0 Point getter defect is documented upstream in issue #505; pinning 0.25.2 and preserving tree lifetime/tuple access passed three isolated real-source runs (86 files, 297 dependency records). Trivy's valid optional Results field and OSV's no-supported-input exit were normalized without hiding unavailable coverage or accepting malformed reports.

Automatic recovery passed a real abrupt restart during fixture indexing on 8789: the same persistent job resumed and SUCCEEDED on attempt 2; 1,504 files and 600 TSX symbols were indexed. No manual retry, cloud request or user repository modification occurred. Unit tests cover transient success, exhaustion, cancellation, original deadlines, permanent/permission failures, prompt-injection error strings, preserved snapshots, delayed queue fairness and non-replay of agent/write operations.

A real local-model plan for online-basic-calculator reached AWAITING_APPROVAL. No existing test suite was discovered; the proposed Flask upgrade needs Werkzeug compatibility review. No real-repository patch or test success is claimed. Actual enrichment of CVE-2026-27205 returned OSV/NVD/EPSS/KEV sources with retrieval times and no provider errors.

Evidence: [repository report](REPOSITORY_VALIDATION_REPORT.md), `evidence/live-repository-audit-final.json`, `repository-parser-regression.json`, `live-automatic-recovery.json`, `live-real-repository-plan.json` and `live-real-repository-enrichment.json`.

## Fresh workflow on the updated deployment

After the recovery/parser/scanner changes, a fresh labelled fixture on the preserved 8789 acceptance volume completed actual local AI planning, explicit fixture approval, Docker patch application, build/four tests and three independent rescans. Outcome VERIFIED: selected eval finding resolved, 22→21 findings, zero new findings; task SUCCEEDED. Six independent arithmetic/security regression tests passed on a disposable copy. Actual sandbox probes passed non-root execution, no host home/socket/credentials, read-only root, blocked egress, CPU/memory/process limits, managed writable mount and timeout removal. This reuses an existing volume and does not claim another clean-volume installation.

The selected fresh task recorded two actual local requests: 2,466 input tokens, 581 output tokens and 64.126 seconds of inference. No cloud request was used. Local compute/electricity cost was not measured. The generated patch uses deprecated ast.Num; it passed the configured Python runtime, but Python 3.14 compatibility is not established. The plan included an existing test file in its allowed scope; only app.py was actually modified.

Separate current evidence: `evidence/recovery-workflow/live-baseline-scan.json`, `live-remediation-plan.json`, `live-agent-execution.json`, `live-agent-final.json`, `live-verification.json` and `live-security-checks.json`. Historical native/deployment evidence below is retained and describes earlier executions.

## Actual controlled local workflow

The controlled fixture is explicitly labelled and contains vulnerable arithmetic evaluation plus old dependency versions. This is actual binary/model/container execution, not a simulated scanner or agent.

- Baseline: Semgrep 1.184.0 returned 1 finding, OSV-Scanner 2.7.0 returned 40, and Trivy 0.76.2 returned 5. All three succeeded. 46 results normalized to 22 findings with scanner provenance retained.
- Ollama `qwen2.5-coder:7b` generated a structured plan and patch. The approved patch changed only `app.py`, replacing dynamic evaluation with restricted AST arithmetic. Patch application occurred inside Docker, with approved hashes and paths checked.
- The actual build and four original arithmetic tests passed. Independent rescanning again ran all three scanners successfully. The original eval finding resolved, zero new findings were introduced, and counts changed from 22 to 21. Report outcome: VERIFIED.
- Six independently added arithmetic/security regression tests passed in a disposable Docker copy. Non-root execution, read-only root, absent socket/host home/credentials, blocked network egress, memory/process limits, writable managed workspace, timeout removal and Docker patch application probes passed.
- The selected successful native task used 2 actual local model requests, 2,445 input tokens, 612 output tokens and 62.288 seconds of inference. No billable cloud inference succeeded; local electricity/hardware cost was not measured.

Native evidence: `evidence/live-baseline-scan.json`, `live-remediation-plan.json`, `live-agent-execution.json`, `live-agent-final.json`, `live-verification.json`, `live-security-checks.json` and `benchmark-results.json`. The other 21 findings remain unresolved; a fix for one finding does not certify the whole fixture.

Failure evidence is retained. An eval patch whose arithmetic tests passed but unsafe evaluation remained was independently rejected. Another patch removed eval but broke arithmetic tests and was rejected. Invalid/unchanged proposals, bounded retries and failed provider jobs remain recorded. No general success rate or competitor advantage is inferred from these selected cases. The final deployed acceptance is a separate successful execution, not a replay of the native evidence.

## Deployment acceptance

The production image was built from the npm/uv lockfiles and recreated successfully. The normal app is available only on loopback at `http://127.0.0.1:8787`; health, actual frontend, self-hosted API reference and Docker-to-Ollama catalog access passed. The operator's existing account, projects, snapshots and provider settings were preserved; acceptance accounts remain in separate test storage.

An initially clean, separate named volume and loopback port 8789 passed frontend serving, owner authentication, persistent project creation, fixture retrieval/indexing and all three real scanner child containers using volume subpaths. The final image was checked again using the same preserved acceptance volume and a fresh fixture. The deployed instance also completed actual Ollama planning, explicit fixture approval, Docker patch application, build/four tests and all three independent rescans: VERIFIED, 22→21 findings, zero new findings, final agent SUCCEEDED. Evidence is recorded separately under `evidence/deployment/`.

See `evidence/clean-deployment-acceptance.json`, `evidence/deployment-readiness.json` and `evidence/resource-observation.json`. Resource readings are point-in-time observations, not peak benchmarks. Local source/tests use network restrictions; scanners require advisory database access. The backend Docker socket remains a critical host-control boundary and requires a trusted operator/dedicated Docker host.

## Final acceptance stages

| User acceptance stage | Outcome | Exact scope / blocker |
|---|---|---|
| 1. Open KYRO | VERIFIED | Real frontend/API/health and initial owner setup |
| 2. Connect authorized GitHub repository | VERIFIED for PAT | Deployed adapter listed 19 authorized repositories; App/OAuth live checks unrun |
| 3. Retrieve and analyze actual source | VERIFIED | Seventeen real repositories indexed; two empty repositories accurately failed; parser fix tested against real INHERIA source |
| 4. Run Semgrep/OSV/Trivy | VERIFIED | Three actual version-pinned containers, baseline and rescans |
| 5. Store/display findings | TESTED | DB/API and actual browser finding views |
| 6. Investigate finding | TESTED | Real finding provenance, bounded source context, transparent risk/reachability evidence |
| 7. Generate remediation plan | VERIFIED | Actual fixture and real calculator local-model plans; calculator plan needs missing-test/compatibility review |
| 8. Obtain approval | TESTED | Explicit API plan-digest approval; harness auto-approves only labelled fixtures |
| 9. Modify code in isolation | VERIFIED | Real approved patch applied in Docker |
| 10. Execute build/tests | VERIFIED for selected fixture | Fresh updated deployment: four original tests and six independent security regression tests; user repository builds/tests unrun |
| 11. Independent rescan/comparison | VERIFIED | All scanners succeeded; original resolved and zero introduced findings |
| 12. Produce evidence report | VERIFIED | Diff, commands, scanner records, remaining findings and limitations persisted |
| 13. Create actual GitHub PR | BLOCKED | Real branch/commit/draft PR implementation exists; approved verified real-repository fix and remote-write approval still required |
| 14. Clean deployment startup | VERIFIED for local Docker | Initially clean volume startup and final image recheck; no public deployment performed |

Optional cloud acceptance is BLOCKED: the provider returned HTTP 401 `unauthorized_client_error` and rejected the KYRO client. No successful cloud response, token usage or monetary cost is fabricated. Local inference remains functional.

Remaining acceptance action: review and approve a suitable real-repository plan, execute/test/verify in Docker, then explicitly approve its draft PR delivery. Repository retrieval and scanner results now pass the stated scope; effective write permissions and actual PR creation remain untested. The current calculator plan needs compatibility review and has no discovered tests, so it is not a ready verified delivery candidate. No automatic merging or public deployment occurred. Incomplete acceptance must not be replaced with pretend success.

## Product-wide interface refresh

The user-requested redesign covers grouped navigation, overview workflow links and actual metric tiles, projects/repository forms, finding filters/tables, evidence panels, remediation/verification views, the agent timeline, model controls, analytics/settings, and access/onboarding. It uses original KYRO orbital artwork, warm headings, layered navy surfaces and differentiated semantic accents. No new service, paid asset, fake statistic or inactive CTA was added.

After the refresh, frontend lint/types/build and all five unit tests passed. Twelve browser tests passed, including all primary screens, three responsive/axe viewports, access-screen axe checks, password visibility/keyboard flow, logout and actual workflow-link navigation. The first run exposed a stale frontend logout cache: the API session ended but the old workspace stayed visible. The fix clears cached data and reloads the signed-out route; the affected test and the full suite passed afterward. Initial failure evidence remains in `evidence/browser-redesign-first-run.json`.

Screenshots are under `evidence/browser/screens/` and `evidence/browser/auth-*.png`. All evidence is generated using controlled fixture accounts; it contains no personal login credentials. The final deployed UI is rechecked independently from the native source-serving test instance.

Final deployed browser run: **12 passed** against loopback port 8789, including completed screen captures and access/keyboard controls. One earlier deployment run exceeded the harness's five-second post-login assertion; the actual API returned 200 after 7.231 seconds under local memory pressure. The browser wait now allows actual completion within 30 seconds; security/hash settings were not weakened. Timing and first-run failure are preserved in `evidence/deployment-login-timing.json` and `evidence/browser-redesign-deployment-first-run.json`.

The deployed core model/patch/build/rescan workflow was executed before the interface-only refresh. Backend, scanner and sandbox source remained unchanged during that refresh; the final image's frontend artifacts match the tested production build and the complete deployed browser suite passed afterward.

The primary deployment first-owner screen also passed actual axe/overflow checks at all three target widths without creating an account. Evidence: `evidence/first-owner-ui.json` and `evidence/browser/setup-*.png`.
