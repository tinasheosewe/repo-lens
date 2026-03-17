"""Tests for RepoLoader."""

from pathlib import Path

import pytest

from trace_engine.analysis.base_parser import BaseParser, ParseResult
from trace_engine.analysis.python_parser import PythonParser
from trace_engine.ingestion.loader import RepoLoader

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample_project"


@pytest.fixture
def loader():
    return RepoLoader(parsers=[PythonParser()])


class DummyTsParser(BaseParser):
    def language_name(self) -> str:
        return "TypeScript"

    def parse_file(self, file_path: str, content: str) -> ParseResult:
        return ParseResult(file_path=file_path)

    def supported_extensions(self) -> set[str]:
        return {".ts"}

    def repository_markers(self) -> set[str]:
        return {"package.json", "tsconfig.json"}

    def classify_file(self, file_path: str, content: str | None = None) -> str | None:
        return None


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

    def test_loads_files_for_configured_parser_extensions(self, tmp_path: Path):
        (tmp_path / "index.ts").write_text("export const value = 1;", encoding="utf-8")
        loader = RepoLoader(parsers=[DummyTsParser()])

        files = loader.load(tmp_path)

        assert "index.ts" in files


class TestInspect:
    def test_supported_repo_detected(self, loader: RepoLoader):
        inspection = loader.inspect(FIXTURES_DIR)
        assert inspection.supported is True
        assert inspection.supported_file_count > 0
        assert ".py" in inspection.detected_extensions
        assert inspection.detected_languages == ["Python"]
        assert ".py" in inspection.active_extensions

    def test_unsupported_repo_rejected(self, loader: RepoLoader, tmp_path: Path):
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "index.ts").write_text("export const x = 1;")

        inspection = loader.inspect(tmp_path)

        assert inspection.supported is False
        assert inspection.supported_file_count == 0
        assert ".ts" in inspection.detected_extensions
        assert inspection.detected_languages == []
        assert "supported language" in inspection.reason

    def test_supported_language_reported_from_configured_parsers(self, tmp_path: Path):
        (tmp_path / "index.ts").write_text("export const x = 1;", encoding="utf-8")
        loader = RepoLoader(parsers=[DummyTsParser()])

        inspection = loader.inspect(tmp_path)

        assert inspection.supported is True
        assert "TypeScript" in inspection.reason

    def test_project_markers_activate_parser_detection(self, tmp_path: Path):
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        loader = RepoLoader(parsers=[DummyTsParser()])

        inspection = loader.inspect(tmp_path)

        assert inspection.supported is False
        assert inspection.detected_languages == ["TypeScript"]
        assert ".ts" in inspection.active_extensions
        assert "project markers" in inspection.reason
