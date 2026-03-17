from __future__ import annotations

from abc import ABC, abstractmethod

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


class BaseParser(ABC):
    """Language-specific AST parser interface."""

    @abstractmethod
    def parse_file(self, file_path: str, content: str) -> ParseResult:
        """Parse *content* and return nodes, edges, and unresolved refs."""

    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """File extensions this parser handles (e.g. ``{'.py'}``)."""
