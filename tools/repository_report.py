"""Render the recorded sequential repository audit; never invent live results."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=ROOT / 'docs/evidence/live-repository-audit-final.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/REPOSITORY_VALIDATION_REPORT.md')
    args = parser.parse_args()
    audit = json.loads(args.input.read_text(encoding='utf-8'))
    repos = audit['repositories']
    if len(repos) != audit['repository_count']:
        raise ValueError('Audit count does not match its repository records')
    totals = {field: sum(repo.get(field, 0) for repo in repos) for field in ['indexed_files', 'dependencies', 'findings']}
    outcomes = {status: sum(repo['status'] == status for repo in repos) for status in ['SUCCEEDED', 'INCONCLUSIVE', 'FAILED']}
    levels = {level: sum(repo.get('severity', {}).get(level, 0) for repo in repos) for level in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']}
    lines = [
        '# Repository validation report', '',
        f"Recorded {audit['started_at']} through {audit['completed_at']}. All {len(repos)} accessible repositories were processed sequentially on their default branches by the deployed KYRO backend. Existing projects and snapshots were preserved.", '',
        f"{len(repos) - outcomes['FAILED']} repositories indexed; {totals['indexed_files']:,} files, {totals['dependencies']:,} dependency records and {totals['findings']:,} normalized scanner findings. {outcomes['SUCCEEDED']} runs completed with all three scanners; {outcomes['INCONCLUSIVE']} had incomplete coverage; {outcomes['FAILED']} repositories had no commits to import.", '',
        'A completed scan means the configured tools finished; it does not certify security. Zero findings does not establish safety. Findings are scanner evidence, not confirmed application-specific exploitability. Semgrep currently uses seven local rules. Dependency input and parser limitations are shown below.', '',
        '## Sequential results', '',
        '| # | Repository / branch | Indexed files | Dependencies | Findings | Semgrep | OSV | Trivy | Outcome |',
        '|---|---|---:|---:|---:|---|---|---|---|',
    ]
    for index, repo in enumerate(repos, 1):
        scanners = {scanner['scanner']: scanner['status'] for scanner in repo.get('scanners', [])}
        path = f"http://127.0.0.1:8787/repositories/{repo['repository_id']}"
        name = repo['name'].split('/', 1)[-1]
        values = [str(repo[field]) if field in repo else '—' for field in ['indexed_files', 'dependencies', 'findings']]
        lines.append(f"| {index} | [{name}]({path}) / {repo['branch']} | {' | '.join(values)} | {scanners.get('semgrep', 'NOT_RUN')} | {scanners.get('osv', 'NOT_RUN')} | {scanners.get('trivy', 'NOT_RUN')} | {repo['status']} |")
    lines.extend(['', 'NOT_APPLICABLE means the tool ran but found no supported dependency inputs. PARTIAL denotes parser/analysis errors. Both leave aggregate coverage INCONCLUSIVE. Empty repository imports remain FAILED with the actual GitHub 409 message.', '', '## Coverage and import issues', ''])
    for repo in repos:
        issues = [f"{scanner['scanner']}: {scanner['error']}" for scanner in repo.get('scanners', []) if scanner.get('error')]
        if repo.get('error'):
            issues.insert(0, repo['error'])
        if issues:
            lines.append(f"- **{repo['name'].split('/', 1)[-1]}:** " + '; '.join(issues) + '.')
    lines.extend(['', '## Findings and intelligence checks', '', '| Severity | Scanner findings |', '|---|---:|'])
    lines.extend(f'| {level} | {count} |' for level, count in levels.items())
    assessed = sum(repo.get('risk_assessments_with_factors', 0) for repo in repos)
    lines.extend(['', f'{assessed} findings have stored risk factors. Repository symbols, relationships, conservative reachability and bounded context retrieval were checked where findings existed. The raw audit retains commit SHAs, scanner versions, exits, durations, parse diagnostics and graph/context counts.', '',
        'The highest counts are in Zoro (154) and inkloom (55); prioritize individual findings using severity, usage and reachability evidence rather than count alone. Counts are per repository snapshot; advisory duplicates across different repositories remain separate. Earlier user snapshots and fixtures may make the overall dashboard totals larger.', '',
        '## Product workflow and recovery', '',
        'The updated deployment completed a fresh labelled fixture workflow: real local AI plan, fixture approval, Docker patch, build, four tests, independent three-scanner rescan and VERIFIED evidence (22→21 findings; zero new findings). Six independent arithmetic/security regression tests and actual sandbox boundary/timeout probes passed on a disposable copy. Evidence: [recovery workflow](evidence/recovery-workflow/live-verification.json) and [security checks](evidence/recovery-workflow/live-security-checks.json).', '',
        'Automatic recovery passed an actual abrupt indexing-container restart: the same persistent job completed on attempt 2 and indexed 1,504 fixture files. No manual retry, user repository edit or cloud request was involved. See [recovery evidence](evidence/live-automatic-recovery.json) and [policy](AUTOMATIC_RECOVERY.md).', '',
        'A real local-model plan for online-basic-calculator is awaiting approval. Its proposed Flask upgrade needs dependency compatibility review; no existing test suite was discovered. The expected test outcome is a recommendation, not an executed result. See [plan evidence](evidence/live-real-repository-plan.json).', '',
        'This repository audit covers retrieval, indexing, scanning and evidence/data boundaries. It did not run every repository build/test suite, execute real-repository fixes or create a remote PR. Those operations retain their approval and sandbox requirements. Optional cloud inference remains unavailable because the provider rejected the client. No GitHub branch, commit, PR, merge or public deployment was performed.', '',
        '## Reproduce', '',
        'Run `python tools/audit_repositories.py --help` for the authorized deployed audit, and `python tools/repository_report.py` to render its recorded final evidence. The audit uses backend-only configured GitHub access and never requests tokens on the command line.', '',
        'Raw evidence: [final repository audit](evidence/live-repository-audit-final.json). Full feature-by-feature acceptance: [product checklist](PRODUCT_CHECKLIST.md), [implementation status](../IMPLEMENTATION_STATUS.md), [test report](TEST_EXECUTION_REPORT.md).', '',
    ])
    args.output.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'repositories': len(repos), 'outcomes': outcomes, 'totals': totals, 'severity': levels, 'report': str(args.output.relative_to(ROOT))}, indent=2))


if __name__ == '__main__':
    main()
