from __future__ import annotations

from pathlib import Path

from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.evidence import Confidence, Evidence, QueryResult, ReasoningStep
from trace_engine.models.graph import EdgeType, NodeType
from trace_engine.query.snippets import QuerySnippetResolver


class CodeNavigator:
    """Graph-backed code navigation: search + path finding."""

    def __init__(
        self,
        graph: CodeGraph,
        repo_root: str | Path | None = None,
    ) -> None:
        self._graph = graph
        self._snippets = QuerySnippetResolver(graph, repo_root=repo_root)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str) -> QueryResult:
        """Find nodes whose name contains *query* (case-insensitive)."""
        query_lower = query.lower()
        matches = [
            n
            for n in self._graph.nodes.values()
            if query_lower in n.name.lower()
        ]
        evidence = [
            Evidence(
                file_path=m.file_path,
                function_name=m.name if m.node_type != NodeType.FILE else None,
                line_start=m.line_start,
                line_end=m.line_end,
                code_snippet=self._snippets.for_node(m),
                description=f"{m.node_type.value}: {m.name}",
            )
            for m in matches
        ]
        return QueryResult(
            conclusion=f"Found {len(matches)} match(es) for '{query}'.",
            evidence=evidence,
            confidence=Confidence.HIGH,
            affected_nodes=[m.id for m in matches],
        )

    # ------------------------------------------------------------------
    # Path finding
    # ------------------------------------------------------------------

    def find_path(self, from_name: str, to_name: str) -> QueryResult:
        """Show all call-paths from *from_name* to *to_name*."""
        from_nodes = self._graph.find_nodes(from_name)
        to_nodes = self._graph.find_nodes(to_name)

        if not from_nodes:
            return QueryResult(
                conclusion=f"Source node '{from_name}' not found.",
                confidence=Confidence.HIGH,
            )
        if not to_nodes:
            return QueryResult(
                conclusion=f"Target node '{to_name}' not found.",
                confidence=Confidence.HIGH,
            )

        from_node = from_nodes[0]
        to_node = to_nodes[0]
        paths = self._graph.get_all_paths(from_node.id, to_node.id)

        if not paths:
            return QueryResult(
                conclusion=f"No path from '{from_name}' to '{to_name}'.",
                confidence=Confidence.HIGH,
            )

        evidence: list[Evidence] = []
        reasoning: list[ReasoningStep] = []
        path_details: list[list[dict[str, object]]] = []
        seen_node_ids: set[str] = set()

        for idx, path in enumerate(paths, start=1):
            readable = " → ".join(
                self._short_name(nid) for nid in path
            )
            reasoning.append(
                ReasoningStep(step=idx, description=f"Path {idx}: {readable}")
            )
            current_path_details: list[dict[str, object]] = []
            for step_index, nid in enumerate(path, start=1):
                node = self._graph.get_node(nid)
                if not node:
                    continue

                current_path_details.append(
                    {
                        "id": node.id,
                        "name": node.name,
                        "node_type": node.node_type.value,
                        "file_path": node.file_path,
                        "line_start": node.line_start,
                        "line_end": node.line_end,
                        "code_snippet": self._snippets.for_node(node),
                        "step": step_index,
                        "step_count": len(path),
                    }
                )

                if node.id not in seen_node_ids:
                    evidence.append(
                        Evidence(
                            file_path=node.file_path,
                            function_name=node.name,
                            line_start=node.line_start,
                            line_end=node.line_end,
                            code_snippet=self._snippets.for_node(node),
                            description=f"Appears in path {idx} at step {step_index} of {len(path)}",
                        )
                    )
                    seen_node_ids.add(node.id)

            path_details.append(current_path_details)

        return QueryResult(
            conclusion=f"Found {len(paths)} path(s) from '{from_name}' to '{to_name}'.",
            evidence=evidence,
            reasoning_chain=reasoning,
            confidence=Confidence.HIGH,
            affected_nodes=[nid for path in paths for nid in path],
            metadata={"paths": paths, "path_details": path_details},
        )

    @staticmethod
    def _short_name(node_id: str) -> str:
        if "::" in node_id:
            return node_id.split("::")[-1]
        return node_id
