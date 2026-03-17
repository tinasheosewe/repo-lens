"""Tests for RepoLoader."""

from pathlib import Path

import pytest

from trace_engine.ingestion.loader import RepoLoader

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample_project"


@pytest.fixture
def loader():
    return RepoLoader()


class TestLoad:
    def test_loads_python_files(self, loader: RepoLoader):
        files = loader.load(FIXTURES_DIR)
        assert len(files) > 0
        assert all(f.endswith(".py") for f in files)

    def test_relative_paths(self, loader: RepoLoader):
        files = loader.load(FIXTURES_DIR)
        assert "main.py" in files
        assert "services/auth.py" in files
        assert "api/routes.py" in files

    def test_content_readable(self, loader: RepoLoader):
        files = loader.load(FIXTURES_DIR)
        assert "def main" in files["main.py"]

    def test_nonexistent_path(self, loader: RepoLoader):
        with pytest.raises(FileNotFoundError):
            loader.load(Path("/nonexistent/path/definitely"))

    def test_ignores_pycache(self, loader: RepoLoader, tmp_path: Path):
        (tmp_path / "good.py").write_text("x = 1")
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "bad.pyc").write_text("nope")
        files = loader.load(tmp_path)
        assert "good.py" in files
        assert not any("__pycache__" in k for k in files)
