# Environment inspection — 2026-11-07

New project; no existing KYRO directory. Other projects are preserved.

Windows 11 host, Python 3.13.15, Node 24.14.1, uv 0.12.13, Git installed.
Docker Desktop CLI 29.9.2 installed; Linux engine initially stopped. WSL2 Ubuntu installed, stopped.
RTX 3050 laptop GPU: 6144 MiB VRAM, 78 MiB initially in use. Physical RAM: 16 GB, about 3.3 GB initially free.
Disk C: about 36 GB free. This constrains image downloads; heavyweight concurrent services are avoided.
Semgrep, OSV-Scanner, Trivy not on Windows PATH. Scanner installation will be project-local where possible.
No llama.cpp listener at 127.0.0.1:8080. Existing Ollama listener at 127.0.0.1:11434 exposes qwen2.5-coder:7b, Q4_K_M, 4.68 GB model.
One optional cloud-provider credential environment variable exists; its value was not inspected and cloud use is not authorized.
No GitHub token environment variable detected. An authorized test repository remains a required external dependency.
