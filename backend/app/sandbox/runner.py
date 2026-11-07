import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.core.security import redact
from app.jobs.worker import Cancelled, cancelled

MAX_OUTPUT = 20_000_000


def process(argv: list[str], timeout: int, job_id: str | None = None, container: str | None = None) -> dict:
    start = time.monotonic()
    status = "COMPLETED"
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        proc = subprocess.Popen(argv, stdout=stdout, stderr=stderr, stdin=subprocess.DEVNULL, shell=False)
        while proc.poll() is None:
            if job_id and cancelled(job_id):
                status = "CANCELLED"
                break
            if time.monotonic() - start > timeout:
                status = "TIMED_OUT"
                break
            if stdout.tell() + stderr.tell() > MAX_OUTPUT:
                status = "OUTPUT_LIMIT"
                break
            time.sleep(0.2)
        if status != "COMPLETED":
            if container:
                subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=10, check=False)
            proc.kill()
        proc.wait(timeout=10)
        stdout.seek(0)
        stderr.seek(0)
        out = stdout.read(MAX_OUTPUT + 1)
        err = stderr.read(MAX_OUTPUT + 1)
        if len(out) + len(err) > MAX_OUTPUT:
            status = "OUTPUT_LIMIT"
        if status == "CANCELLED":
            raise Cancelled("Container execution cancelled")
        return {"command": argv, "status": status, "exit_code": proc.returncode, "stdout": redact(out.decode("utf-8", errors="replace")), "stderr": redact(err.decode("utf-8", errors="replace")), "duration_seconds": round(time.monotonic() - start, 3)}


def docker_health() -> dict:
    try:
        result = process(["docker", "version", "--format", "{{json .Server}}"], 10)
        if result["exit_code"] != 0:
            return {"available": False, "error": "Docker Linux engine unavailable"}
        data = json.loads(result["stdout"])
        return {"available": True, "version": data["Version"], "platform": data.get("Os", "unknown")}
    except (OSError, ValueError, KeyError):
        return {"available": False, "error": "Docker is not installed or unavailable"}


def installed_image(image: str) -> bool:
    try:
        result = process(["docker", "image", "inspect", image], 10)
        return result["exit_code"] == 0
    except OSError:
        return False


def managed_mount(root: Path, destination: str, readonly: bool = True) -> str:
    root = root.resolve()
    if not root.is_relative_to(settings.data_dir.resolve()):
        raise ValueError("Mount must stay inside managed KYRO data")
    if settings.workspace_volume:
        subpath = root.relative_to(settings.data_dir.resolve()).as_posix()
        value = f"type=volume,src={settings.workspace_volume},dst={destination},volume-subpath={subpath}"
    else:
        value = f"type=bind,src={root},dst={destination}"
    return value + (",readonly" if readonly else "")


