from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import Callable

from trace_engine.analysis.base_parser import BaseParser


class FileCategory(str, Enum):
    SOURCE = "source"
    TEST = "test"
    CONFIG = "config"
    INFRASTRUCTURE = "infrastructure"
    DOCUMENTATION = "documentation"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClassificationContext:
    path: PurePosixPath
    content: str | None = None

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def suffix(self) -> str:
        return self.path.suffix

    @property
    def normalized_path(self) -> str:
        return "/".join(self.path.parts)


@dataclass(frozen=True)
class ClassificationRule:
    name: str
    category: FileCategory
    weight: int
    predicate: Callable[[ClassificationContext], bool]

    def matches(self, context: ClassificationContext) -> bool:
        return self.predicate(context)


class FileClassifier:
    """Rule-based classifier for repository files."""

    _DOC_NAMES: set[str] = {
        "readme", "changelog", "license", "copying", "contributing",
    }
    _CONFIG_DIR_NAMES: set[str] = {"config", "configs", "settings"}
    _TEST_DIR_NAMES: set[str] = {"tests", "test"}
    _TEST_CONTENT_MARKERS: tuple[str, ...] = (
        "import pytest", "from pytest", "import unittest", "from unittest",
        "def test_", "class Test",
    )
    _CATEGORY_PRIORITY: dict[FileCategory, int] = {
        FileCategory.TEST: 5,
        FileCategory.INFRASTRUCTURE: 4,
        FileCategory.CONFIG: 3,
        FileCategory.DOCUMENTATION: 2,
        FileCategory.SOURCE: 1,
        FileCategory.UNKNOWN: 0,
    }

    _CONFIG_NAMES: set[str] = {
        "config.py", "settings.py", "conf.py", ".env",
        "setup.py", "setup.cfg", "pyproject.toml",
    }
    _CONFIG_EXTENSIONS: set[str] = {
        ".toml", ".yaml", ".yml", ".ini", ".cfg", ".json", ".env",
    }
    _INFRA_NAMES: set[str] = {
        "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
        "Makefile", "Procfile", "Vagrantfile",
    }
    _DOC_EXTENSIONS: set[str] = {".md", ".rst", ".txt"}
    _TEST_MARKERS: tuple[str, ...] = (
        "test_", "_test.py", "/tests/", "/test/", "conftest.py", "tests/",
    )

    def __init__(self, parsers: list[BaseParser] | None = None) -> None:
        self._parsers = tuple(parsers or [])
        self._rules = self._build_rules()

    def classify(self, file_path: str, content: str | None = None) -> FileCategory:
        context = ClassificationContext(path=PurePosixPath(file_path), content=content)
        scores: dict[FileCategory, int] = {}

        self._apply_rules(context, scores)
        self._apply_parser_hints(file_path, content, scores)

        if not scores:
            return FileCategory.UNKNOWN

        best_score = max(scores.values())
        winners = [category for category, score in scores.items() if score == best_score]
        winners.sort(key=lambda category: self._CATEGORY_PRIORITY[category], reverse=True)
        return winners[0]

    def _build_rules(self) -> tuple[ClassificationRule, ...]:
        return (
            ClassificationRule(
                name="infra-name",
                category=FileCategory.INFRASTRUCTURE,
                weight=5,
                predicate=lambda context: context.name in self._INFRA_NAMES,
            ),
            ClassificationRule(
                name="infra-directory",
                category=FileCategory.INFRASTRUCTURE,
                weight=4,
                predicate=lambda context: any(
                    part in {".github", ".gitlab-ci"}
                    for part in context.path.parts
                ),
            ),
            ClassificationRule(
                name="doc-extension",
                category=FileCategory.DOCUMENTATION,
                weight=4,
                predicate=lambda context: context.suffix in self._DOC_EXTENSIONS,
            ),
            ClassificationRule(
                name="doc-name",
                category=FileCategory.DOCUMENTATION,
                weight=3,
                predicate=lambda context: context.path.stem.lower() in self._DOC_NAMES,
            ),
            ClassificationRule(
                name="config-name-or-extension",
                category=FileCategory.CONFIG,
                weight=4,
                predicate=lambda context: (
                    context.name in self._CONFIG_NAMES
                    or context.suffix in self._CONFIG_EXTENSIONS
                ),
            ),
            ClassificationRule(
                name="config-directory",
                category=FileCategory.CONFIG,
                weight=1,
                predicate=lambda context: any(
                    part.lower() in self._CONFIG_DIR_NAMES
                    for part in context.path.parts[:-1]
                ),
            ),
            ClassificationRule(
                name="test-path-marker",
                category=FileCategory.TEST,
                weight=4,
                predicate=lambda context: any(
                    marker in context.normalized_path
                    for marker in self._TEST_MARKERS
                ),
            ),
            ClassificationRule(
                name="test-directory",
                category=FileCategory.TEST,
                weight=3,
                predicate=lambda context: any(
                    part.lower() in self._TEST_DIR_NAMES
                    for part in context.path.parts[:-1]
                ),
            ),
            ClassificationRule(
                name="test-content",
                category=FileCategory.TEST,
                weight=2,
                predicate=lambda context: bool(context.content) and any(
                    marker in context.content
                    for marker in self._TEST_CONTENT_MARKERS
                ),
            ),
        )

    def _apply_rules(
        self,
        context: ClassificationContext,
        scores: dict[FileCategory, int],
    ) -> None:
        for rule in self._rules:
            if rule.matches(context):
                self._add_score(scores, rule.category, rule.weight)

    def _apply_parser_hints(
        self,
        file_path: str,
        content: str | None,
        scores: dict[FileCategory, int],
    ) -> None:
        for parser in self._parsers:
            hint = parser.classify_file(file_path, content=content)
            if hint is None:
                continue
            self._add_score(scores, FileCategory(hint), 3)

    @staticmethod
    def _add_score(scores: dict[FileCategory, int], category: FileCategory, weight: int) -> None:
        scores[category] = scores.get(category, 0) + weight
