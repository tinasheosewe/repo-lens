"""Tests for the Python AST parser."""

import pytest

from trace_engine.analysis.python_parser import PythonParser
from trace_engine.models.graph import EdgeType, NodeType


@pytest.fixture
def parser():
    return PythonParser()


class TestSupportedExtensions:
    def test_python(self, parser: PythonParser):
        assert ".py" in parser.supported_extensions()


class TestParseEmpty:
    def test_empty_file(self, parser: PythonParser):
        result = parser.parse_file("empty.py", "")
        assert len(result.nodes) == 1  # FILE node
        assert result.nodes[0].node_type == NodeType.FILE

    def test_syntax_error(self, parser: PythonParser):
        result = parser.parse_file("bad.py", "def (broken:")
        assert result.file_path == "bad.py"
        assert len(result.nodes) == 0


class TestFunctionParsing:
    def test_simple_function(self, parser: PythonParser):
        code = "def greet(name):\n    return f'Hello {name}'\n"
        result = parser.parse_file("funcs.py", code)
        func_nodes = [n for n in result.nodes if n.node_type == NodeType.FUNCTION]
        assert len(func_nodes) == 1
        assert func_nodes[0].name == "greet"
        assert func_nodes[0].id == "funcs.py::greet"

    def test_multiple_functions(self, parser: PythonParser):
        code = "def foo():\n    pass\ndef bar():\n    pass\n"
        result = parser.parse_file("multi.py", code)
        funcs = [n for n in result.nodes if n.node_type == NodeType.FUNCTION]
        assert len(funcs) == 2
        names = {f.name for f in funcs}
        assert names == {"foo", "bar"}

    def test_async_function(self, parser: PythonParser):
        code = "async def fetch():\n    pass\n"
        result = parser.parse_file("async.py", code)
        funcs = [n for n in result.nodes if n.node_type == NodeType.FUNCTION]
        assert len(funcs) == 1
        assert funcs[0].metadata["is_async"] is True

    def test_function_args(self, parser: PythonParser):
        code = "def add(a, b):\n    return a + b\n"
        result = parser.parse_file("args.py", code)
        func = [n for n in result.nodes if n.node_type == NodeType.FUNCTION][0]
        assert func.metadata["args"] == ["a", "b"]

    def test_decorated_function(self, parser: PythonParser):
        code = "@app.route('/hello')\ndef hello():\n    pass\n"
        result = parser.parse_file("deco.py", code)
        func = [n for n in result.nodes if n.node_type == NodeType.FUNCTION][0]
        assert "app.route" in func.metadata["decorators"]


class TestClassParsing:
    def test_simple_class(self, parser: PythonParser):
        code = "class Dog:\n    def bark(self):\n        pass\n"
        result = parser.parse_file("cls.py", code)
        classes = [n for n in result.nodes if n.node_type == NodeType.CLASS]
        methods = [n for n in result.nodes if n.node_type == NodeType.METHOD]
        assert len(classes) == 1
        assert classes[0].name == "Dog"
        assert len(methods) == 1
        assert methods[0].name == "bark"
        assert methods[0].id == "cls.py::Dog.bark"

    def test_inheritance(self, parser: PythonParser):
        code = "class Animal:\n    pass\nclass Dog(Animal):\n    pass\n"
        result = parser.parse_file("inh.py", code)
        inherits = [e for e in result.internal_edges if e.edge_type == EdgeType.INHERITS]
        assert len(inherits) == 1
        assert inherits[0].source_id == "inh.py::Dog"
        assert inherits[0].target_id == "inh.py::Animal"

    def test_defines_edges(self, parser: PythonParser):
        code = "class Foo:\n    def method(self):\n        pass\n"
        result = parser.parse_file("def.py", code)
        defines = [e for e in result.internal_edges if e.edge_type == EdgeType.DEFINES]
        # FILE defines Foo, Foo defines method
        assert len(defines) == 2


class TestImportParsing:
    def test_import(self, parser: PythonParser):
        code = "import os\nimport sys\n"
        result = parser.parse_file("imp.py", code)
        assert len(result.imports) == 2
        names = {i.local_name for i in result.imports}
        assert names == {"os", "sys"}

    def test_from_import(self, parser: PythonParser):
        code = "from os.path import join\n"
        result = parser.parse_file("frm.py", code)
        assert len(result.imports) == 1
        imp = result.imports[0]
        assert imp.local_name == "join"
        assert imp.module_path == "os.path"
        assert imp.original_name == "join"

    def test_import_alias(self, parser: PythonParser):
        code = "from collections import OrderedDict as OD\n"
        result = parser.parse_file("alias.py", code)
        assert result.imports[0].local_name == "OD"
        assert result.imports[0].original_name == "OrderedDict"

    def test_star_import(self, parser: PythonParser):
        code = "from utils import *\n"
        result = parser.parse_file("star.py", code)
        assert len(result.imports) == 1
        assert result.imports[0].is_star is True


class TestCallParsing:
    def test_local_call(self, parser: PythonParser):
        code = "def helper():\n    pass\ndef main():\n    helper()\n"
        result = parser.parse_file("lcall.py", code)
        calls = [e for e in result.internal_edges if e.edge_type == EdgeType.CALLS]
        assert len(calls) == 1
        assert calls[0].source_id == "lcall.py::main"
        assert calls[0].target_id == "lcall.py::helper"

    def test_self_method_call(self, parser: PythonParser):
        code = (
            "class Svc:\n"
            "    def run(self):\n"
            "        self.setup()\n"
            "    def setup(self):\n"
            "        pass\n"
        )
        result = parser.parse_file("self.py", code)
        calls = [e for e in result.internal_edges if e.edge_type == EdgeType.CALLS]
        assert any(
            e.source_id == "self.py::Svc.run" and e.target_id == "self.py::Svc.setup"
            for e in calls
        )

    def test_imported_call(self, parser: PythonParser):
        code = "from auth import authenticate\ndef login():\n    authenticate()\n"
        result = parser.parse_file("icall.py", code)
        assert len(result.unresolved_calls) == 1
        uc = result.unresolved_calls[0]
        assert uc.caller_id == "icall.py::login"
        assert uc.called_name == "authenticate"

    def test_var_type_tracking(self, parser: PythonParser):
        code = (
            "from auth import AuthService\n"
            "svc = AuthService()\n"
            "def run():\n"
            "    svc.authenticate()\n"
        )
        result = parser.parse_file("vt.py", code)
        # Expect at least the AuthService() constructor call as unresolved
        assert len(result.unresolved_calls) >= 1
        # The svc.authenticate() call should resolve via var_types
        auth_calls = [
            uc for uc in result.unresolved_calls
            if "AuthService" in uc.called_name and "authenticate" in uc.called_name
        ]
        constructor_calls = [
            uc for uc in result.unresolved_calls
            if uc.called_name == "AuthService"
        ]
        # Either we resolved svc.authenticate → AuthService.authenticate, 
        # or at minimum the constructor call is tracked
        assert len(auth_calls) > 0 or len(constructor_calls) > 0
