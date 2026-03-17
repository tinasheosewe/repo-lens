from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Evidence(BaseModel):
    """A piece of evidence backing a query result."""

    file_path: str
    function_name: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    code_snippet: str | None = None
    description: str


class ReasoningStep(BaseModel):
    """One step in the reasoning chain."""

    step: int
    description: str
    evidence: Evidence | None = None


class QueryResult(BaseModel):
    """Structured output for every Trace query."""

    conclusion: str
    evidence: list[Evidence] = Field(default_factory=list)
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    confidence: Confidence
    affected_nodes: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
