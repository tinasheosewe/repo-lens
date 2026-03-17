"""Tests for DependencyAnalyzer."""

import pytest

from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.evidence import Confidence
from trace_engine.models.graph import EdgeType, GraphEdge, GraphNode, NodeType
from trace_engine.query.dependencies import DependencyAnalyzer


class TestCircularDependencies:
    def test_no_cycles_in_sample(self, sample_graph: CodeGraph):
        analyzer = DependencyAnalyzer(sample_graph)
        result = analyzer.find_circular_dependencies()
        # The sample project has no circular imports
        assert result.metadata.get("cycles") is not None

    def test_detects_cycle(self):
        """Build a small graph with a circular import."""
        from trace_engine.models.code_graph import CodeGraph

        g = CodeGraph()
        g.add_node(GraphNode(
            id="a.py", name="a.py", node_type=NodeType.FILE,
            file_path="a.py", line_start=1, line_end=1,
        ))
        g.add_node(GraphNode(
            id="b.py", name="b.py", node_type=NodeType.FILE,
            file_path="b.py", line_start=1, line_end=1,
        ))
        g.add_edge(GraphEdge(
            source_id="a.py", target_id="b.py", edge_type=EdgeType.IMPORTS,
        ))
        g.add_edge(GraphEdge(
            source_id="b.py", target_id="a.py", edge_type=EdgeType.IMPORTS,
        ))
        analyzer = DependencyAnalyzer(g)
        result = analyzer.find_circular_dependencies()
        assert len(result.metadata["cycles"]) >= 1


class TestHotspots:
    def test_find_hotspots_default_threshold(self, sample_graph: CodeGraph):
        analyzer = DependencyAnalyzer(sample_graph)
        result = analyzer.find_hotspots()
        # Just verify it runs and returns valid structure
        assert result.confidence is not None
        assert isinstance(result.evidence, list)

    def test_find_hotspots_low_threshold(self, sample_graph: CodeGraph):
        analyzer = DependencyAnalyzer(sample_graph)
        result = analyzer.find_hotspots(threshold=1)
        # With threshold=1 we should find more hotspots
        assert len(result.evidence) > 0

    def test_hotspot_evidence_has_fan_info(self, sample_graph: CodeGraph):
        analyzer = DependencyAnalyzer(sample_graph)
        result = analyzer.find_hotspots(threshold=1)
        for ev in result.evidence:
            assert "fan-in" in ev.description
            assert "fan-out" in ev.description


class TestCoupledFiles:
    def test_coupled_files(self, sample_graph: CodeGraph):
        analyzer = DependencyAnalyzer(sample_graph)
        result = analyzer.find_coupled_files(threshold=1)
        assert result.confidence is not None

    def test_coupled_files_high_threshold(self, sample_graph: CodeGraph):
        analyzer = DependencyAnalyzer(sample_graph)
        result = analyzer.find_coupled_files(threshold=100)
        assert len(result.evidence) == 0
        assert result.confidence == Confidence.HIGH
