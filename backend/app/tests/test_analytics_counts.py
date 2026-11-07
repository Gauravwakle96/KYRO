from app.database import Finding, Project, Remediation, Repository, ScanRun, SessionLocal


def test_repeated_verification_does_not_count_as_two_distinct_fixes(client, owner):
    with SessionLocal() as db:
        project = Project(user_id=owner["id"], name="Controlled analytics fixture")
        db.add(project)
        db.flush()
        repo = Repository(project_id=project.id, full_name="unit/fixture", branch="main")
        db.add(repo)
        db.flush()
        scan = ScanRun(repository_id=repo.id, snapshot_sha="unit")
        db.add(scan)
        db.flush()
        finding = Finding(repository_id=repo.id, scan_id=scan.id, fingerprint="unit", title="unit", severity="HIGH", data={})
        db.add(finding)
        db.flush()
        for _ in range(2):
            db.add(Remediation(finding_id=finding.id, repository_id=repo.id, verification={"status": "VERIFIED"}))
        db.commit()
    result = client.get("/api/analytics").json()
    assert result["verified_fixes"] == 1 and result["verified_runs"] == 2
