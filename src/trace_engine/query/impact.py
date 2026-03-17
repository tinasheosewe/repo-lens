from __future__ import annotations

from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.evidence import Confidence, Evidence, QueryResult, ReasoningStep
from trace_engine.models.graph import EdgeType, NodeType


class ImpactAnalyzer:
    """Flagship feature: 'What breaks if I change / remove X?'"""

    _USAGE_EDGES = {EdgeType.CALLS, EdgeType.IMPORTS}

    def __init__(self, graph: CodeGraph) -> None:
        self._graph = graph

    def analyze(self, node_id: str) -> QueryResult:
        node = self._graph.get_node(node_id)
        if node is None:
            return QueryResult(
                conclusion=f"Node '{node_id}' not found in the code graph.",
                confidence=Confidence.HIGH,
            )
        return self._run(node)

    def analyze_by_name(self, name: str) -> QueryResult:
        nodes = self._graph.find_nodes(name)
        if not nodes:
            return QueryResult(
                conclusion=f"No node named '{name}' found in the code graph.",
                confidence=Confidence.HIGH,
            )
        return self._run(nodes[0])

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self, node) -> QueryResult:
        # Step 1 — direct dependents
        direct = self._graph.get_dependents(node.id, self._USAGE_EDGES)

        # Step 2 — transitive dependents
        transitive = self._graph.get_transitive_dependents(node.id, self._USAGE_EDGES)

        # Step 3 — classify each affected node
        evidence: list[Evidence] = []
        reasoning: list[ReasoningStep] = [
            ReasoningStep(
                step=1,
                description=(
                    f"Located '{node.name}' ({node.node_type.value}) "
                    f"at {node.file_path}:{node.line_start}"
                ),
            ),
            ReasoningStep(
                step=2,
                description=f"Found {len(direct)} direct dependent(s) via CALLS/IMPORTS edges.",
            ),
            ReasoningStep(
                step=3,
                description=f"Transitive expansion found {len(transitive)} total affected node(s).",
            ),
        ]

        for idx, dep in enumerate(transitive, start=1):
            severity = self._classify_severity(node, dep)
            ev = Evidence(
                file_path=dep.file_path,
                function_name=dep.name,
                line_start=dep.line_start,
                line_end=dep.line_end,
                description=f"[{severity}] {dep.name} ({dep.node_type.value})",
            )
            evidence.append(ev)

            reasoning.append(
                ReasoningStep(
                    step=3 + idx,
                    description=(
                        f"{dep.name} in {dep.file_path}:{dep.line_start} "
                        f"{'directly' if dep in direct else 'transitively'} "
                        f"depends on {node.name} — severity: {severity}"
                    ),
                    evidence=ev,
                )
            )

        # Step 4 — build conclusion
        files_affected = {dep.file_path for dep in transitive}
        conclusion = (
            f"Changing/removing '{node.name}' affects "
            f"{len(transitive)} component(s) across {len(files_affected)} file(s)."
        )

        confidence = Confidence.HIGH if transitive else Confidence.MEDIUM

        return QueryResult(
            conclusion=conclusion,
            evidence=evidence,
            reasoning_chain=reasoning,
            confidence=confidence,
            affected_nodes=[d.id for d in transitive],
            metadata={
                "direct_count": len(direct),
                "transitive_count": len(transitive),
                "files_affected": sorted(files_affected),
            },
        )

    def _classify_severity(self, target, dependent) -> str:
        """Heuristic severity classification."""
        edges = self._graph.get_edges_from(
            dependent.id, {EdgeType.CALLS}
        )
        calls_target = any(e.target_id == target.id for e in edges)

        if calls_target:
            return "CRITICAL — runtime failure if removed"
        # Import-only dependency
        return "HIGH — import would break"
