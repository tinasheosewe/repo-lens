from __future__ import annotations

from pathlib import Path

from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.evidence import Confidence, Evidence, QueryResult, ReasoningStep
from trace_engine.models.graph import EdgeType, NodeType
from trace_engine.query.snippets import QuerySnippetResolver


class DeadCodeDetector:
    """Find functions / methods with no callers."""

    _ENTRY_POINT_NAMES: set[str] = {"main", "__init__", "__main__"}
    _MAGIC_PREFIXES = "__"
    _ENTRY_DECORATORS = {
        "app.route", "app.get", "app.post", "app.put", "app.delete",
        "router.get", "router.post", "router.put", "router.delete",
        "pytest.fixture", "staticmethod", "classmethod", "property",
    }

    def __init__(
        self,
        graph: CodeGraph,
        repo_root: str | Path | None = None,
    ) -> None:
        self._graph = graph
        self._repo_root = Path(repo_root).resolve() if repo_root else None
        self._snippets = QuerySnippetResolver(graph, repo_root=repo_root)

    def detect(self, *, include_private: bool = False) -> QueryResult:
        callables = (
            self._graph.get_nodes_by_type(NodeType.FUNCTION)
            + self._graph.get_nodes_by_type(NodeType.METHOD)
        )

        dead: list[Evidence] = []
        uncertain: list[Evidence] = []
        reasoning: list[ReasoningStep] = [
            ReasoningStep(
                step=1,
                description=f"Scanned {len(callables)} callable(s) in the code graph.",
            ),
        ]

        for func in callables:
            if self._is_entry_point(func):
                continue
            if not include_private and func.name.startswith("_"):
                continue

            callers = self._graph.get_edges_to(func.id, {EdgeType.CALLS})
            if not callers:
                cat = self._graph.get_node(func.file_path)
                is_test = (
                    cat is not None
                    and cat.metadata.get("category") == "test"
                )
                ev = Evidence(
                    file_path=func.file_path,
                    function_name=func.name,
                    line_start=func.line_start,
                    line_end=func.line_end,
                    code_snippet=self._snippets.for_node(func),
                    description="No incoming CALLS edges",
                )
                if is_test:
                    uncertain.append(ev)
                else:
                    dead.append(ev)

        reasoning.append(
            ReasoningStep(
                step=2,
                description=f"Found {len(dead)} likely dead function(s) and {len(uncertain)} uncertain.",
            )
        )

        return QueryResult(
            conclusion=f"{len(dead)} function(s) appear to be dead code.",
            evidence=dead + uncertain,
            reasoning_chain=reasoning,
            confidence=Confidence.HIGH if not uncertain else Confidence.MEDIUM,
            affected_nodes=[e.function_name or "" for e in dead],
            metadata={
                "dead_count": len(dead),
                "uncertain_count": len(uncertain),
            },
        )

    def _is_entry_point(self, node) -> bool:
        if node.name in self._ENTRY_POINT_NAMES:
            return True
        if node.name.startswith(self._MAGIC_PREFIXES) and node.name.endswith("__"):
            return True
        decorators: list[str] = node.metadata.get("decorators", [])
        return any(
            any(d.startswith(ep) for ep in self._ENTRY_DECORATORS)
            for d in decorators
        )

