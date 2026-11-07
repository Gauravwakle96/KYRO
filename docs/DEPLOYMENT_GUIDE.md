# Deployment guide

Use a dedicated workstation/VM and Docker Linux engine. Native startup and Compose share the same application/API and Alembic schema. Containers are version-pinned and package installation uses committed uv/npm lockfiles. First image pulls and Trivy database download need internet; later source/tests use configured isolation policies.

Run scanner setup, `docker compose build`, then `docker compose up -d`. The service publishes **127.0.0.1:8787 only**. Verify `docker compose ps`, `/api/health`, `/`, scanner readiness and a controlled fixture workflow. Health checks query the real database. A successful image build alone is not target acceptance.

The data volume stores SQLite, managed source/workspaces, OAuth encryption key and caches. Docker child execution uses volume-subpath mounts; Docker API 26+ is required. The backend uses non-root uid 1000 with socket group access. The Docker socket is a privileged infrastructure boundary; use a dedicated engine/VM and protect backend access.

For local host inference set `KYRO_DEPLOY_LOCAL_MODEL_URL=http://host.docker.internal:<port>/v1` and the actual model. The inference server must accept connections from Docker's gateway. KYRO does not change the existing model's bind address. A Linux host can provide a supported local endpoint without paid infrastructure. Cloud fallback stays blocked by default.

PostgreSQL uses the overlay and an ignored POSTGRES_PASSWORD. Keep database ports internal. For an authorized public deployment, configure HTTPS reverse proxy, secure cookies, exact host/origin values, server secret provisioning, backup/restore and infrastructure egress policy. Do not simply bind this initial single-owner Docker-host controller to the public internet.

Back up data and encryption key together. Stop jobs before moving data. `docker compose down` preserves named volumes; `down -v` deletes them and requires an intentional destructive decision. Upgrades run reviewed Alembic migrations before accepting traffic. SQLite and the one-worker dispatcher support a single application process; scaled dispatch requires a separate design.

For a fresh isolated local acceptance volume, run:

```powershell
docker compose -p kyro-clean-acceptance -f docker-compose.yml -f infrastructure/docker/compose.acceptance.yml up -d --build
python tools/deployment_acceptance.py
```

This uses loopback port 8789 and the distinct `kyro-clean-acceptance` volume, preserving the normal application data. It checks frontend serving, owner auth, database-backed projects, fixture ingestion/indexing and real scanner containers using named-volume subpaths. The override requires Compose support for `!override` (2.24.4+). The report is `docs/evidence/clean-deployment-acceptance.json`. It cannot substitute for authorized live GitHub acceptance.

The acceptance overlay clears GitHub configuration and requires local-only inference, separating synthetic fixture execution from operator credentials. Existing named volumes are preserved; running these commands again is not a clean-volume deployment test.

After deployment scanning, the same controlled fixture can exercise actual planning/editing/verification with separately scoped harness state and evidence:

```powershell
python tools/live_acceptance.py --url http://127.0.0.1:8789 --data-dir data/deployment-acceptance --evidence-dir docs/evidence/deployment --phase all
```

For the recorded recovery workflow, use the separately scoped `data/recovery-workflow` state. `python tools/deployed_security_acceptance.py --state-dir data/recovery-workflow --evidence-dir docs/evidence/recovery-workflow` checks its verified fixture patch in a disposable copy. `python tools/recovery_acceptance.py` creates a larger labelled fixture and abruptly restarts only the dedicated acceptance container to verify real automatic indexing recovery; the primary deployment is preserved.

This creates/uses only the labelled acceptance fixture, never creates a PR, and requires the real local model endpoint. The final delivered image has passed this workflow. Browser tests against that instance use `KYRO_TEST_URL=http://127.0.0.1:8789` and `KYRO_TEST_CREDENTIALS=../data/deployment-acceptance/test-login.json` from frontend. Runtime test credentials remain in ignored data; they are not release contents.
