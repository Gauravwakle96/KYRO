"""Check a deployed fixture patch and sandbox without touching user repositories."""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECK = r'''
import json, shutil, sys
from datetime import UTC, datetime
from uuid import uuid4
from app.core.config import settings
from app.database import SessionLocal, Remediation, Repository, ModelUsage
from app.agents.engine import workspace
from app.sandbox.runner import container_command, process, execute_command, apply_patch
from app.core.security import digest
from sqlalchemy import select

with SessionLocal() as db:
    task = db.get(Remediation, sys.argv[1])
    repo = db.get(Repository, task.repository_id) if task else None
    if repo is None or repo.source != 'fixture' or task.verification.get('status') != 'VERIFIED':
        raise ValueError('This security check requires a verified labelled fixture patch')
    root = settings.data_dir / 'security-checks' / uuid4().hex
    root.mkdir(parents=True)
    regression = root / 'regression'
    shutil.copytree(workspace(task), regression)
    (regression / 'test_security_regression.py').write_text("""import unittest
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
""", encoding='utf-8')
    tests = execute_command(regression, {'kind': 'regression', 'argv': ['python', '-m', 'pytest', '-q']})
    boundary = """import json, os, pathlib, socket
checks = {}
checks['nonroot'] = os.getuid() == 1000
checks['no_docker_socket'] = not pathlib.Path('/var/run/docker.sock').exists()
checks['no_host_home'] = not pathlib.Path('/host').exists()
checks['no_credentials'] = not any(k in os.environ for k in ['KYRO_GITHUB_TOKEN', 'KYRO_CLOUD_API_KEY'])
try:
    pathlib.Path('/etc/kyro-test').write_text('blocked', encoding='utf-8')
    checks['root_filesystem_readonly'] = False
except OSError:
    checks['root_filesystem_readonly'] = True
try:
    socket.create_connection(('1.1.1.1', 443), timeout=2).close()
    checks['egress_blocked'] = False
except OSError:
    checks['egress_blocked'] = True
checks['process_limit'] = pathlib.Path('/sys/fs/cgroup/pids.max').read_text(encoding='utf-8').strip() == '128'
checks['memory_limit'] = int(pathlib.Path('/sys/fs/cgroup/memory.max').read_text(encoding='utf-8')) == 1024 * 1024 * 1024
quota, period = pathlib.Path('/sys/fs/cgroup/cpu.max').read_text(encoding='utf-8').split()
checks['cpu_limit'] = quota != 'max' and int(quota) == int(period)
pathlib.Path('write-check.txt').write_text('managed workspace', encoding='utf-8')
checks['workspace_writable'] = pathlib.Path('write-check.txt').exists()
print(json.dumps(checks))
raise SystemExit(0 if all(checks.values()) else 1)
"""
    argv, name = container_command(root, settings.sandbox_image, ['python', '-I', '-c', boundary], writable=True)
    execution = process(argv, 30, container=name)
    checks = json.loads(execution['stdout']) if execution['exit_code'] == 0 else {}
    argv, name = container_command(root, settings.sandbox_image, ['python', '-I', '-c', 'import time; time.sleep(60)'], writable=True)
    timeout = process(argv, 2, container=name)
    cleanup = process(['docker', 'inspect', name], 10)
    checks['timeout_enforced_and_container_removed'] = timeout['status'] == 'TIMED_OUT' and cleanup['exit_code'] != 0
    probe = root / 'patch-probe.py'
    probe.write_text('# Original controlled file\n', encoding='utf-8')
    checkpoint = root / 'checkpoints'
    checkpoint.mkdir()
    result = apply_patch(root, [{'path': 'patch-probe.py', 'before_hash': digest(probe.read_bytes()), 'content': '# Controlled Docker patch\n'}], checkpoint)
    checks['docker_patch_application'] = probe.read_text(encoding='utf-8') == '# Controlled Docker patch\n' and result['status'] == 'PASSED'
    usage = [{'model': u.model, 'provider': u.provider, 'input_tokens': u.input_tokens, 'output_tokens': u.output_tokens, 'duration_seconds': u.duration_seconds, 'status': u.status, 'retries': u.retries, 'estimated_cost': u.estimated_cost} for u in db.scalars(select(ModelUsage).where(ModelUsage.remediation_id == task.id))]
    report = {'checked_at': datetime.now(UTC).isoformat(), 'fixture': 'Labelled vulnerable arithmetic fixture', 'remediation_id': task.id, 'boundary_checks': checks, 'boundary_execution': execution, 'timeout_execution': timeout, 'independent_security_regression': tests, 'usage': usage, 'passed': bool(checks) and all(checks.values()) and tests['status'] == 'PASSED', 'limitations': ['Disposable copy; original verified patch unchanged', 'Shared-kernel Docker isolation; no container-escape proof', 'Selected fixture does not establish general agent reliability']}
    print(json.dumps(report))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-dir', type=Path, default=ROOT / 'data/recovery-workflow')
    parser.add_argument('--evidence-dir', type=Path, default=ROOT / 'docs/evidence/recovery-workflow')
    args = parser.parse_args()
    container = 'kyro-clean-acceptance-kyro-1'
    identity = subprocess.check_output(['docker', 'inspect', container, '--format', '{{index .Config.Labels "com.docker.compose.project"}}'], text=True).strip()
    if identity != 'kyro-clean-acceptance':
        raise RuntimeError('Checks require the dedicated acceptance deployment')
    state = json.loads((args.state_dir / 'workflow.json').read_text(encoding='utf-8'))
    result = subprocess.run(['docker', 'exec', container, 'python', '-c', CHECK, state['remediation_id']], capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError('Deployed security harness failed; no successful evidence recorded')
    report = json.loads(result.stdout)
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    (args.evidence_dir / 'live-security-checks.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'boundary_checks': report['boundary_checks'], 'tests_executed': report['independent_security_regression']['tests_executed'], 'usage': report['usage']}, indent=2))
    if not report['passed']:
        raise SystemExit('Actual security checks failed; inspect recorded evidence')


if __name__ == '__main__':
    main()
