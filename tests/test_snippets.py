from __future__ import annotations

from pathlib import Path

from trace_engine.models.code_graph import CodeGraph
from trace_engine.query.snippets import QuerySnippetResolver


def _repo_with_neighbour(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("not part of the repository\n", encoding="utf-8")
    return repo


def test_reads_snippet_inside_repository(tmp_path: Path):
    repo = _repo_with_neighbour(tmp_path)
    resolver = QuerySnippetResolver(CodeGraph(), repo_root=repo)

    assert resolver.for_location("app.py", 1, 2) == "def main():\n    return 1"


def test_refuses_paths_outside_repository(tmp_path: Path):
    repo = _repo_with_neighbour(tmp_path)
    resolver = QuerySnippetResolver(CodeGraph(), repo_root=repo)

    assert resolver.for_location("../outside.txt", 1, 5) is None
    assert resolver.for_location(str(tmp_path / "outside.txt"), 1, 5) is None


def test_refuses_symlink_that_leaves_repository(tmp_path: Path):
    repo = _repo_with_neighbour(tmp_path)
    (repo / "link.py").symlink_to(tmp_path / "outside.txt")
    resolver = QuerySnippetResolver(CodeGraph(), repo_root=repo)

    assert resolver.for_location("link.py", 1, 5) is None
