# Reachability analysis

Categories are evidence labels, not exploitability verdicts:

- CONFIRMED_REFERENCE: a scanner identifies a source location referencing a potentially vulnerable operation.
- POTENTIAL_REACHABILITY: imports plus calls to a vulnerable package alias are recorded; advisory-level vulnerable-function identity is still unknown.
- INFERRED_REACHABILITY: a dependency import exists without a confirmed matching call.
- NO_REFERENCE_FOUND: supported static index has no matching import/call.
- UNKNOWN: no supported location or package evidence.

Every match records file, line, operation kind and scanner/import evidence. Dependency declarations are recorded separately. Installed versions and affected ranges are scanner/advisory data, not guesses from import names.

Python aliases are handled; JS package imports are recognized. Reflection, dynamic imports, aliases beyond local AST facts, dependency injection and transitive calls can be missed. An import does not establish a vulnerable function call. No-reference findings retain their severity and do not certify safety. More complete function-level advisory mappings and dataflow are planned and not claimed as implemented.
