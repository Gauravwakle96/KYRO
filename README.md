# KYRO

**Think. Build. Secure.**

AI-powered autonomous software security and engineering intelligence, built for local execution and human-reviewed changes.

KYRO retrieves authorized source snapshots, indexes code, runs real Semgrep/OSV-Scanner/Trivy containers, explains finding priority, generates a bounded local-model plan, executes approved edits in Docker, independently rescans and prepares an approved draft GitHub pull request.

Its workflow is **Understand → Detect → Investigate → Prioritize → Plan → Approve → Remediate → Test → Verify → Deliver**. Users see the original scanner evidence, the proposed operation, the actual code diff and the verification results. Approval is required before editing a repository workspace and before publishing a draft pull request.

[Quick start](#start-with-docker-recommended) · [User guide](#how-to-use-kyro) · [Capabilities](#what-kyro-can-do) · [Recovery](#automatic-recovery) · [Validation](#what-has-been-tested) · [Documentation](#documentation)

The whole-product [checklist](docs/PRODUCT_CHECKLIST.md), [test execution report](docs/TEST_EXECUTION_REPORT.md) and [implementation status](IMPLEMENTATION_STATUS.md) record actual acceptance and remaining external blockers. This product is not certified secure or ready for public multi-tenant operation.

The latest [repository report](docs/REPOSITORY_VALIDATION_REPORT.md) records all 19 authorized repositories, individual scanner outcomes and 347 normalized findings. [Automatic recovery](docs/AUTOMATIC_RECOVERY.md) retries known transient read failures and resumes interrupted indexing; original errors and incomplete results stay visible. Actual restart recovery and a fresh deployed AI/patch/test/rescan workflow passed; live GitHub draft PR creation remains unrun.

## What KYRO can do

| Capability | User-facing behavior |
|---|---|
| Projects and repository snapshots | Organize repositories by project, select a branch and inspect the exact retrieved commit. |
| Repository intelligence | Discover languages, frameworks, manifests, dependencies, likely entry points, tests and supported code symbols. |
| Real security scanning | Execute Semgrep, OSV-Scanner and Trivy sequentially; preserve each tool's result, exit status and error evidence. |
| Unified findings | Search and filter normalized results while retaining the original scanner provenance. |
| Contextual prioritization | Explain risk factors separately from raw CVSS; show reference/reachability evidence and its limitations. |
| Vulnerability enrichment | Retrieve available OSV, NVD, FIRST EPSS and CISA KEV information with source timestamps and provider errors. |
| Evidence graph | Explore recorded relationships among repositories, files and findings. |
| Local AI remediation | Retrieve bounded relevant code and generate a structured, reviewable plan using a configured local model. |
| Controlled code modification | Apply approved file changes in a Docker workspace with hash, path, command and resource boundaries. |
| Independent verification | Run build/test commands and scanners again, compare findings and retain failed or incomplete outcomes. |
| Evidence reports | Download the original finding, root cause, diff, command results, scanner comparison and limitations. |
| Draft PR delivery | Implemented GitHub branch/commit/draft PR flow, gated on explicit approval and VERIFIED evidence; live product PR acceptance remains pending. |
| Recovery and activity | Retry eligible transient read failures, resume interrupted indexing, cancel jobs and inspect persistent recovery history. |
| Model usage and analytics | Show recorded model tokens, inference duration, scan history and verification outcomes; unavailable costs remain unknown. |

The current release uses a single local owner and one lightweight background worker. General-purpose bug fixing, full interprocedural dataflow analysis and team permissions are future expansion, rather than claims about the current agent.

## Requirements

For Docker startup: Git, Docker Desktop or a compatible Linux Docker engine (26+), Docker Compose 2.24.4+ and at least 10 GB free disk for images, scanner caches and source. Host Python/Node are unnecessary for this deployment; the images install the pinned runtimes. For native development, also install Python 3.12–3.13, uv and Node 24.

A local OpenAI-compatible inference endpoint is required for AI planning and editing. Repository analysis and scanners can operate without a running AI model. Dependency scanning uses public advisory services; offline operation requires suitable pre-populated scanner caches. GitHub access and optional cloud inference require separately configured authorization. The core local workflow requires no paid cloud service.

## Start with Docker (recommended)

In PowerShell on Windows:

```powershell
git clone https://github.com/Gauravwakle96/KYRO.git
cd KYRO
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
./infrastructure/scripts/setup-scanners.ps1
docker compose up -d --build
```

On Linux/macOS, clone the same repository, copy `.env.example` to `.env` if it does not exist, then run:

```bash
docker pull semgrep/semgrep:1.184.0
docker pull ghcr.io/google/osv-scanner:v2.7.0
docker pull aquasec/trivy:0.76.2
docker build -t kyro-sandbox:local -f infrastructure/docker/Sandbox.Dockerfile .
docker compose up -d --build
```

Open **http://127.0.0.1:8787**. On a fresh installation, create the first owner account; there is no preset password. Later, sign in with that account. Check health at **http://127.0.0.1:8787/api/health** and view the generated API reference at **http://127.0.0.1:8787/docs**.

Before using AI remediation, configure an available local model as explained below. To try scanning without GitHub authorization, follow the labelled test-fixture workflow. The first image build and scanner database downloads require internet access and may take time.

## Start locally on Windows

From this directory:

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
# Edit backend settings in .env; never add credentials to source or frontend files.
./infrastructure/scripts/setup-scanners.ps1
./infrastructure/scripts/start-local.ps1
```

Open **http://127.0.0.1:8787** and create the initial owner account. Public registration closes after the first owner. Stop the server with Ctrl+C. The script builds the actual frontend and runs the backend on loopback. Run `npm run dev` in frontend for frontend development; its proxy targets port 8787.

Settings paths are relative to `backend` for native startup: use `KYRO_DATA_DIR=../data` and `KYRO_DATABASE_URL=sqlite:///../data/kyro.db`. `.env` is read from the project root. Use absolute paths for custom deployments.

## Model configuration

Default: `KYRO_LOCAL_ONLY=true`, `KYRO_LOCAL_MODEL_URL=http://127.0.0.1:8080/v1`, model `qwen3-8b`. Configure the actual model identifier in AI Models. llama.cpp's `llama-server` supports `/v1/chat/completions`. An existing Ollama server can use `http://127.0.0.1:11434/v1` with its actual model identifier. KYRO does not download a GGUF or overwrite an existing inference installation.

For an existing Ollama installation with `qwen2.5-coder:7b`, configure the ignored root `.env`:

```dotenv
KYRO_LOCAL_ONLY=true
KYRO_LOCAL_MODEL=qwen2.5-coder:7b
KYRO_LOCAL_MODEL_URL=http://127.0.0.1:11434/v1
KYRO_DEPLOY_LOCAL_MODEL_URL=http://host.docker.internal:11434/v1
```

The first URL is for native startup; the deployment URL is for Docker. Use a model that is actually installed, start its server, then check **AI Models** for availability. After editing `.env`, run `docker compose up -d` to recreate a service whose configuration changed. On Linux, and on some Docker Desktop setups, the model server must accept connections from Docker's host gateway; see [troubleshooting](docs/TROUBLESHOOTING.md). Protect that endpoint with appropriate interface/firewall restrictions.

Local-only blocks external model URLs and never falls back to cloud. Optional HTTPS cloud inference requires operator cost authorization, local-only disabled and backend provider configuration. `KYRO_CLOUD_PROTOCOL` selects `chat` or `responses`; `KYRO_MODEL_ROUTING` selects local, cloud, or automatic routing. Automatic routing uses local inference for lower-severity dependency tasks and an authorized cloud model for source-code or high-severity tasks. Plans record the selected provider; execution stays bound to it. Provider failures remain failures, and a server-configured request ceiling bounds cloud attempts. Monetary estimates require verified operator-provided prices; unavailable costs and tokens remain unavailable. Live cloud acceptance remains blocked by the configured provider's client policy.

To start your existing Qwen3 GGUF with the project-local official llama.cpp binary:

```powershell
python tools/install_llama.py
./infrastructure/scripts/start-model.ps1 -ModelPath 'C:/path/to/your/Qwen3-8B-Q4_K_M.gguf'
```

The installer verifies GitHub asset SHA-256 digests and downloads binaries, not model weights. The launch script uses one 8192-token slot, quantized KV cache, automatic GPU fitting and a 1024-token reasoning ceiling. It binds loopback and sleeps after idle time to release resources. Do not keep another heavy model loaded simultaneously. The model adapter uses JSON-schema structured completions; compatible providers must implement that response format for remediation.

## Connect GitHub

Preferred: create a GitHub App restricted to selected repositories with **Metadata: read**, **Contents: read/write**, **Pull requests: read/write**. Configure backend `KYRO_GITHUB_APP_ID`, `KYRO_GITHUB_INSTALLATION_ID` and `KYRO_GITHUB_APP_PRIVATE_KEY_PATH`. Keep the private key outside the checkout. Install the App only on repositories you authorize KYRO to modify.

Alternatively configure an OAuth application's `KYRO_GITHUB_CLIENT_ID` with device flow enabled. Setup displays GitHub's code and authorization URL; OAuth credentials are encrypted in the backend data directory. OAuth's `repo` scope is broader than a repository-restricted App; the App is preferred. A fine-grained PAT can be supplied through backend `KYRO_GITHUB_TOKEN` with selected repository Contents/PR permissions. Never paste it into frontend configuration or source. Local service environment is available only to the server process.

The repositories page lists accessible repositories, branches and immutable snapshots. PR creation separately requires a VERIFIED report and explicit user approval. KYRO creates a **draft**, never merges, and refuses if the base SHA changed. An actual authorized repository is required for live GitHub acceptance; unit contract fixtures do not establish live acceptance.

**Current import behavior:** GitHub authorization is required and the UI selects repositories available to that connection. Public repository import from a URL without a token is planned; it is not implemented in this checkout. Private repositories always require permission. Automatic fork-based delivery to someone else's repository is also pending. Do not expect a link alone to grant write access.

## How to use KYRO

1. **Sign in and check setup.** Open **Workspace setup** to inspect GitHub, scanner and model readiness. Missing integrations are reported explicitly.
2. **Create a project.** Go to **Projects**, enter a name and optional description, and click **Create project**.
3. **Connect a repository.** Go to **Repositories**, choose the project, GitHub repository and branch, then click **Connect**. This queues retrieval and indexing; watch **Agent Workspace** until the repository is READY.
4. **Inspect the repository.** Open the connected repository to browse actual source files, languages, frameworks, test-file discovery and indexed symbols. Retrieval already performs analysis; **Analyze** can update the index of the stored snapshot. A stored snapshot does not silently follow later remote commits.
5. **Run scanners.** Click **Run scanners**. KYRO runs the three real tools sequentially. Inspect **Security** and the execution timeline for completed results, partial coverage or errors.
6. **Investigate a finding.** Open **Findings**, search/filter results and select an issue. Review its affected location/version, scanner evidence, contextual risk factors and reachability category. **Enrich finding** queues external advisory lookups where identifiers are available.
7. **Request a plan.** Click **Create remediation plan**. The configured model receives bounded relevant context and proposes a root cause, strategy, risks, existing files and build/test commands. Proposed outcomes are not test results.
8. **Review and approve.** Inspect every proposed file and command. Select **I reviewed the changes, risks and commands**, click **Approve plan**, then **Execute approved fix**. Approval binds the plan, source commit and file hashes. Execution modifies a separate managed Docker workspace, not the original remote branch.
9. **Follow execution.** Inspect **Agent Workspace** and the remediation page for actual model/tool actions, checkpoints, diff, command output and errors. Bounded revisions can address failed patch validation or tests within the approved scope; an exhausted agent remains failed.
10. **Verify independently.** Click **Run independent verification** after a patch exists. A separate runner reruns approved commands and scanners, compares findings, checks scope and records remaining/new findings. Inspect the outcome in **Verification** or the remediation page.
11. **Download evidence.** Click **Download evidence report**. The JSON report includes the original finding, root cause, changed files, diff, build/test output, independent scans, before/after comparison and limitations.
12. **Approve delivery when eligible.** A VERIFIED real-repository task can show **Create draft pull request**. Publishing requires a separate approval and authorized GitHub write access. The product only reports a PR after GitHub confirms creation. A reviewer decides whether to merge; KYRO does not automatically merge or deploy.

For an unfamiliar repository, begin with one finding and a small reviewed patch. Missing project dependencies may require a trusted custom sandbox image before meaningful tests can run. A repository with no discovered test suite must not be presented as having passed tests.

### Verification outcomes

| Outcome | Meaning |
|---|---|
| VERIFIED | The selected finding resolved under complete recorded baseline/rescan coverage, scope checks and successful build/test commands. This is not proof of complete application security. |
| PARTIALLY_VERIFIED | Some evidence supports the fix, but tests, build or scanner coverage are incomplete. |
| FAILED | The original issue remains, a quality gate fails, tests fail, scope changes unexpectedly or new findings are introduced. |
| INCONCLUSIVE | Required evidence or a complete baseline is unavailable, so the system cannot establish the result. |

### Finding and scanner limits

Static imports and call references do not prove runtime exploitability. **NO_REFERENCE_FOUND** does not establish safety. **NOT_APPLICABLE** means a tool found no supported dependency input; **PARTIAL** indicates incomplete scanner analysis. Both leave missing coverage visible. Zero findings is not a security certification.

### Find your work in the interface

| Area | What to use it for |
|---|---|
| Overview | Actual repository, finding, scan and remediation counts and workflow shortcuts. |
| Projects / Repositories | Project management, repository/branch selection, snapshot metadata and source inspection. |
| Security / Findings / Dependencies | Scanner runs, evidence-backed finding review and dependency inventories. |
| Repository evidence graph | Interactive relationships and supporting evidence reached from repository/finding details. |
| Remediation / Agent Workspace | Plan review, approvals, generated diffs, actions, jobs and recovery history. |
| Verification / Pull Requests | Independent results, downloadable reports and confirmed draft PR records. |
| Analytics / AI Models / Settings | Recorded usage/history, model availability/configuration and runtime/audit policies. |

## Automatic recovery

Recovery is enabled by default for eligible imports, fixture retrieval, indexing, baseline scans and vulnerability enrichment. Temporary network/provider failures can retry; interrupted read jobs can resume after the backend restarts. Attempt numbers, original failure reasons, scheduled delays and final outcomes persist in jobs and audit records.

Default policy: **three total attempts**, delays of **two and four seconds**, provider Retry-After delays capped at **60 seconds**, and the original overall job deadline. Cancellation stops recovery. Scheduled retries do not block ready jobs. Manual retry controls preserve the original failed job and its evidence.

| Backend setting | Default |
|---|---|
| `KYRO_AUTOMATIC_RECOVERY` | `true` |
| `KYRO_JOB_MAX_ATTEMPTS` | `3` |
| `KYRO_JOB_RETRY_DELAY` | `2` seconds |

Recovery cannot create missing source, grant permissions, repair every arbitrary product bug or turn failed tests into a pass. Interrupted agent edits, verification and GitHub delivery do not automatically replay. KYRO does not rewrite itself, expose credentials, expand sandbox permissions, merge or deploy as a recovery action. See [the complete policy and actual fault-injection evidence](docs/AUTOMATIC_RECOVERY.md).

## Controlled demo and actual workflow

Create a project → Repositories → **Import test fixture**. The fixture contains intentionally vulnerable code and a dependency; it is always marked TEST FIXTURE. Run scanners → inspect the eval finding → create a model plan → review its files, risks and commands → approve → execute → independently verify. Actual dependency findings remain unless their own approved task addresses them. A fixture cannot publish a PR.

This is deliberately vulnerable source used for real scanner/model/container execution. Use it locally to learn the workflow; never deploy it as an application. Its findings and metrics must not be confused with production repository results.

## Docker deployment

```powershell
./infrastructure/scripts/setup-scanners.ps1
docker compose build
docker compose up -d
```

Open http://127.0.0.1:8787. Default Compose exposes loopback only. `KYRO_DEPLOY_LOCAL_MODEL_URL` controls the container's local host endpoint, e.g. `http://host.docker.internal:11434/v1`; the model server must accept the Docker host connection. SQLite and source persist in the `kyro-data` volume. PostgreSQL overlay: configure a secret `POSTGRES_PASSWORD` in `.env`, then `docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build`. Do not run `down -v` unless you intend to delete stored data.

**Deployment boundary:** the backend's Docker socket grants control of the Docker host. Repository execution containers never receive that socket, credentials or host home directories. Use a dedicated Docker host/VM and restrict KYRO to trusted operators. See [sandbox limitations](docs/SANDBOX_SECURITY.md) and [deployment guide](docs/DEPLOYMENT_GUIDE.md) before broader use. Public deployment requires separate authorization and security hardening.

Stop the local deployment with `docker compose stop`. Check logs with `docker compose logs --tail 100 kyro`. The data volume contains repository snapshots, findings, reports, caches and encrypted OAuth credentials; protect it and back it up with the encryption key. Do not publish that runtime data with the source code.

## What has been tested

Recorded validation on 2026-11-07:

- **132 backend tests**, **9 frontend unit tests** and **14 deployed browser tests** passed. Browser checks include three responsive/accessibility viewports and retained actual recovery history.
- Python lint/types, frontend lint/types/production build and Node/Python dependency audits passed.
- A fresh deployed controlled fixture completed actual local-model planning, explicit approval, Docker modification, build/four tests and all three independent rescans: **VERIFIED, 22→21 findings, zero new findings**. Six additional independent security regression tests and sandbox boundary/timeout probes passed.
- Real indexing interrupted by an abrupt acceptance-container restart completed the **same job on attempt 2**, indexing **1,504 fixture files** without a manual retry.
- All **19 authorized repositories** were processed sequentially: **17 indexed**, **8 complete scanner runs**, **9 inconclusive runs** and **2 empty repositories**. The recorded cohort contains **347 normalized scanner findings**; this does not establish that every repository's builds/tests or fixes passed.
- A real-repository local model produced a reviewable plan, and OSV/NVD/EPSS/KEV enrichment returned recorded sources. That repository had no discovered tests and its plan still required dependency compatibility review.

Live GitHub App/OAuth acceptance, actual product-generated GitHub PR creation, successful live cloud inference and public/team deployment are still pending. Earlier measured backend coverage was 69.87%; no updated coverage number is claimed. See the [test execution report](docs/TEST_EXECUTION_REPORT.md) and [implementation status](IMPLEMENTATION_STATUS.md) for exact scope, evidence and failures. Publishing this source repository is separate from testing KYRO's remediation PR engine.

## Validation

```powershell
cd backend
uv sync --frozen
uv run pytest --cov=app
uv run ruff check app migrations
uv run mypy app
uvx pip-audit -r requirements.txt
cd ../frontend
npm ci
npm run typecheck
npm run lint
npm run test
npm audit
npm run build
```

`tools/live_acceptance.py` tests only the explicitly labelled fixture on an isolated test server at port 8788. See [benchmarking](docs/BENCHMARKING_FRAMEWORK.md) for its reproducible launch. Browser acceptance uses `npm run test:e2e` after that setup. Fixtures are separated from live evidence under `docs/evidence/`.

## Scope and limitations

Initial Semgrep scope: seven local rules for dynamic evaluation/execution, pickle, shell calls and unsafe YAML. OSV and Trivy provide advisory-backed dependency coverage. Missing supported inputs report NOT_APPLICABLE and unavailable coverage. Python/JS/TS symbols are supported; other languages receive file/manifest indexing. Static reachability is conservative; no runtime exploit claim is made. Default sandbox contains Python, pytest, Node and npm; arbitrary framework dependencies, Go and Rust toolchains require a trusted custom sandbox image. Dependency installation inside untrusted scripts has no network access by default. Read jobs have bounded automatic recovery; agent edits and writes retain approved retries and checkpoint review.

Findings and logs may contain sensitive repository information. Protect the data directory, volume, encryption key and backups. Do not run concurrent application replicas with SQLite or the single-worker dispatcher. See the implementation status for exact remaining acceptance blockers.

## Architecture and source layout

KYRO is a modular monolith: a React/TypeScript/Vite frontend, a FastAPI/Pydantic backend, SQLAlchemy/Alembic persistence, a database-backed job worker, independent scanner adapters, a local/optional-cloud model router and a Docker sandbox. SQLite is the local default; a PostgreSQL Compose overlay is provided. No Redis, graph database, paid model provider or multi-agent cluster is mandatory.

```text
frontend/             Web interface, API client and browser/unit tests
backend/app/          API, database, scanners, intelligence, agent, sandbox and verification
backend/migrations/   Alembic database migrations
infrastructure/       Docker images, Compose acceptance overlay and startup scripts
tests/fixtures/       Explicitly labelled vulnerable test source
tools/                Reproducible research, audit, acceptance and packaging harnesses
docs/                 Architecture, threat model, user/deployment guidance and recorded evidence
```

## Documentation

- [Whole-product checklist](docs/PRODUCT_CHECKLIST.md) and [implementation status](IMPLEMENTATION_STATUS.md)
- [Architecture](docs/PRODUCT_ARCHITECTURE.md), [system design](docs/SYSTEM_DESIGN.md), [database schema](docs/DATABASE_SCHEMA.md) and [API contracts](docs/API_DOCUMENTATION.md)
- [Repository intelligence](docs/REPOSITORY_INTELLIGENCE.md), [reachability](docs/REACHABILITY_ANALYSIS.md), [evidence graph](docs/ATTACK_PATH_ARCHITECTURE.md) and [vulnerability intelligence](docs/VULNERABILITY_INTELLIGENCE.md)
- [Agent reliability](docs/AGENT_RELIABILITY.md), [patch quality](docs/PATCH_QUALITY.md), [independent verification](docs/VERIFICATION_ENGINE.md) and [automatic recovery](docs/AUTOMATIC_RECOVERY.md)
- [Threat model](docs/THREAT_MODEL.md), [sandbox security](docs/SANDBOX_SECURITY.md) and [data isolation](docs/DATA_ISOLATION.md)
- [Deployment](docs/DEPLOYMENT_GUIDE.md), [troubleshooting](docs/TROUBLESHOOTING.md) and [CI/CD](docs/CI_CD_INTEGRATION.md)
- [Test execution report](docs/TEST_EXECUTION_REPORT.md), [repository audit](docs/REPOSITORY_VALIDATION_REPORT.md) and [benchmarking framework](docs/BENCHMARKING_FRAMEWORK.md)

## License

KYRO's original source is available under the [MIT License](LICENSE). Integrated scanners, models, dependencies and bundled third-party assets retain their respective licenses; review those terms for your deployment and redistribution.
