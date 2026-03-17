"""Tests for QueryEngine (dependents, usages, endpoints)."""

import pytest

from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.evidence import Confidence
from trace_engine.query.engine import QueryEngine


class TestFindDependents:
    def test_find_dependents_known(self, sample_graph: CodeGraph):
        engine = QueryEngine(sample_graph)
        result = engine.find_dependents("authenticate")
        assert result.confidence == Confidence.HIGH
        assert len(result.affected_nodes) > 0

    def test_find_dependents_unknown(self, sample_graph: CodeGraph):
        engine = QueryEngine(sample_graph)
        result = engine.find_dependents("nonexistent_func")
        assert "found" in result.conclusion.lower()

    def test_dependents_have_evidence(self, sample_graph: CodeGraph):
        engine = QueryEngine(sample_graph)
        result = engine.find_dependents("authenticate")
        for ev in result.evidence:
            assert ev.file_path
            assert ev.description


class TestFindUsages:
    def test_find_usages_known(self, sample_graph: CodeGraph):
        engine = QueryEngine(sample_graph)
        result = engine.find_usages("authenticate")
        assert len(result.affected_nodes) > 0

    def test_find_usages_unknown(self, sample_graph: CodeGraph):
        engine = QueryEngine(sample_graph)
        result = engine.find_usages("nope")
        assert "found" in result.conclusion.lower()


class TestListEndpoints:
    def test_no_endpoints_in_sample(self, sample_graph: CodeGraph):
        """The sample project doesn't use @app.route decorators."""
        engine = QueryEngine(sample_graph)
        result = engine.list_endpoints()
        # Sample project has no decorated endpoints
        assert result.confidence == Confidence.HIGH
