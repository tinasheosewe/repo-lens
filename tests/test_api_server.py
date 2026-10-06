from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from trace_engine.api import server


SESSION_HEADERS = {server.TRACE_SESSION_HEADER: "test-session"}


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

    app = server.create_app()
    client = TestClient(app)

    response = client.post("/api/ingest", json={"source": str(source_dir)}, headers=SESSION_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["loaded"] is True
    assert data["repo_source"] == str(source_dir)
    assert data["repo_source_type"] == "local"


def test_repo_support_reports_detected_languages(tmp_path: Path):
    source_dir = tmp_path / "repo"
    source_dir.mkdir()
    (source_dir / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")

    app = server.create_app()
    client = TestClient(app)

    response = client.get("/api/repo-support", params={"source": str(source_dir)})

    assert response.status_code == 200
    data = response.json()
    assert data["supported"] is False
    assert data["detected_languages"] == ["Python"]
    assert data["active_extensions"] == [".py"]


def test_health_endpoint_does_not_require_session_header():
    app = server.create_app()
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_cors_allows_only_the_dev_frontend_by_default(monkeypatch):
    monkeypatch.delenv("TRACE_CORS_ORIGINS", raising=False)
    app = server.create_app()
    client = TestClient(app)

    allowed = client.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"})
    other = client.get("/api/health", headers={"Origin": "https://example.org"})

    assert allowed.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    assert "access-control-allow-origin" not in other.headers


def test_cors_origins_can_be_configured(monkeypatch):
    monkeypatch.setenv("TRACE_CORS_ORIGINS", "https://trace.example.org, https://other.example.org")
    app = server.create_app()
    client = TestClient(app)

    response = client.get("/api/health", headers={"Origin": "https://other.example.org"})

    assert response.headers.get("access-control-allow-origin") == "https://other.example.org"


def test_frontend_files_are_served_from_dist_only(tmp_path: Path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("export {};", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("not part of the front end", encoding="utf-8")
    index = (dist / "index.html").resolve()

    assert server._resolve_frontend_file(dist, "assets/app.js") == (dist / "assets" / "app.js").resolve()
    assert server._resolve_frontend_file(dist, "some/client/route") == index
    assert server._resolve_frontend_file(dist, "../outside.txt") == index
    assert server._resolve_frontend_file(dist, str(outside)) == index


def test_create_app_preloads_repo_from_trace_repo_path_env(tmp_path: Path, monkeypatch):
    source_dir = tmp_path / "repo"
    source_dir.mkdir()
    (source_dir / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")

    monkeypatch.setenv("TRACE_REPO_PATH", str(source_dir))
    app = server.create_app()
    client = TestClient(app)

    response = client.get("/api/status", headers=SESSION_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["loaded"] is True
    assert data["repo_source"] == str(source_dir)
    assert data["repo_source_type"] == "local"


def test_create_app_defaults_to_public_flasky_repo(monkeypatch):
    monkeypatch.delenv("TRACE_REPO_PATH", raising=False)

    assert server._startup_repo_source(None) == server.DEFAULT_STARTUP_REPO_SOURCE


def test_status_reports_display_source_for_dot_git_repo(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")

    _git("init", cwd=repo)
    _git("config", "user.name", "Trace Test", cwd=repo)
    _git("config", "user.email", "trace@example.com", cwd=repo)
    _git("add", "app.py", cwd=repo)
    _git("commit", "-m", "initial", cwd=repo)

    bare = tmp_path / "origin.git"
    _git("clone", "--bare", str(repo), str(bare), cwd=tmp_path)
    _git("remote", "add", "origin", bare.as_uri(), cwd=repo)

    monkeypatch.chdir(repo)
    app = server.create_app()
    client = TestClient(app)

    ingest_response = client.post("/api/ingest", json={"source": "."}, headers=SESSION_HEADERS)
    assert ingest_response.status_code == 200

    response = client.get("/api/status", headers=SESSION_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["repo_source"] == "."
    assert data["repo_display_source"] == bare.as_uri()


def test_onboarding_endpoint_returns_summary(tmp_path: Path):
    source_dir = tmp_path / "repo"
    source_dir.mkdir()
    (source_dir / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")

    app = server.create_app()
    client = TestClient(app)

    ingest_response = client.post("/api/ingest", json={"source": str(source_dir)}, headers=SESSION_HEADERS)
    assert ingest_response.status_code == 200

    response = client.get("/api/onboarding", headers=SESSION_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert "repo" not in data["conclusion"].lower() or data["conclusion"]


def test_ask_endpoint_returns_config_message_without_llm(tmp_path: Path, monkeypatch):
    source_dir = tmp_path / "repo"
    source_dir.mkdir()
    (source_dir / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    monkeypatch.delenv("TRACE_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    app = server.create_app()
    client = TestClient(app)

    ingest_response = client.post("/api/ingest", json={"source": str(source_dir)}, headers=SESSION_HEADERS)
    assert ingest_response.status_code == 200

    response = client.post("/api/ask", json={"question": "What is the entry point?"}, headers=SESSION_HEADERS)

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

    app = server.create_app()
    client = TestClient(app)

    ingest_response = client.post(
        "/api/ingest",
        json={"source": bare.as_uri(), "ref": "feature/review"},
        headers=SESSION_HEADERS,
    )
    assert ingest_response.status_code == 200

    response = client.get("/api/repo-refs", headers=SESSION_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert any(option["value"] == "feature/review" for option in data["branches"])
    assert data["commits"]


def test_sessions_do_not_override_each_other(tmp_path: Path):
    repo_one = tmp_path / "repo-one"
    repo_one.mkdir()
    (repo_one / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")

    repo_two = tmp_path / "repo-two"
    repo_two.mkdir()
    (repo_two / "worker.py").write_text("def run():\n    return 2\n", encoding="utf-8")

    app = server.create_app()
    client = TestClient(app)

    session_one = {server.TRACE_SESSION_HEADER: "session-one"}
    session_two = {server.TRACE_SESSION_HEADER: "session-two"}

    response_one = client.post("/api/ingest", json={"source": str(repo_one)}, headers=session_one)
    response_two = client.post("/api/ingest", json={"source": str(repo_two)}, headers=session_two)

    assert response_one.status_code == 200
    assert response_two.status_code == 200

    status_one = client.get("/api/status", headers=session_one)
    status_two = client.get("/api/status", headers=session_two)

    assert status_one.status_code == 200
    assert status_two.status_code == 200
    assert status_one.json()["repo_source"] == str(repo_one)
    assert status_two.json()["repo_source"] == str(repo_two)


def test_expired_session_is_evicted(tmp_path: Path, monkeypatch):
    source_dir = tmp_path / "repo"
    source_dir.mkdir()
    (source_dir / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")

    now = 1_000.0
    monkeypatch.setenv("TRACE_SESSION_TTL_SECONDS", "5")
    monkeypatch.setattr(server, "_current_time", lambda: now)

    app = server.create_app()
    app.state.startup_repo_source = None
    client = TestClient(app)

    ingest_response = client.post("/api/ingest", json={"source": str(source_dir)}, headers=SESSION_HEADERS)
    assert ingest_response.status_code == 200

    now = 1_007.0
    response = client.get("/api/status", headers=SESSION_HEADERS)

    assert response.status_code == 200
    assert response.json()["loaded"] is False


def test_expired_remote_session_removes_cached_checkout(tmp_path: Path, monkeypatch):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")

    _git("init", cwd=worktree)
    _git("config", "user.name", "Trace Test", cwd=worktree)
    _git("config", "user.email", "trace@example.com", cwd=worktree)
    _git("add", "app.py", cwd=worktree)
    _git("commit", "-m", "initial", cwd=worktree)

    bare = tmp_path / "remote.git"
    _git("clone", "--bare", str(worktree), str(bare), cwd=tmp_path)

    now = 2_000.0
    monkeypatch.setenv("TRACE_SESSION_TTL_SECONDS", "5")
    monkeypatch.setattr(server, "_current_time", lambda: now)

    app = server.create_app()
    app.state.startup_repo_source = None
    client = TestClient(app)
    remote_headers = {server.TRACE_SESSION_HEADER: "expiring-session"}

    ingest_response = client.post("/api/ingest", json={"source": bare.as_uri()}, headers=remote_headers)
    assert ingest_response.status_code == 200

    cached_path = Path(ingest_response.json()["repo_path"])
    assert cached_path.exists()

    now = 2_007.0
    response = client.get("/api/status", headers=remote_headers)

    assert response.status_code == 200
    assert response.json()["loaded"] is False
    assert not cached_path.exists()


def test_background_cleanup_expires_remote_session_without_request(tmp_path: Path, monkeypatch):
    worktree = tmp_path / "background-worktree"
    worktree.mkdir()
    (worktree / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")

    _git("init", cwd=worktree)
    _git("config", "user.name", "Trace Test", cwd=worktree)
    _git("config", "user.email", "trace@example.com", cwd=worktree)
    _git("add", "app.py", cwd=worktree)
    _git("commit", "-m", "initial", cwd=worktree)

    bare = tmp_path / "background-remote.git"
    _git("clone", "--bare", str(worktree), str(bare), cwd=tmp_path)

    now = 3_000.0
    monkeypatch.setenv("TRACE_SESSION_TTL_SECONDS", "1")
    monkeypatch.setenv("TRACE_SESSION_SWEEP_INTERVAL_SECONDS", "1")
    monkeypatch.setattr(server, "_current_time", lambda: now)

    app = server.create_app()
    remote_headers = {server.TRACE_SESSION_HEADER: "background-expiring-session"}

    with TestClient(app) as client:
        ingest_response = client.post("/api/ingest", json={"source": bare.as_uri()}, headers=remote_headers)
        assert ingest_response.status_code == 200

        cached_path = Path(ingest_response.json()["repo_path"])
        assert cached_path.exists()

        now = 3_005.0
        time.sleep(1.2)

        assert not app.state.trace_sessions
        assert not cached_path.exists()