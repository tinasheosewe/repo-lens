from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import PurePosixPath

from pydantic import BaseModel, Field

from trace_engine.models.graph import GraphEdge, GraphNode


class ImportInfo(BaseModel):
    """Describes a single import statement."""

    local_name: str
    module_path: str
    original_name: str | None = None
    is_star: bool = False


class UnresolvedCall(BaseModel):
    """A function call whose target lives in another file."""

    source_file: str
    caller_id: str
    called_name: str
    import_info: ImportInfo
    line: int


class ParseResult(BaseModel):
    """Output of parsing a single source file."""

    file_path: str
    nodes: list[GraphNode] = Field(default_factory=list)
    internal_edges: list[GraphEdge] = Field(default_factory=list)
    imports: list[ImportInfo] = Field(default_factory=list)
    unresolved_calls: list[UnresolvedCall] = Field(default_factory=list)
    exports: dict[str, str] = Field(default_factory=dict)


class BaseParser(ABC):
    """Language-specific AST parser interface."""

    @abstractmethod
    def language_name(self) -> str:
        """Human-readable language name (e.g. ``'Python'``)."""

    @abstractmethod
    def parse_file(self, file_path: str, content: str) -> ParseResult:
        """Parse *content* and return nodes, edges, and unresolved refs."""

    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """File extensions this parser handles (e.g. ``{'.py'}``)."""

    def repository_markers(self) -> set[str]:
        """Return filenames that indicate a repository likely uses this language."""
        return set()

    def can_parse(self, file_path: str) -> bool:
        """Return whether this parser can parse *file_path*."""
        return PurePosixPath(file_path).suffix in self.supported_extensions()

    def matches_repository(self, file_paths: Iterable[str]) -> bool:
        """Return whether this parser should activate for the given repository."""
        markers = self.repository_markers()
        for file_path in file_paths:
            if self.can_parse(file_path):
                return True
            if PurePosixPath(file_path).name in markers:
                return True
        return False

    def classify_file(self, file_path: str, content: str | None = None) -> str | None:
        """Return an optional file-category hint for *file_path*."""
        return None

    def module_names(self, file_path: str) -> set[str]:
        """Return importable module names that map to *file_path*."""
        return set()

    def resolve_import_target(
        self,
        importer_path: str,
        module_path: str,
        module_map: dict[str, str],
        *,
        available_paths: set[str] | None = None,
    ) -> str | None:
        """Resolve an import specifier to a repository-relative file path."""
        _ = importer_path, available_paths
        if module_path in module_map:
            return module_map[module_path]
        for candidate, file_path in module_map.items():
            if candidate.endswith(f".{module_path}") or candidate == module_path:
                return file_path
        return None
