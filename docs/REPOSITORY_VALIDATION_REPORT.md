# Repository validation report

Recorded 2026-11-07T15:16:11.899201+00:00 through 2026-11-07T15:22:40.881445+00:00. All 19 accessible repositories were processed sequentially on their default branches by the deployed KYRO backend. Existing projects and snapshots were preserved.

17 repositories indexed; 1,487 files, 3,901 dependency records and 347 normalized scanner findings. 8 runs completed with all three scanners; 9 had incomplete coverage; 2 repositories had no commits to import.

A completed scan means the configured tools finished; it does not certify security. Zero findings does not establish safety. Findings are scanner evidence, not confirmed application-specific exploitability. Semgrep currently uses seven local rules. Dependency input and parser limitations are shown below.

## Sequential results

| # | Repository / branch | Indexed files | Dependencies | Findings | Semgrep | OSV | Trivy | Outcome |
|---|---|---:|---:|---:|---|---|---|---|
| 1 | [KYRO](http://127.0.0.1:8787/repositories/a800161f-c5ef-412f-bd77-b47704d855c1) / main | — | — | — | NOT_RUN | NOT_RUN | NOT_RUN | FAILED |
| 2 | [INHERIA](http://127.0.0.1:8787/repositories/ded99edd-8137-41ec-a503-c8d2ecc81761) / main | 86 | 297 | 0 | PARTIAL | SUCCEEDED | SUCCEEDED | INCONCLUSIVE |
| 3 | [NTUxSTEng_Hackathon](http://127.0.0.1:8787/repositories/478cb46e-f618-4110-af19-a5fe4955350d) / main | 28 | 3 | 0 | SUCCEEDED | SUCCEEDED | NOT_APPLICABLE | INCONCLUSIVE |
| 4 | [Plugin-fraud-behavior-](http://127.0.0.1:8787/repositories/01ede546-289c-44db-830a-6b17bd19947a) / main | 268 | 179 | 27 | SUCCEEDED | SUCCEEDED | SUCCEEDED | SUCCEEDED |
| 5 | [NAGRIVANTA-2](http://127.0.0.1:8787/repositories/66a93031-1dbf-4c0a-a490-8b65e67e1bdd) / main | 17 | 0 | 0 | SUCCEEDED | NOT_APPLICABLE | NOT_APPLICABLE | INCONCLUSIVE |
| 6 | [SOVRIVA](http://127.0.0.1:8787/repositories/03639073-0df9-425f-8d3e-31cd733be599) / main | 90 | 16 | 0 | SUCCEEDED | SUCCEEDED | NOT_APPLICABLE | INCONCLUSIVE |
| 7 | [OPTICORE](http://127.0.0.1:8787/repositories/1985e728-bb43-42e5-af0c-e2c2680c20e2) / main | — | — | — | NOT_RUN | NOT_RUN | NOT_RUN | FAILED |
| 8 | [VARSHIQ](http://127.0.0.1:8787/repositories/0b243bea-93ca-4d94-9970-d12e93a704ed) / master | 159 | 404 | 0 | PARTIAL | SUCCEEDED | SUCCEEDED | INCONCLUSIVE |
| 9 | [graphear](http://127.0.0.1:8787/repositories/062ef93b-fa34-497f-a1c4-113e57cc884a) / main | 77 | 362 | 1 | SUCCEEDED | SUCCEEDED | SUCCEEDED | SUCCEEDED |
| 10 | [Anime-Web-Demo](http://127.0.0.1:8787/repositories/cd5bf5d7-bace-48b8-b6d5-8e54a4298656) / master | 81 | 525 | 23 | SUCCEEDED | SUCCEEDED | SUCCEEDED | SUCCEEDED |
| 11 | [SPENDSMART](http://127.0.0.1:8787/repositories/fce06663-47bd-48a6-b428-a473ff81da11) / main | 64 | 1006 | 14 | SUCCEEDED | SUCCEEDED | SUCCEEDED | SUCCEEDED |
| 12 | [Ai-WasteTwinn](http://127.0.0.1:8787/repositories/02dad475-d301-4e04-bf77-2b7772ace7a5) / main | 18 | 0 | 0 | PARTIAL | NOT_APPLICABLE | NOT_APPLICABLE | INCONCLUSIVE |
| 13 | [NAGRIVANTA](http://127.0.0.1:8787/repositories/cd96be49-d75e-444f-81be-fe2b13ef08e2) / main | 133 | 669 | 35 | SUCCEEDED | SUCCEEDED | SUCCEEDED | SUCCEEDED |
| 14 | [Twin_ai](http://127.0.0.1:8787/repositories/12f86170-a1a8-4659-af74-0d1962907bc3) / master | 56 | 342 | 21 | SUCCEEDED | SUCCEEDED | SUCCEEDED | SUCCEEDED |
| 15 | [inkloom](http://127.0.0.1:8787/repositories/db5ab0d8-75d0-4669-b9e9-d8193ad0d07b) / master | 311 | 69 | 55 | PARTIAL | SUCCEEDED | SUCCEEDED | INCONCLUSIVE |
| 16 | [online-basic-calculator](http://127.0.0.1:8787/repositories/9f30556f-5a21-4e17-9a46-dcab29d8e92e) / main | 6 | 2 | 16 | SUCCEEDED | SUCCEEDED | SUCCEEDED | SUCCEEDED |
| 17 | [CommBank-Server](http://127.0.0.1:8787/repositories/7b8093ac-02c0-4773-9b51-ad24d80708d9) / main | 51 | 0 | 1 | SUCCEEDED | SUCCEEDED | NOT_APPLICABLE | INCONCLUSIVE |
| 18 | [Zoro](http://127.0.0.1:8787/repositories/cc7299fb-eb9d-4e22-b3df-077b152a2a88) / main | 41 | 27 | 154 | SUCCEEDED | SUCCEEDED | SUCCEEDED | SUCCEEDED |
| 19 | [desktop-tutorial](http://127.0.0.1:8787/repositories/62471869-3c78-4042-bd9f-750ef7ba13dd) / main | 1 | 0 | 0 | SUCCEEDED | NOT_APPLICABLE | NOT_APPLICABLE | INCONCLUSIVE |

NOT_APPLICABLE means the tool ran but found no supported dependency inputs. PARTIAL denotes parser/analysis errors. Both leave aggregate coverage INCONCLUSIVE. Empty repository imports remain FAILED with the actual GitHub 409 message.

## Coverage and import issues

- **KYRO:** GitHub repository has no commits yet; push source code before importing it (409).
- **INHERIA:** semgrep: Semgrep reported 2 parsing/analysis errors; inspect raw scanner evidence for affected files.
- **NTUxSTEng_Hackathon:** trivy: No supported package files detected; dependency coverage is unavailable.
- **NAGRIVANTA-2:** osv: No supported dependency sources found; dependency coverage is unavailable; trivy: No supported package files detected; dependency coverage is unavailable.
- **SOVRIVA:** trivy: No supported package files detected; dependency coverage is unavailable.
- **OPTICORE:** GitHub repository has no commits yet; push source code before importing it (409).
- **VARSHIQ:** semgrep: Semgrep reported 1 parsing/analysis errors; inspect raw scanner evidence for affected files.
- **Ai-WasteTwinn:** semgrep: Semgrep reported 1 parsing/analysis errors; inspect raw scanner evidence for affected files; osv: No supported dependency sources found; dependency coverage is unavailable; trivy: No supported package files detected; dependency coverage is unavailable.
- **inkloom:** semgrep: Semgrep reported 1 parsing/analysis errors; inspect raw scanner evidence for affected files.
- **CommBank-Server:** trivy: No supported package files detected; dependency coverage is unavailable.
- **desktop-tutorial:** osv: No supported dependency sources found; dependency coverage is unavailable; trivy: No supported package files detected; dependency coverage is unavailable.

## Findings and intelligence checks

| Severity | Scanner findings |
|---|---:|
| CRITICAL | 16 |
| HIGH | 129 |
| MEDIUM | 170 |
| LOW | 28 |
| UNKNOWN | 4 |

347 findings have stored risk factors. Repository symbols, relationships, conservative reachability and bounded context retrieval were checked where findings existed. The raw audit retains commit SHAs, scanner versions, exits, durations, parse diagnostics and graph/context counts.

The highest counts are in Zoro (154) and inkloom (55); prioritize individual findings using severity, usage and reachability evidence rather than count alone. Counts are per repository snapshot; advisory duplicates across different repositories remain separate. Earlier user snapshots and fixtures may make the overall dashboard totals larger.

## Product workflow and recovery

The updated deployment completed a fresh labelled fixture workflow: real local AI plan, fixture approval, Docker patch, build, four tests, independent three-scanner rescan and VERIFIED evidence (22→21 findings; zero new findings). Six independent arithmetic/security regression tests and actual sandbox boundary/timeout probes passed on a disposable copy. Evidence: [recovery workflow](evidence/recovery-workflow/live-verification.json) and [security checks](evidence/recovery-workflow/live-security-checks.json).

Automatic recovery passed an actual abrupt indexing-container restart: the same persistent job completed on attempt 2 and indexed 1,504 fixture files. No manual retry, user repository edit or cloud request was involved. See [recovery evidence](evidence/live-automatic-recovery.json) and [policy](AUTOMATIC_RECOVERY.md).

A real local-model plan for online-basic-calculator is awaiting approval. Its proposed Flask upgrade needs dependency compatibility review; no existing test suite was discovered. The expected test outcome is a recommendation, not an executed result. See [plan evidence](evidence/live-real-repository-plan.json).

This repository audit covers retrieval, indexing, scanning and evidence/data boundaries. It did not run every repository build/test suite, execute real-repository fixes or create a remote PR. Those operations retain their approval and sandbox requirements. Optional cloud inference remains unavailable because the provider rejected the client. No GitHub branch, commit, PR, merge or public deployment was performed.

## Reproduce

Run `python tools/audit_repositories.py --help` for the authorized deployed audit, and `python tools/repository_report.py` to render its recorded final evidence. The audit uses backend-only configured GitHub access and never requests tokens on the command line.

Raw evidence: [final repository audit](evidence/live-repository-audit-final.json). Full feature-by-feature acceptance: [product checklist](PRODUCT_CHECKLIST.md), [implementation status](../IMPLEMENTATION_STATUS.md), [test report](TEST_EXECUTION_REPORT.md).
