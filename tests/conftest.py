from __future__ import annotations

from pathlib import Path

import pytest

from trace_engine.analysis.graph_builder import GraphBuilder
from trace_engine.analysis.python_parser import PythonParser
from trace_engine.ingestion.classifier import FileClassifier
from trace_engine.models.code_graph import CodeGraph

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample_project"


@pytest.fixture
def sample_project_files() -> dict[str, str]:
    """Load every .py file from the sample project fixture."""
    files: dict[str, str] = {}
    for py_file in sorted(FIXTURES_DIR.rglob("*.py")):
        rel = str(py_file.relative_to(FIXTURES_DIR)).replace("\\", "/")
        files[rel] = py_file.read_text(encoding="utf-8")
    return files


@pytest.fixture
def python_parser() -> PythonParser:
    return PythonParser()


@pytest.fixture
def classifier() -> FileClassifier:
    return FileClassifier()


@pytest.fixture
def graph_builder() -> GraphBuilder:
    return GraphBuilder(parsers=[PythonParser()], classifier=FileClassifier())


@pytest.fixture
def sample_graph(graph_builder: GraphBuilder, sample_project_files: dict[str, str]) -> CodeGraph:
    return graph_builder.build(sample_project_files)
