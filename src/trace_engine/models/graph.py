from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"


class EdgeType(str, Enum):
    IMPORTS = "imports"
    CALLS = "calls"
    DEFINES = "defines"
    CONTAINS = "contains"
    INHERITS = "inherits"


class GraphNode(BaseModel):
    """A node in the code graph (file, class, function, or method)."""

    id: str
    name: str
    node_type: NodeType
    file_path: str
    line_start: int
    line_end: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """A directed edge in the code graph."""

    source_id: str
    target_id: str
    edge_type: EdgeType
    metadata: dict[str, Any] = Field(default_factory=dict)
