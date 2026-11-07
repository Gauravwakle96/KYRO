# Agent reliability

One agent, structured schemas and an explicit state graph implement analyzing/planning/validation/approval/execution/testing/verification outcomes. A model may propose only existing context files and approved build/test argument arrays. Repository content and model output are untrusted; system instructions and mechanical boundaries reject secret/CI/path/command expansion.

Plans bind repository SHA and file hashes. Patch replacements include a current before_hash; stale files fail. At most six files of 80 KB each can change. Maximum four steps, per-request output limit, task token budget, command timeout and overall job timeout are operator-configured. Successful provider token counts are recorded; absent counts remain null. Failed provider requests are logged without prompt/keys.

Each patch step persists a checkpoint, actual modifications, diff, executed commands and diagnostics. Failed tests may trigger a model revision within the same approved files. Interrupted agent/edit/verification/write jobs require explicit review and retry; recovery never certifies a prior patch. Safe retrieval/indexing/scan/enrichment jobs have separate bounded automatic recovery, described in [AUTOMATIC_RECOVERY.md](AUTOMATIC_RECOVERY.md). Retrying execution begins from the immutable original snapshot; checkpoint replay is manual evidence inspection, not arbitrary command replay.

Prompt instructions alone are not a security boundary. Filesystem containment, allowlisted commands, no credentials in execution containers, bounded resources and approval hashes remain mandatory even if the model follows malicious repository instructions. No automatic model fallback, merge or deployment occurs.

Validated replacements are applied inside Docker with fixed trusted Python code, isolated interpreter startup, a read-only patch input and hash checks. The model cannot select the patch application executable. Dynamic-evaluation fixes reject retained execution builtins before file modification. Unchanged checkpoints are rejected rather than presented as new fixes. Invalid proposals are recorded and retried within the step ceiling. Existing tests remain contextual data; their behavior is checked by the recorded independent commands and separate controlled security regression harness.

Actual small-model runs include both successes and bounded failures. A passing scanner result with broken arithmetic tests was rejected. No general task-completion rate is claimed from this fixture.
