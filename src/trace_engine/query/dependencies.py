from __future__ import annotations

from pathlib import Path

from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.evidence import Confidence, Evidence, QueryResult, ReasoningStep
from trace_engine.models.graph import EdgeType, NodeType
from trace_engine.query.snippets import QuerySnippetResolver


class DependencyAnalyzer:
    """Dependency insights: cycles, hotspots, coupling."""

    def __init__(
        self,
        graph: CodeGraph,
        repo_root: str | Path | None = None,
    ) -> None:
        self._graph = graph
        self._snippets = QuerySnippetResolver(graph, repo_root=repo_root)

    # ------------------------------------------------------------------
    # Circular dependencies (file-level)
    # ------------------------------------------------------------------

    def find_circular_dependencies(self) -> QueryResult:
        """Detect circular import chains between files."""
        all_cycles = self._graph.find_cycles()
        # Keep only cycles that are entirely FILE-level IMPORTS edges
        file_ids = {n.id for n in self._graph.get_nodes_by_type(NodeType.FILE)}
        file_cycles: list[list[str]] = [
            c for c in all_cycles
            if all(nid in file_ids for nid in c)
        ]

        evidence = [
            Evidence(
                file_path=cycle[0],
                description=" → ".join(cycle) + f" → {cycle[0]}",
                code_snippet=self._snippets.for_cycle(cycle),
            )
            for cycle in file_cycles
        ]

        return QueryResult(
            conclusion=f"Found {len(file_cycles)} circular dependency chain(s).",
            evidence=evidence,
            reasoning_chain=[
                ReasoningStep(
                    step=1,
                    description=f"Ran cycle detection on {len(file_ids)} file node(s).",
                ),
                ReasoningStep(
                    step=2,
                    description=f"Filtered to {len(file_cycles)} file-level cycle(s).",
                ),
            ],
            confidence=Confidence.HIGH,
            metadata={"cycles": file_cycles},
        )

    # ------------------------------------------------------------------
    # Hotspots (high fan-in / fan-out)
    # ------------------------------------------------------------------

    def find_hotspots(self, *, threshold: int = 3) -> QueryResult:
        """Find nodes with high fan-in or fan-out."""
        hotspots: list[Evidence] = []
        affected: list[str] = []

        for nid, node in self._graph.nodes.items():
            if node.node_type == NodeType.FILE:
                continue
            fi = self._graph.fan_in(nid)
            fo = self._graph.fan_out(nid)
            if fi >= threshold or fo >= threshold:
                hotspots.append(
                    Evidence(
                        file_path=node.file_path,
                        function_name=node.name,
                        line_start=node.line_start,
                        line_end=node.line_end,
                        code_snippet=self._snippets.for_node(node),
                        description=f"fan-in={fi}  fan-out={fo}",
                    )
                )
                affected.append(nid)

        hotspots.sort(
            key=lambda e: sum(
                int(x) for x in (e.description or "").replace("fan-in=", "").replace("fan-out=", "").split()
                if x.isdigit()
            ),
            reverse=True,
        )

        return QueryResult(
            conclusion=f"Found {len(hotspots)} hotspot(s) with fan-in/out ≥ {threshold}.",
            evidence=hotspots,
            confidence=Confidence.HIGH,
            affected_nodes=affected,
        )

    # ------------------------------------------------------------------
    # Tightly coupled modules
    # ------------------------------------------------------------------

    def find_coupled_files(self, *, threshold: int = 2) -> QueryResult:
        """Find file pairs with many inter-dependencies."""
        file_nodes = self._graph.get_nodes_by_type(NodeType.FILE)
        pairs: dict[tuple[str, str], int] = {}

        for fnode in file_nodes:
            edges = self._graph.get_edges_from(fnode.id, {EdgeType.IMPORTS})
            for e in edges:
                pair = tuple(sorted([e.source_id, e.target_id]))
                pairs[pair] = pairs.get(pair, 0) + 1  # type: ignore[arg-type]

        coupled = [
            (a, b, count)
            for (a, b), count in pairs.items()
            if count >= threshold
        ]
        coupled.sort(key=lambda x: x[2], reverse=True)

        evidence = [
            Evidence(
                file_path=a,
                description=f"{a} ↔ {b}  ({count} import edge(s))",
                code_snippet=self._snippets.for_coupled_files(a, b),
            )
            for a, b, count in coupled
        ]

        return QueryResult(
            conclusion=f"Found {len(coupled)} tightly-coupled file pair(s).",
            evidence=evidence,
            confidence=Confidence.MEDIUM,
        )
