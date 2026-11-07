# CI/CD integration

`.github/workflows/ci.yml` runs locked installation, backend lint/type/tests/audit and frontend lint/tests/audit/production build on push/PR or manual dispatch. It has read-only Contents permission and uploads test evidence. The workflow has been prepared locally; no GitHub Actions run is claimed until this project is published to an authorized repository.

The checked-in GitHub Actions workflow validates the KYRO product itself: locked backend/frontend installs, lint/typecheck/tests/audit and production build. No repository credentials or paid model endpoints are required for unit checks. Docker/live-model acceptance is a separately authorized environment check.

Target repository scans and remediation are manual in this release. A future action can call KYRO's owned API with a short-lived authorized session or a purpose-built integration credential. Long requests must enqueue jobs and inspect scanner/verification status rather than trusting HTTP 202. A partial scan cannot be published as a clean security check.

Do not provide secrets to fork PR workflows or run untrusted repository scripts on host runners. KYRO's PRs are drafts; merging/deployment remains a reviewer action. Automated PR remediation schedules, status publication and unattended repository workflows are not implemented and are not represented as working integrations.
