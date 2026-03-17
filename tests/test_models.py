"""Tests for Pydantic models (GraphNode, GraphEdge, Evidence, QueryResult)."""

from trace_engine.models.graph import EdgeType, GraphEdge, GraphNode, NodeType
from trace_engine.models.evidence import Confidence, Evidence, QueryResult, ReasoningStep


class TestGraphNode:
    def test_creation(self):
        node = GraphNode(
            id="src/main.py::main",
            name="main",
            node_type=NodeType.FUNCTION,
            file_path="src/main.py",
            line_start=1,
            line_end=5,
        )
        assert node.id == "src/main.py::main"
        assert node.node_type == NodeType.FUNCTION
        assert node.metadata == {}

    def test_metadata(self):
        node = GraphNode(
            id="a.py::Foo",
            name="Foo",
            node_type=NodeType.CLASS,
            file_path="a.py",
            line_start=1,
            line_end=10,
            metadata={"decorators": ["dataclass"]},
        )
        assert node.metadata["decorators"] == ["dataclass"]

    def test_serialization_roundtrip(self):
        node = GraphNode(
            id="x.py::bar",
            name="bar",
            node_type=NodeType.METHOD,
            file_path="x.py",
            line_start=3,
            line_end=7,
        )
        data = node.model_dump()
        restored = GraphNode.model_validate(data)
        assert restored == node


class TestGraphEdge:
    def test_creation(self):
        edge = GraphEdge(
            source_id="a.py::foo",
            target_id="b.py::bar",
            edge_type=EdgeType.CALLS,
        )
        assert edge.edge_type == EdgeType.CALLS
        assert edge.metadata == {}

    def test_serialization_roundtrip(self):
        edge = GraphEdge(
            source_id="a",
            target_id="b",
            edge_type=EdgeType.IMPORTS,
            metadata={"line": 3},
        )
        assert GraphEdge.model_validate(edge.model_dump()) == edge


class TestEvidence:
    def test_creation(self):
        ev = Evidence(
            file_path="a.py",
            function_name="foo",
            line_start=10,
            description="test evidence",
        )
        assert ev.file_path == "a.py"


class TestQueryResult:
    def test_minimal(self):
        qr = QueryResult(
            conclusion="Nothing found.",
            confidence=Confidence.HIGH,
        )
        assert qr.evidence == []
        assert qr.reasoning_chain == []
        assert qr.affected_nodes == []

    def test_full(self):
        ev = Evidence(file_path="a.py", description="something")
        step = ReasoningStep(step=1, description="checked graph", evidence=ev)
        qr = QueryResult(
            conclusion="Found 1 issue.",
            evidence=[ev],
            reasoning_chain=[step],
            confidence=Confidence.MEDIUM,
            affected_nodes=["a.py::foo"],
        )
        assert len(qr.evidence) == 1
        assert qr.reasoning_chain[0].evidence is not None
