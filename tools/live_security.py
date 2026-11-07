"""Live controlled sandbox checks and independent generated-patch regression tests.

Run from backend with `uv run python ../tools/live_security.py`.
This never executes repository code on the host or modifies a deliverable patch.
"""
import json
import pathlib
import shutil
import sys
from datetime import UTC, datetime
from uuid import uuid4

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.core.security import digest  # noqa: E402
from app.sandbox.runner import apply_patch, container_command, execute_command, process  # noqa: E402

DATA = ROOT / "data" / "acceptance"
settings.data_dir = DATA
settings.workspace_volume = ""
working = DATA / "security-checks" / uuid4().hex
working.mkdir(parents=True)

# Trusted harness executes in exactly the same container policy as repository tests.
boundary = r'''
import errno, json, os, pathlib, socket
checks = {}
checks['nonroot'] = os.getuid() == 1000
checks['no_docker_socket'] = not pathlib.Path('/var/run/docker.sock').exists()
checks['no_host_home'] = not pathlib.Path('/host').exists()
checks['no_credentials'] = not any(k in os.environ for k in ['KYRO_GITHUB_TOKEN','AGENTROUTER_API_KEY','KYRO_CLOUD_API_KEY'])
try:
    pathlib.Path('/etc/kyro-test').write_text('blocked')
    checks['root_filesystem_readonly'] = False
except OSError:
    checks['root_filesystem_readonly'] = True
try:
    socket.create_connection(('1.1.1.1',443), timeout=2).close()
    checks['egress_blocked'] = False
except OSError:
    checks['egress_blocked'] = True
checks['process_limit'] = pathlib.Path('/sys/fs/cgroup/pids.max').read_text().strip() == '128'
checks['memory_limit'] = int(pathlib.Path('/sys/fs/cgroup/memory.max').read_text()) == 1024 * 1024 * 1024
pathlib.Path('write-check.txt').write_text('managed workspace only')
checks['workspace_writable'] = pathlib.Path('write-check.txt').read_text() == 'managed workspace only'
print(json.dumps(checks))
raise SystemExit(0 if all(checks.values()) else 1)
'''
argv, name = container_command(working, settings.sandbox_image, ["python", "-c", boundary], writable=True)
execution = process(argv, 30, container=name)
checks = json.loads(execution["stdout"]) if execution["exit_code"] == 0 else {}
argv, name = container_command(working, settings.sandbox_image, ["python", "-c", "import time; time.sleep(60)"], writable=True)
timeout = process(argv, 2, container=name)
cleanup = process(["docker", "inspect", name], 10)
checks["timeout_enforced_and_container_removed"] = timeout["status"] == "TIMED_OUT" and cleanup["exit_code"] != 0
probe = working / "patch-probe.py"
probe.write_text("# Original controlled file\n", encoding="utf-8")
checkpoints = working / "checkpoints"
checkpoints.mkdir()
patch_result = apply_patch(working, [{"path": "patch-probe.py", "before_hash": digest(probe.read_bytes()), "content": "# Controlled Docker-applied patch\n"}], checkpoints)
checks["docker_patch_application"] = probe.read_text() == "# Controlled Docker-applied patch\n" and patch_result["status"] == "PASSED"

state = json.loads((DATA / "workflow.json").read_text())
source = DATA / "workspaces" / state["remediation_id"]
regression = working / "regression"
shutil.copytree(source, regression)
(regression / "test_security_regression.py").write_text('''import unittest
from app import calculate

class SecurityRegression(unittest.TestCase):
    def test_rejects_code_and_nonnumeric_inputs(self):
        for expression in ["__import__('os').system('id')", "open('/tmp/kyro-exploit', 'w')", "(1).__class__", "[1, 2]", "{'x': 1}", "'text'", "unknown_name", "lambda: 1", "1; 2"]:
            with self.subTest(expression=expression):
                with self.assertRaises((ValueError, TypeError, SyntaxError)):
                    calculate(expression)

    def test_arithmetic_contract(self):
        for expression, expected in [('2+3*4', 14), ('(2+3)*4', 20), ('-2 + 5', 3), ('9/3', 3)]:
            with self.subTest(expression=expression):
                self.assertEqual(calculate(expression), expected)
''', encoding="utf-8")
test_result = execute_command(regression, {"kind": "regression", "argv": ["python", "-m", "pytest", "-q"]})
report = {"created_at": datetime.now(UTC).isoformat(), "fixture": "Explicit controlled KYRO arithmetic fixture", "remediation_id": state["remediation_id"], "boundary_checks": checks, "boundary_execution": execution, "timeout_execution": timeout, "independent_security_regression": test_result, "limitations": ["Docker isolation is not a proof against kernel/container escapes", "Checks cover this configured sandbox, not every malicious repository", "Regression tests run in a disposable copy; the deliverable patch is unchanged"]}
(ROOT / "docs" / "evidence" / "live-security-checks.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"boundary_checks": checks, "regression_status": test_result["status"], "tests_executed": test_result["tests_executed"]}, indent=2))
if not all(checks.values()) or test_result["status"] != "PASSED":
    raise SystemExit("Live security checks failed; inspect recorded evidence")
