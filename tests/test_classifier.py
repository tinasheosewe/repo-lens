"""Tests for the FileClassifier."""

import pytest

from trace_engine.analysis.css_parser import CssParser
from trace_engine.analysis.ecmascript_parser import JavaScriptParser, TypeScriptParser
from trace_engine.analysis.html_parser import HtmlParser
from trace_engine.analysis.python_parser import PythonParser
from trace_engine.ingestion.classifier import FileCategory, FileClassifier


@pytest.fixture
def cls():
    return FileClassifier(parsers=[PythonParser()])


@pytest.fixture
def web_cls() -> FileClassifier:
    return FileClassifier(
        parsers=[
            PythonParser(),
            JavaScriptParser(),
            TypeScriptParser(),
            HtmlParser(),
            CssParser(),
        ]
    )


class TestSourceFiles:
    def test_python_file(self, cls: FileClassifier):
        assert cls.classify("src/main.py") == FileCategory.SOURCE

    def test_nested_python_file(self, cls: FileClassifier):
        assert cls.classify("services/auth/handler.py") == FileCategory.SOURCE


class TestTestFiles:
    def test_test_prefix(self, cls: FileClassifier):
        assert cls.classify("tests/test_auth.py") == FileCategory.TEST

    def test_test_directory(self, cls: FileClassifier):
        assert cls.classify("tests/unit/helpers.py") == FileCategory.TEST

    def test_conftest(self, cls: FileClassifier):
        assert cls.classify("tests/conftest.py") == FileCategory.TEST

    def test_pytest_content_without_test_path(self, cls: FileClassifier):
        content = "import pytest\n\ndef test_login():\n    assert True\n"
        assert cls.classify("checks/login_spec.py", content=content) == FileCategory.TEST


class TestConfigFiles:
    def test_config_py(self, cls: FileClassifier):
        assert cls.classify("config.py") == FileCategory.CONFIG

    def test_pyproject_toml(self, cls: FileClassifier):
        assert cls.classify("pyproject.toml") == FileCategory.CONFIG

    def test_yaml(self, cls: FileClassifier):
        assert cls.classify("settings.yaml") == FileCategory.CONFIG

    def test_config_directory(self, cls: FileClassifier):
        assert cls.classify("configs/runtime/feature_flags") == FileCategory.CONFIG


class TestInfraFiles:
    def test_dockerfile(self, cls: FileClassifier):
        assert cls.classify("Dockerfile") == FileCategory.INFRASTRUCTURE

    def test_github_actions(self, cls: FileClassifier):
        assert cls.classify(".github/workflows/ci.yml") == FileCategory.INFRASTRUCTURE

    def test_makefile(self, cls: FileClassifier):
        assert cls.classify("Makefile") == FileCategory.INFRASTRUCTURE


class TestDocFiles:
    def test_readme(self, cls: FileClassifier):
        assert cls.classify("README.md") == FileCategory.DOCUMENTATION

    def test_rst(self, cls: FileClassifier):
        assert cls.classify("docs/guide.rst") == FileCategory.DOCUMENTATION

    def test_license_without_extension(self, cls: FileClassifier):
        assert cls.classify("LICENSE") == FileCategory.DOCUMENTATION


class TestUnknown:
    def test_binary(self, cls: FileClassifier):
        assert cls.classify("image.png") == FileCategory.UNKNOWN


class TestWebFiles:
    def test_typescript_source(self, web_cls: FileClassifier):
        assert web_cls.classify("src/app.ts") == FileCategory.SOURCE

    def test_javascript_test_file(self, web_cls: FileClassifier):
        assert web_cls.classify("src/components/button.test.js") == FileCategory.TEST

    def test_vitest_content_without_test_path(self, web_cls: FileClassifier):
        content = "import { describe, it, expect } from 'vitest'\ndescribe('x', () => it('y', () => expect(true).toBe(true)))"
        assert web_cls.classify("checks/ui.js", content=content) == FileCategory.TEST

    def test_html_source(self, web_cls: FileClassifier):
        assert web_cls.classify("web/index.html") == FileCategory.SOURCE

    def test_css_source(self, web_cls: FileClassifier):
        assert web_cls.classify("web/styles.css") == FileCategory.SOURCE
