# Patch quality

Quality evidence includes immutable baseline SHA, approved plan/hashes, checkpoint history, changed files, unified diff, actual command exit/logs and independent scanner results. Files outside approved scope, new findings or failed commands fail the gate. A model's success claim is ignored.

Independent verification enumerates the workspace tree, compares baseline and updated hashes, and retrieves actual file contents for delivery. The original finding is compared by advisory/rule plus component/location as well as fingerprint so moving a line alone cannot certify resolution. Source and dependency changes retain residual findings in reports.

Compatibility is tested only to the extent of recorded project build/test commands. Missing suites, unsupported frameworks and unavailable dependency installation are limitations. Maintainability and the conceptual root cause still require human plan/diff review; a passing test suite is not an automated semantic proof. The model cannot claim its own patch is verified.
