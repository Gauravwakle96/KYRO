# Attack-path architecture

The initial graph uses relational repository/finding/index records and derives view nodes and edges with explicit evidence. Repository CONTAINS indexed file, repository AFFECTED_BY recorded finding, file REFERENCES finding through scanner or import/call evidence. The interactive browser view supports node selection and an accessible evidence table.

Each edge references a scan ID or file/line. The system does not infer network exposure, exploit chains or runtime attack paths. Node placement is an inspection layout, not severity or distance semantics. Function-level CALLS, remediation/test/PR edges and more complete entry-point graphs are future additions. No Neo4j deployment is required.
