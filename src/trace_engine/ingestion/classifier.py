from __future__ import annotations

from enum import Enum
from pathlib import PurePosixPath


class FileCategory(str, Enum):
    SOURCE = "source"
    TEST = "test"
    CONFIG = "config"
    INFRASTRUCTURE = "infrastructure"
    DOCUMENTATION = "documentation"
    UNKNOWN = "unknown"


class FileClassifier:
    """Heuristic classifier for repository files."""

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

    def classify(self, file_path: str) -> FileCategory:
        path = PurePosixPath(file_path)
        name = path.name
        suffix = path.suffix

        if name in self._INFRA_NAMES:
            return FileCategory.INFRASTRUCTURE
        if any(p in {".github", ".gitlab-ci"} for p in path.parts):
            return FileCategory.INFRASTRUCTURE
        if suffix in self._DOC_EXTENSIONS:
            return FileCategory.DOCUMENTATION
        if name in self._CONFIG_NAMES or suffix in self._CONFIG_EXTENSIONS:
            return FileCategory.CONFIG
        if any(marker in file_path for marker in self._TEST_MARKERS):
            return FileCategory.TEST
        if suffix == ".py":
            return FileCategory.SOURCE
        return FileCategory.UNKNOWN
