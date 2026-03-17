from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from trace_engine.api import server


def test_ingest_accepts_json_body(tmp_path: Path):
    source_dir = tmp_path / "repo"
    source_dir.mkdir()
    (source_dir / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")

    server._trace = None
    app = server.create_app()
    client = TestClient(app)

    response = client.post("/api/ingest", json={"source": str(source_dir)})

    assert response.status_code == 200
    data = response.json()
    assert data["loaded"] is True
    assert data["repo_source"] == str(source_dir)
    assert data["repo_source_type"] == "local"