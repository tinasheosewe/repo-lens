from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from trace_engine.ingestion.source_resolver import RepoSourceResolver


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git is required for source resolver tests",
)


def _git(*args: str, cwd: Path | None = None) -> None:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)


class TestRepoSourceResolver:
    def test_resolves_local_directory(self, tmp_path: Path):
        resolver = RepoSourceResolver()
        resolved = resolver.resolve(str(tmp_path))

        assert resolved.source_type == "local"
        assert resolved.local_path == tmp_path.resolve()

    def test_clones_file_remote(self, tmp_path: Path):
        resolver = RepoSourceResolver()

        worktree = tmp_path / "worktree"
        worktree.mkdir()
        (worktree / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")

        _git("init", cwd=worktree)
        _git("config", "user.name", "Trace Test", cwd=worktree)
        _git("config", "user.email", "trace@example.com", cwd=worktree)
        _git("add", "app.py", cwd=worktree)
        _git("commit", "-m", "initial", cwd=worktree)

        bare = tmp_path / "remote.git"
        _git("clone", "--bare", str(worktree), str(bare))

        resolved = resolver.resolve(bare.as_uri())

        assert resolved.source_type == "remote"
        assert resolved.local_path.is_dir()
        assert (resolved.local_path / "app.py").is_file()

    def test_clones_specific_ref(self, tmp_path: Path):
        resolver = RepoSourceResolver()

        worktree = tmp_path / "worktree_ref"
        worktree.mkdir()
        (worktree / "app.py").write_text("def main():\n    return 'base'\n", encoding="utf-8")

        _git("init", cwd=worktree)
        _git("config", "user.name", "Trace Test", cwd=worktree)
        _git("config", "user.email", "trace@example.com", cwd=worktree)
        _git("add", "app.py", cwd=worktree)
        _git("commit", "-m", "base", cwd=worktree)
        _git("checkout", "-b", "feature/test-ref", cwd=worktree)
        (worktree / "app.py").write_text("def main():\n    return 'feature'\n", encoding="utf-8")
        _git("commit", "-am", "feature", cwd=worktree)

        bare = tmp_path / "remote_ref.git"
        _git("clone", "--bare", str(worktree), str(bare))

        resolved = resolver.resolve(bare.as_uri(), ref="feature/test-ref")

        assert resolved.ref == "feature/test-ref"
        assert "feature" in (resolved.local_path / "app.py").read_text(encoding="utf-8")

    def test_uses_origin_url_as_display_source_for_dot(self, tmp_path: Path, monkeypatch):
        resolver = RepoSourceResolver()

        worktree = tmp_path / "worktree_dot"
        worktree.mkdir()
        (worktree / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")

        _git("init", cwd=worktree)
        _git("config", "user.name", "Trace Test", cwd=worktree)
        _git("config", "user.email", "trace@example.com", cwd=worktree)
        _git("add", "app.py", cwd=worktree)
        _git("commit", "-m", "initial", cwd=worktree)

        bare = tmp_path / "display_remote.git"
        _git("clone", "--bare", str(worktree), str(bare))
        _git("remote", "add", "origin", bare.as_uri(), cwd=worktree)

        monkeypatch.chdir(worktree)
        resolved = resolver.resolve(".")

        assert resolved.source == "."
        assert resolved.display_source == bare.as_uri()

    def test_rejects_remote_checkout_over_size_limit(self, tmp_path: Path, monkeypatch):
        resolver = RepoSourceResolver()

        worktree = tmp_path / "worktree_large"
        worktree.mkdir()
        (worktree / "large.bin").write_bytes(b"x" * 128)

        _git("init", cwd=worktree)
        _git("config", "user.name", "Trace Test", cwd=worktree)
        _git("config", "user.email", "trace@example.com", cwd=worktree)
        _git("add", "large.bin", cwd=worktree)
        _git("commit", "-m", "initial", cwd=worktree)

        bare = tmp_path / "too_large.git"
        _git("clone", "--bare", str(worktree), str(bare))

        monkeypatch.setenv("TRACE_MAX_CLONE_BYTES", "32")
        with pytest.raises(RuntimeError, match="exceeds the clone size limit"):
            resolver.resolve(bare.as_uri())

    def test_lists_review_refs(self, tmp_path: Path):
        resolver = RepoSourceResolver()

        worktree = tmp_path / "worktree_refs"
        worktree.mkdir()
        (worktree / "app.py").write_text("def main():\n    return 'base'\n", encoding="utf-8")

        _git("init", cwd=worktree)
        _git("config", "user.name", "Trace Test", cwd=worktree)
        _git("config", "user.email", "trace@example.com", cwd=worktree)
        _git("add", "app.py", cwd=worktree)
        _git("commit", "-m", "base", cwd=worktree)
        _git("branch", "-M", "main", cwd=worktree)
        _git("checkout", "-b", "feature/review", cwd=worktree)
        (worktree / "app.py").write_text("def main():\n    return 'feature'\n", encoding="utf-8")
        _git("commit", "-am", "feature", cwd=worktree)

        bare = tmp_path / "remote_refs.git"
        _git("clone", "--bare", str(worktree), str(bare))

        resolved = resolver.resolve(bare.as_uri(), ref="feature/review")
        catalog = resolver.list_review_refs(resolved.local_path, current_ref="feature/review")

        branch_names = {branch.name for branch in catalog.branches}
        assert "main" in branch_names
        assert "feature/review" in branch_names
        assert catalog.commits
