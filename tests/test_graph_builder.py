"""Tests for GraphBuilder — cross-file resolution and full graph assembly."""

import pytest

from trace_engine.analysis.graph_builder import GraphBuilder
from trace_engine.analysis.python_parser import PythonParser
from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.graph import EdgeType, NodeType


class TestModuleMap:
    def test_build_module_map(self):
        files = {
            "main.py": "",
            "services/__init__.py": "",
            "services/auth.py": "",
        }
        mm = GraphBuilder._build_module_map(files.keys())
        assert mm["main"] == "main.py"
        assert mm["services"] == "services/__init__.py"
        assert mm["services.auth"] == "services/auth.py"

    def test_resolve_module_exact(self):
        mm = {"services.auth": "services/auth.py"}
        assert GraphBuilder._resolve_module("services.auth", mm) == "services/auth.py"

    def test_resolve_module_suffix(self):
        mm = {"myproject.services.auth": "services/auth.py"}
        result = GraphBuilder._resolve_module("services.auth", mm)
        assert result == "services/auth.py"

    def test_resolve_module_not_found(self):
        assert GraphBuilder._resolve_module("nope", {}) is None


class TestGraphBuilding:
    def test_file_nodes_created(self, sample_graph: CodeGraph):
        files = sample_graph.get_nodes_by_type(NodeType.FILE)
        paths = {f.file_path for f in files}
        assert "main.py" in paths
        assert "services/auth.py" in paths
        assert "api/routes.py" in paths

    def test_class_nodes_created(self, sample_graph: CodeGraph):
        classes = sample_graph.get_nodes_by_type(NodeType.CLASS)
        names = {c.name for c in classes}
        assert "AuthService" in names
        assert "PaymentService" in names
        assert "User" in names
        assert "Payment" in names

    def test_function_nodes_created(self, sample_graph: CodeGraph):
        funcs = sample_graph.get_nodes_by_type(NodeType.FUNCTION)
        names = {f.name for f in funcs}
        assert "main" in names
        assert "get_user" in names
        assert "create_payment" in names

    def test_method_nodes_created(self, sample_graph: CodeGraph):
        methods = sample_graph.get_nodes_by_type(NodeType.METHOD)
        names = {m.name for m in methods}
        assert "authenticate" in names
        assert "process_payment" in names

    def test_import_edges(self, sample_graph: CodeGraph):
        import_edges = [e for e in sample_graph.edges if e.edge_type == EdgeType.IMPORTS]
        # main.py imports from services/auth.py and services/payment.py
        sources = {e.source_id for e in import_edges}
        assert "main.py" in sources

    def test_defines_edges(self, sample_graph: CodeGraph):
        defines = [e for e in sample_graph.edges if e.edge_type == EdgeType.DEFINES]
        assert len(defines) > 0

    def test_file_category_metadata(self, sample_graph: CodeGraph):
        main_node = sample_graph.get_node("main.py")
        assert main_node is not None
        assert main_node.metadata.get("category") == "source"

        config_node = sample_graph.get_node("config.py")
        assert config_node is not None
        assert config_node.metadata.get("category") == "config"


class TestCrossFileCalls:
    def test_imported_function_call(self, sample_graph: CodeGraph):
        """api/routes.py calls send_receipt_email from services/email.py."""
        target_id = "services/email.py::send_receipt_email"
        edges = sample_graph.get_edges_to(target_id, {EdgeType.CALLS})
        callers = {e.source_id for e in edges}
        assert any("create_payment" in c for c in callers)

    def test_var_type_resolved_call(self, sample_graph: CodeGraph):
        """api/routes.py creates auth_service = AuthService() and calls .authenticate()."""
        target_id = "services/auth.py::AuthService.authenticate"
        edges = sample_graph.get_edges_to(target_id, {EdgeType.CALLS})
        callers = {e.source_id for e in edges}
        assert any("get_user" in c for c in callers) or any("create_payment" in c for c in callers)
