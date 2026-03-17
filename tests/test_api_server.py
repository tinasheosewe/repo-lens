from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from trace_engine.api import server


def _git(*args: str, cwd: Path) -> None:
    import subprocess

    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)


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


def test_repo_support_reports_detected_languages(tmp_path: Path):
    source_dir = tmp_path / "repo"
    source_dir.mkdir()
    (source_dir / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")

    server._trace = None
    app = server.create_app()
    client = TestClient(app)

    response = client.get("/api/repo-support", params={"source": str(source_dir)})

    assert response.status_code == 200
    data = response.json()
    assert data["supported"] is False
    assert data["detected_languages"] == ["Python"]
    assert data["active_extensions"] == [".py"]


def test_onboarding_endpoint_returns_summary(tmp_path: Path):
    source_dir = tmp_path / "repo"
    source_dir.mkdir()
    (source_dir / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")

    server._trace = None
    app = server.create_app()
    client = TestClient(app)

    ingest_response = client.post("/api/ingest", json={"source": str(source_dir)})
    assert ingest_response.status_code == 200

    response = client.get("/api/onboarding")

    assert response.status_code == 200
    data = response.json()
    assert "repo" not in data["conclusion"].lower() or data["conclusion"]


def test_ask_endpoint_returns_config_message_without_llm(tmp_path: Path, monkeypatch):
    source_dir = tmp_path / "repo"
    source_dir.mkdir()
    (source_dir / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    monkeypatch.delenv("TRACE_LLM_API_KEY", raising=False)

    server._trace = None
    app = server.create_app()
    client = TestClient(app)

    ingest_response = client.post("/api/ingest", json={"source": str(source_dir)})
    assert ingest_response.status_code == 200

    response = client.post("/api/ask", json={"question": "What is the entry point?"})

    assert response.status_code == 200
    data = response.json()
    assert "not configured" in data["conclusion"].lower()


def test_repo_refs_endpoint_returns_branch_and_commit_options(tmp_path: Path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")

    _git("init", cwd=worktree)
    _git("config", "user.name", "Trace Test", cwd=worktree)
    _git("config", "user.email", "trace@example.com", cwd=worktree)
    _git("add", "app.py", cwd=worktree)
    _git("commit", "-m", "initial", cwd=worktree)
    _git("branch", "-M", "main", cwd=worktree)
    _git("checkout", "-b", "feature/review", cwd=worktree)
    (worktree / "app.py").write_text("def main():\n    return 2\n", encoding="utf-8")
    _git("commit", "-am", "feature", cwd=worktree)

    bare = tmp_path / "remote.git"
    _git("clone", "--bare", str(worktree), str(bare), cwd=tmp_path)

    server._trace = None
    app = server.create_app()
    client = TestClient(app)

    ingest_response = client.post("/api/ingest", json={"source": bare.as_uri(), "ref": "feature/review"})
    assert ingest_response.status_code == 200

    response = client.get("/api/repo-refs")

    assert response.status_code == 200
    data = response.json()
    assert any(option["value"] == "feature/review" for option in data["branches"])
    assert data["commits"]