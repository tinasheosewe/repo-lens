"""Tests for storage (FileGraphRepository) and output (Formatter)."""

import json

import pytest

from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.evidence import Confidence, Evidence, QueryResult, ReasoningStep
from trace_engine.models.graph import EdgeType, GraphEdge, GraphNode, NodeType
from trace_engine.output.formatter import Formatter
from trace_engine.storage.repository import FileGraphRepository


class TestFileGraphRepository:
    def test_save_and_load(self, tmp_path):
        repo = FileGraphRepository(tmp_path / ".trace")
        g = CodeGraph()
        g.add_node(GraphNode(
            id="a.py", name="a.py", node_type=NodeType.FILE,
            file_path="a.py", line_start=1, line_end=10,
        ))
        g.add_node(GraphNode(
            id="a.py::foo", name="foo", node_type=NodeType.FUNCTION,
            file_path="a.py", line_start=1, line_end=3,
        ))
        g.add_edge(GraphEdge(
            source_id="a.py", target_id="a.py::foo", edge_type=EdgeType.DEFINES,
        ))

        repo.save("test_project", g)
        assert repo.exists("test_project")

        loaded = repo.load("test_project")
        assert loaded is not None
        assert loaded.node_count == 2
        assert loaded.edge_count == 1
        assert loaded.get_node("a.py::foo") is not None

    def test_load_nonexistent(self, tmp_path):
        repo = FileGraphRepository(tmp_path / ".trace")
        assert repo.load("nope") is None

    def test_exists_false(self, tmp_path):
        repo = FileGraphRepository(tmp_path / ".trace")
        assert not repo.exists("nope")

    def test_overwrite(self, tmp_path):
        repo = FileGraphRepository(tmp_path / ".trace")
        g1 = CodeGraph()
        g1.add_node(GraphNode(
            id="x.py", name="x.py", node_type=NodeType.FILE,
            file_path="x.py", line_start=1, line_end=1,
        ))
        repo.save("proj", g1)

        g2 = CodeGraph()
        g2.add_node(GraphNode(
            id="y.py", name="y.py", node_type=NodeType.FILE,
            file_path="y.py", line_start=1, line_end=1,
        ))
        g2.add_node(GraphNode(
            id="z.py", name="z.py", node_type=NodeType.FILE,
            file_path="z.py", line_start=1, line_end=1,
        ))
        repo.save("proj", g2)

        loaded = repo.load("proj")
        assert loaded is not None
        assert loaded.node_count == 2


class TestFormatter:
    def test_renders_without_error(self):
        from io import StringIO
        from rich.console import Console

        buf = StringIO()
        console = Console(file=buf, force_terminal=True)
        fmt = Formatter(console)

        result = QueryResult(
            conclusion="Found 2 issues.",
            evidence=[
                Evidence(file_path="a.py", function_name="foo", line_start=10, description="broken"),
            ],
            reasoning_chain=[
                ReasoningStep(step=1, description="Checked graph"),
            ],
            confidence=Confidence.HIGH,
            affected_nodes=["a.py::foo"],
        )
        fmt.render(result, title="Test Output")
        output = buf.getvalue()
        assert "Found" in output and "issues" in output
        assert "a.py" in output

    def test_renders_empty_result(self):
        from io import StringIO
        from rich.console import Console

        buf = StringIO()
        console = Console(file=buf, force_terminal=True)
        fmt = Formatter(console)

        result = QueryResult(conclusion="Nothing.", confidence=Confidence.LOW)
        fmt.render(result)
        assert "Nothing." in buf.getvalue()
