"""Tests for ImpactAnalyzer."""

import pytest

from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.evidence import Confidence
from trace_engine.query.impact import ImpactAnalyzer


class TestImpactAnalysis:
    def test_nonexistent_node(self, sample_graph: CodeGraph):
        analyzer = ImpactAnalyzer(sample_graph)
        result = analyzer.analyze("nonexistent::thing")
        assert "not found" in result.conclusion

    def test_nonexistent_name(self, sample_graph: CodeGraph):
        analyzer = ImpactAnalyzer(sample_graph)
        result = analyzer.analyze_by_name("totally_fake")
        assert "found" in result.conclusion.lower()
        assert len(result.affected_nodes) == 0

    def test_authenticate_impact(self, sample_graph: CodeGraph):
        """Removing authenticate should affect several components."""
        analyzer = ImpactAnalyzer(sample_graph)
        result = analyzer.analyze_by_name("authenticate")
        assert result.confidence in {Confidence.HIGH, Confidence.MEDIUM}
        assert len(result.affected_nodes) > 0
        assert len(result.evidence) > 0
        assert len(result.reasoning_chain) >= 3

    def test_impact_has_evidence(self, sample_graph: CodeGraph):
        analyzer = ImpactAnalyzer(sample_graph)
        result = analyzer.analyze_by_name("authenticate")
        for ev in result.evidence:
            assert ev.file_path
            assert ev.description

    def test_impact_has_metadata(self, sample_graph: CodeGraph):
        analyzer = ImpactAnalyzer(sample_graph)
        result = analyzer.analyze_by_name("authenticate")
        assert "direct_count" in result.metadata
        assert "transitive_count" in result.metadata
        assert "files_affected" in result.metadata

    def test_leaf_node_impact(self, sample_graph: CodeGraph):
        """A function with no dependents should report 0 affected."""
        analyzer = ImpactAnalyzer(sample_graph)
        result = analyzer.analyze_by_name("unused_email_function")
        assert len(result.affected_nodes) == 0

    def test_impact_severity_classification(self, sample_graph: CodeGraph):
        analyzer = ImpactAnalyzer(sample_graph)
        result = analyzer.analyze_by_name("authenticate")
        # Should have CRITICAL entries for direct callers
        critical_evidence = [e for e in result.evidence if "CRITICAL" in e.description]
        assert len(critical_evidence) > 0
