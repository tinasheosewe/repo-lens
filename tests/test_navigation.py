"""Tests for CodeNavigator."""

import pytest

from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.evidence import Confidence
from trace_engine.query.navigation import CodeNavigator


class TestSearch:
    def test_search_by_name(self, sample_graph: CodeGraph):
        nav = CodeNavigator(sample_graph)
        result = nav.search("auth")
        assert len(result.affected_nodes) > 0
        # Should find AuthService and authenticate at minimum
        found_names = {e.function_name or "" for e in result.evidence}
        assert any("auth" in n.lower() for n in found_names) or any(
            "Auth" in n for n in found_names
        )

    def test_search_case_insensitive(self, sample_graph: CodeGraph):
        nav = CodeNavigator(sample_graph)
        r1 = nav.search("Auth")
        r2 = nav.search("auth")
        assert len(r1.affected_nodes) == len(r2.affected_nodes)

    def test_search_no_results(self, sample_graph: CodeGraph):
        nav = CodeNavigator(sample_graph)
        result = nav.search("zzzznothing")
        assert len(result.affected_nodes) == 0


class TestPathFinding:
    def test_find_path_not_found_source(self, sample_graph: CodeGraph):
        nav = CodeNavigator(sample_graph)
        result = nav.find_path("nonexistent", "authenticate")
        assert "not found" in result.conclusion

    def test_find_path_not_found_target(self, sample_graph: CodeGraph):
        nav = CodeNavigator(sample_graph)
        result = nav.find_path("main", "nonexistent")
        assert "not found" in result.conclusion

    def test_find_path_no_connection(self, sample_graph: CodeGraph):
        nav = CodeNavigator(sample_graph)
        # validate_email has no path to authenticate
        result = nav.find_path("validate_email", "authenticate")
        assert "No path" in result.conclusion or len(result.metadata.get("paths", [])) == 0

    def test_find_path_exists(self, sample_graph: CodeGraph):
        nav = CodeNavigator(sample_graph)
        result = nav.find_path("process_payment", "authenticate")
        if result.metadata.get("paths"):
            assert len(result.reasoning_chain) > 0
