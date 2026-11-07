# Sandbox security

Every untrusted build/test runs in a managed Docker workspace. Defaults: non-root uid 1000, read-only container root, writable task-only workspace, no network, no capabilities, no-new-privileges, one CPU, 1 GB memory/swap ceiling, 128 process limit, 180-second command timeout, bounded output and temporary storage. Host home directories, credentials and the Docker socket are never mounted into these execution containers. Cancellation removes the task-named container.

Semgrep reads immutable source and local rules with metrics/version networking disabled. OSV/Trivy read source and need network for advisory metadata/database retrieval; they are trusted scanner images, not arbitrary scripts. Trivy's isolated cache volume provides disk-backed temporary extraction. Scanner egress is not domain-filtered by this first release. Confidential deployments need an egress firewall and offline advisory cache strategy.

Compose uses a named data volume with Docker volume-subpath mounts so children see only their task/source/rules directory. Native Windows startup uses checked bind mounts inside the KYRO data root. Cleanup validates the final absolute path before recursive deletion.

**Residual risk:** Docker shares a kernel and scanner parsing can contain vulnerabilities. The backend has Docker-host control via its socket; compromise of the API/worker can compromise that host. Deploy on a dedicated trusted workstation/VM and expose loopback. This is not a hardened hostile multi-tenant service. Rootless Docker or gVisor on a supported Linux host is a future hardening path; gVisor is not enabled or tested here. No host sandbox permissions or trust hashes were weakened by KYRO.

Custom sandbox images may provide project-specific dependencies/toolchains. Images are operator-controlled configuration; never let a repository select a privileged image or mount. Networked dependency installation and arbitrary shell tools are not approved by the default policy.
