"""Tests for GraphBuilder — cross-file resolution and full graph assembly."""

import pytest

from trace_engine.analysis.css_parser import CssParser
from trace_engine.analysis.ecmascript_parser import JavaScriptParser, TypeScriptParser
from trace_engine.analysis.graph_builder import GraphBuilder
from trace_engine.analysis.html_parser import HtmlParser
from trace_engine.analysis.python_parser import PythonParser
from trace_engine.ingestion.classifier import FileClassifier
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


class TestWebGraphBuilding:
    def test_builds_mixed_language_graph(self):
        files = {
            "src/util.js": "export function foo() { return 1; }\n",
            "src/app.js": "import { foo } from './util';\nexport function run() { return foo(); }\n",
            "src/service.ts": "export class Api { ping() { return 1; } }\n",
            "src/index.ts": "import { Api } from './service';\nconst api = new Api();\nexport const boot = () => api.ping();\n",
            "web/index.html": "<html><head><link rel=\"stylesheet\" href=\"./styles.css\"><script src=\"./app.js\"></script></head><body><div id=\"app\" class=\"hero\"></div></body></html>",
            "web/styles.css": "@import './base.css';\n.hero { color: red; }\n",
            "web/base.css": "body { margin: 0; }\n",
            "web/app.js": "import { run } from '../src/app.js';\nrun();\n",
        }
        parsers = [PythonParser(), JavaScriptParser(), TypeScriptParser(), HtmlParser(), CssParser()]
        builder = GraphBuilder(parsers=parsers, classifier=FileClassifier(parsers=parsers))

        graph = builder.build(files)

        file_paths = {node.file_path for node in graph.get_nodes_by_type(NodeType.FILE)}
        assert "web/index.html" in file_paths
        assert "web/styles.css" in file_paths
        assert "src/app.js" in file_paths
        assert "src/index.ts" in file_paths

        html_import_targets = {
            edge.target_id
            for edge in graph.get_edges_from("web/index.html", {EdgeType.IMPORTS})
        }
        assert "web/styles.css" in html_import_targets
        assert "web/app.js" in html_import_targets

        css_import_targets = {
            edge.target_id
            for edge in graph.get_edges_from("web/styles.css", {EdgeType.IMPORTS})
        }
        assert "web/base.css" in css_import_targets

        js_callers = {edge.source_id for edge in graph.get_edges_to("src/util.js::foo", {EdgeType.CALLS})}
        assert "src/app.js::run" in js_callers

        ts_callers = {edge.source_id for edge in graph.get_edges_to("src/service.ts::Api.ping", {EdgeType.CALLS})}
        assert "src/index.ts::boot" in ts_callers
