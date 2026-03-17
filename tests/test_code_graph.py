"""Tests for CodeGraph (NetworkX wrapper)."""

import pytest

from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.graph import EdgeType, GraphEdge, GraphNode, NodeType


def _node(id: str, name: str, ntype: NodeType = NodeType.FUNCTION) -> GraphNode:
    return GraphNode(
        id=id, name=name, node_type=ntype,
        file_path=id.split("::")[0] if "::" in id else id,
        line_start=1, line_end=1,
    )


def _edge(src: str, tgt: str, etype: EdgeType = EdgeType.CALLS) -> GraphEdge:
    return GraphEdge(source_id=src, target_id=tgt, edge_type=etype)


@pytest.fixture
def graph() -> CodeGraph:
    """
    A ──calls──► B ──calls──► C
    A ──imports─► D
    """
    g = CodeGraph()
    for n in [
        _node("a.py::A", "A"), _node("b.py::B", "B"),
        _node("c.py::C", "C"), _node("d.py", "d.py", NodeType.FILE),
    ]:
        g.add_node(n)
    g.add_edge(_edge("a.py::A", "b.py::B", EdgeType.CALLS))
    g.add_edge(_edge("b.py::B", "c.py::C", EdgeType.CALLS))
    g.add_edge(_edge("a.py::A", "d.py", EdgeType.IMPORTS))
    return g


class TestNodeOperations:
    def test_add_and_get(self, graph: CodeGraph):
        assert graph.get_node("a.py::A") is not None
        assert graph.get_node("nonexistent") is None

    def test_has_node(self, graph: CodeGraph):
        assert graph.has_node("a.py::A")
        assert not graph.has_node("z.py::Z")

    def test_node_count(self, graph: CodeGraph):
        assert graph.node_count == 4

    def test_get_nodes_by_type(self, graph: CodeGraph):
        funcs = graph.get_nodes_by_type(NodeType.FUNCTION)
        assert len(funcs) == 3

    def test_find_nodes(self, graph: CodeGraph):
        results = graph.find_nodes("B")
        assert len(results) == 1
        assert results[0].id == "b.py::B"

    def test_find_nodes_with_type(self, graph: CodeGraph):
        assert len(graph.find_nodes("B", NodeType.FILE)) == 0


class TestEdgeOperations:
    def test_edge_count(self, graph: CodeGraph):
        assert graph.edge_count == 3

    def test_edges_property(self, graph: CodeGraph):
        assert len(graph.edges) == 3

    def test_get_edges_from(self, graph: CodeGraph):
        edges = graph.get_edges_from("a.py::A")
        assert len(edges) == 2

    def test_get_edges_from_filtered(self, graph: CodeGraph):
        edges = graph.get_edges_from("a.py::A", {EdgeType.CALLS})
        assert len(edges) == 1
        assert edges[0].target_id == "b.py::B"

    def test_get_edges_to(self, graph: CodeGraph):
        edges = graph.get_edges_to("b.py::B")
        assert len(edges) == 1
        assert edges[0].source_id == "a.py::A"

    def test_get_edges_to_nonexistent(self, graph: CodeGraph):
        assert graph.get_edges_to("nope") == []


class TestTraversal:
    def test_get_dependents(self, graph: CodeGraph):
        deps = graph.get_dependents("b.py::B")
        assert len(deps) == 1
        assert deps[0].id == "a.py::A"

    def test_get_dependencies(self, graph: CodeGraph):
        deps = graph.get_dependencies("a.py::A")
        assert len(deps) == 2

    def test_transitive_dependents(self, graph: CodeGraph):
        trans = graph.get_transitive_dependents("c.py::C")
        ids = {n.id for n in trans}
        assert "b.py::B" in ids
        assert "a.py::A" in ids

    def test_transitive_dependencies(self, graph: CodeGraph):
        trans = graph.get_transitive_dependencies("a.py::A")
        ids = {n.id for n in trans}
        assert "b.py::B" in ids
        assert "c.py::C" in ids

    def test_get_all_paths(self, graph: CodeGraph):
        paths = graph.get_all_paths("a.py::A", "c.py::C")
        assert len(paths) == 1
        assert paths[0] == ["a.py::A", "b.py::B", "c.py::C"]

    def test_no_path(self, graph: CodeGraph):
        assert graph.get_all_paths("c.py::C", "a.py::A") == []

    def test_find_cycles_none(self, graph: CodeGraph):
        assert graph.find_cycles() == []

    def test_find_cycles_present(self):
        g = CodeGraph()
        g.add_node(_node("x.py::X", "X"))
        g.add_node(_node("y.py::Y", "Y"))
        g.add_edge(_edge("x.py::X", "y.py::Y"))
        g.add_edge(_edge("y.py::Y", "x.py::X"))
        cycles = g.find_cycles()
        assert len(cycles) >= 1


class TestStats:
    def test_fan_in(self, graph: CodeGraph):
        assert graph.fan_in("b.py::B") == 1
        assert graph.fan_in("c.py::C") == 1

    def test_fan_out(self, graph: CodeGraph):
        assert graph.fan_out("a.py::A") == 2

    def test_fan_nonexistent(self, graph: CodeGraph):
        assert graph.fan_in("nope") == 0
        assert graph.fan_out("nope") == 0


class TestSerialization:
    def test_roundtrip(self, graph: CodeGraph):
        data = graph.to_dict()
        restored = CodeGraph.from_dict(data)
        assert restored.node_count == graph.node_count
        assert restored.edge_count == graph.edge_count
        assert restored.get_node("a.py::A") is not None

    def test_empty_graph(self):
        g = CodeGraph()
        data = g.to_dict()
        restored = CodeGraph.from_dict(data)
        assert restored.node_count == 0
        assert restored.edge_count == 0