def container_command(root: Path, image: str, args: list[str], *, writable=False, network="none", extra_mounts: list[str] | None = None, extra_env: dict[str, str] | None = None, memory=1024) -> tuple[list[str], str]:
    name = "kyro-" + uuid4().hex
    root = root.resolve()
    if not root.is_relative_to(settings.data_dir.resolve()) or not root.is_dir():
        raise ValueError("Container mount must be a managed KYRO workspace")
    mount = managed_mount(root, "/workspace", readonly=not writable)
    argv = ["docker", "run", "--rm", "--name", name, "--init", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=128", "--cpus=1", f"--memory={memory}m", f"--memory-swap={memory}m", "--network", network, "--tmpfs", "/tmp:rw,noexec,nosuid,size=256m", "--env", "HOME=/tmp", "--env", "PYTHONDONTWRITEBYTECODE=1", "--workdir", "/workspace", "--mount", mount]
    if writable:
        argv += ["--user", "1000:1000"]
    for mount_value in extra_mounts or []:
        argv += ["--mount", mount_value]
    for key, value in (extra_env or {}).items():
        argv += ["--env", f"{key}={value}"]
    return [*argv, image, *args], name


def validate_command(argv: list[str]):
    allowed = (
        ["python", "-m", "pytest"], ["python", "-m", "unittest"], ["python", "-m", "compileall"],
        ["npm", "test"], ["npm", "run", "build"], ["npm", "run", "typecheck"],
        ["cargo", "test"], ["cargo", "check"], ["go", "test"], ["go", "build"],
    )
    if len(argv) > 20 or not any(argv[:len(prefix)] == prefix for prefix in allowed):
        raise ValueError("Command is not an approved build or test command")
    if any(len(arg) > 200 or any(char in arg for char in ["\x00", "\n", "\r"]) for arg in argv):
        raise ValueError("Invalid command argument")
    if argv[:3] == ["python", "-m", "pytest"] and any(arg.startswith(("-p", "--override-ini")) for arg in argv[3:]):
        raise ValueError("Pytest plugin overrides are not permitted")


def execute_command(root: Path, command: dict, job_id: str | None = None) -> dict:
    validate_command(command["argv"])
    if not installed_image(settings.sandbox_image):
        raise RuntimeError("Sandbox image missing. Run the documented Docker setup command.")
    argv, name = container_command(root, settings.sandbox_image, command["argv"], writable=True)
    result = process(argv, settings.command_timeout, job_id, name)
    status = "PASSED" if result["status"] == "COMPLETED" and result["exit_code"] == 0 else "FAILED"
    test_count = None
    if command["kind"] in {"test", "regression"} and status == "PASSED":
        test_count = executed_tests(result["stdout"] + "\n" + result["stderr"])
        if not test_count:
            status = "NO_TESTS" if test_count == 0 else "INCONCLUSIVE"
    return {**result, "command": command["argv"], "kind": command["kind"], "status": status, "tests_executed": test_count}


def apply_patch(root: Path, changes: list[dict], checkpoint_dir: Path, job_id: str | None = None) -> dict:
    """Apply validated replacements with fixed trusted code inside the sandbox.

    The model cannot choose this command or executable. -I prevents repository
    sitecustomize/PYTHONPATH from being loaded while applying a patch.
    """
    if not installed_image(settings.sandbox_image):
        raise RuntimeError("Sandbox image missing; patch was not applied")
    payload = checkpoint_dir / "patch-input.json"
    payload.write_text(json.dumps(changes), encoding="utf-8")
    code = """import hashlib,json,pathlib
root=pathlib.Path('/workspace').resolve()
changes=json.loads(pathlib.Path('/patch/patch-input.json').read_text())
checked=[]
for change in changes:
    path=root/change['path']
    if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError('Invalid patch path')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=change['before_hash']:
        raise ValueError('Patch checkpoint hash changed')
    checked.append((path,change['content']))
for path,content in checked:
    path.write_text(content,encoding='utf-8',newline='')
print(json.dumps({'modified_files':len(checked)}))
"""
    argv, name = container_command(root, settings.sandbox_image, ["python", "-I", "-c", code], writable=True, extra_mounts=[managed_mount(checkpoint_dir, "/patch")])
    result = process(argv, settings.command_timeout, job_id, name)
    if result["status"] != "COMPLETED" or result["exit_code"] != 0:
        raise RuntimeError("Sandbox patch application failed: " + result["stderr"][-500:])
    return {"tool": "apply_patch", "status": "PASSED", "exit_code": result["exit_code"], "duration_seconds": result["duration_seconds"], "stdout": result["stdout"], "stderr": result["stderr"]}


def executed_tests(output: str) -> int | None:
    unittest = re.search(r"Ran (\d+) tests?\b", output)
    if unittest:
        return int(unittest[1])
    cargo = re.findall(r"running (\d+) tests?\b", output)
    if cargo:
        return sum(map(int, cargo))
    passed = re.findall(r"\b(\d+) passed\b", output)
    if passed:
        return max(map(int, passed))
    if "no tests ran" in output or "no test files" in output.lower():
        return 0
    return None
