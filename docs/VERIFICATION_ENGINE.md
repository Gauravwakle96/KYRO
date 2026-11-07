# Independent verification

Verification is deterministic backend code, separate from model editing. It reruns approved build/test/regression commands, scans through all three independent adapters and compares against the target's baseline scan. The agent's earlier command logs remain distinct from independent logs.

VERIFIED requires complete baseline, complete rescan, original finding absent, no new normalized findings, in-scope modification, successful build and a known existing suite with a passing test/regression command. PARTIALLY_VERIFIED marks absence with missing build/tests or partial scanner coverage. FAILED marks failed tests, new findings, scope violations or the original issue remaining. INCONCLUSIVE marks unusable baseline/rescan.

Reports include root cause, original finding/provenance, actual changed files/diff, command stdout/stderr/exit/duration, before/after fingerprints, introduced/remaining findings, patch quality, timestamps and limitations. The browser can download JSON. Delivery checks recorded verified file hashes and the live GitHub base SHA. Scanner disappearance alone, missing tests and the remediation model's opinion cannot satisfy verification.

Runtime exploits, exhaustive semantic equivalence, deployed service behavior and full interprocedural dataflow remain outside this release's verification guarantee.
