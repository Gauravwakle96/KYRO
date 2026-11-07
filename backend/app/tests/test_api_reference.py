def test_docs_assets_are_local_and_csp_remains_strict(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "cdn.jsdelivr" not in response.text
    assert "swagger-ui-bundle.js" in response.text
    assert "unsafe-inline" not in response.headers["content-security-policy"]
    assert client.get("/api/docs-static/initialize.js").status_code == 200
