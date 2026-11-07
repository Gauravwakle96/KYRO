# Benchmarking framework

Benchmarks use owned controlled fixtures; no dynamic testing targets external systems. Unit fixtures validate contracts only. Live evidence is separately captured through the actual API, binaries, model and Docker.

For an isolated acceptance server, from backend:

```powershell
$env:KYRO_DATA_DIR='../data/acceptance'
$env:KYRO_DATABASE_URL='sqlite:///../data/acceptance/kyro.db'
$env:KYRO_LOCAL_MODEL_URL='http://127.0.0.1:8080/v1'
$env:KYRO_LOCAL_MODEL='qwen3-8b'
$env:KYRO_ALLOWED_ORIGINS='http://127.0.0.1:8788,http://localhost:8788'
uv run uvicorn app.main:app --host 127.0.0.1 --port 8788 --no-access-log
```

Use the operator's actual configured local model; no model install or paid requests are required by the script. From project root: `python tools/live_acceptance.py --phase all`. The script creates an isolated test owner with a random ignored credential, imports an explicitly labelled fixture, runs real scanners, obtains an actual model plan, automatically approves only that controlled fixture, executes and independently verifies. It never publishes a PR. `npm run test:e2e` in frontend tests the actual server after this setup.

P2 metrics: label positive/negative source cases, compute precision/recall/false-positive rate only within that labelled corpus; compare raw and normalized findings for provenance/duplicate preservation; record risk factors and reachability category/evidence. Advisory databases change, so record scanner version, snapshot SHA and retrieval time. Unknown package ground truth must not be included as a claimed accuracy denominator.

P6 metrics: completed tasks, generated patches, actual build/test outcomes, failed retries, step count, wall-clock duration and unauthorized actions rejected. Verification metrics: original rule/advisory disappearance, new findings, report status, independently run regression behavior and evidence completeness. False-verification rate requires a labelled insecure-patch corpus; a single positive run cannot establish it.

Cost metrics: provider-reported input/output tokens, missing-usage records, request duration/count, local wall-clock time, configured cloud estimates, cost per VERIFIED task. No cloud cost or latency is invented when cloud is unused. Hardware figures and container limits accompany any performance claim.

`tools/benchmark.py` derives a report from captured live evidence and labels its denominator. It does not compare competitors. No broad performance superiority, general precision or complete exploitability accuracy is claimed.

After acceptance, run `uv run python ../tools/live_security.py` from backend for independent arithmetic/security regression and actual sandbox probes. Run `python tools/benchmark.py` from the project root to summarize recorded measurements. Both retain separate evidence. The generated patch is not manually altered by the harness.
