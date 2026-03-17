from __future__ import annotations

from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.evidence import Confidence, Evidence, QueryResult, ReasoningStep
from trace_engine.models.graph import EdgeType, NodeType


class QueryEngine:
    """Deterministic graph-backed queries — no LLM required."""

    def __init__(self, graph: CodeGraph) -> None:
        self._graph = graph

    # ------------------------------------------------------------------
    # What depends on X?
    # ------------------------------------------------------------------

    def find_dependents(self, name: str) -> QueryResult:
        nodes = self._graph.find_nodes(name)
        if not nodes:
            return QueryResult(
                conclusion=f"No node named '{name}' found in the code graph.",
                confidence=Confidence.HIGH,
            )

        target = nodes[0]
        dependents = self._graph.get_dependents(
            target.id, edge_types={EdgeType.CALLS, EdgeType.IMPORTS}
        )
        evidence = [
            Evidence(
                file_path=d.file_path,
                function_name=d.name,
                line_start=d.line_start,
                line_end=d.line_end,
                description=f"{d.name} depends on {target.name}",
            )
            for d in dependents
        ]
        return QueryResult(
            conclusion=(
                f"{len(dependents)} component(s) directly depend on '{target.name}'."
            ),
            evidence=evidence,
            reasoning_chain=[
                ReasoningStep(
                    step=1,
                    description=f"Located node '{target.name}' ({target.node_type.value}) at {target.file_path}:{target.line_start}",
                ),
                ReasoningStep(
                    step=2,
                    description=f"Traversed incoming CALLS and IMPORTS edges — found {len(dependents)} direct dependent(s).",
                ),
            ],
            confidence=Confidence.HIGH,
            affected_nodes=[d.id for d in dependents],
        )

    # ------------------------------------------------------------------
    # Where is X used?
    # ------------------------------------------------------------------

    def find_usages(self, name: str) -> QueryResult:
        nodes = self._graph.find_nodes(name)
        if not nodes:
            return QueryResult(
                conclusion=f"No node named '{name}' found.",
                confidence=Confidence.HIGH,
            )

        target = nodes[0]
        callers = self._graph.get_dependents(
            target.id, edge_types={EdgeType.CALLS}
        )
        evidence = []
        for c in callers:
            edges = self._graph.get_edges_to(target.id, {EdgeType.CALLS})
            for e in edges:
                if e.source_id == c.id:
                    evidence.append(
                        Evidence(
                            file_path=c.file_path,
                            function_name=c.name,
                            line_start=e.metadata.get("line"),
                            description=f"Called from {c.name} in {c.file_path}",
                        )
                    )
                    break
            else:
                evidence.append(
                    Evidence(
                        file_path=c.file_path,
                        function_name=c.name,
                        line_start=c.line_start,
                        description=f"Called from {c.name}",
                    )
                )

        return QueryResult(
            conclusion=f"'{target.name}' is used in {len(callers)} location(s).",
            evidence=evidence,
            confidence=Confidence.HIGH,
            affected_nodes=[c.id for c in callers],
        )

    # ------------------------------------------------------------------
    # List all API endpoints
    # ------------------------------------------------------------------

    _ENDPOINT_DECORATORS = {
        "app.route", "app.get", "app.post", "app.put", "app.delete", "app.patch",
        "router.get", "router.post", "router.put", "router.delete", "router.patch",
    }

    def list_endpoints(self) -> QueryResult:
        endpoints: list[Evidence] = []
        affected: list[str] = []
        for node in (
            self._graph.get_nodes_by_type(NodeType.FUNCTION)
            + self._graph.get_nodes_by_type(NodeType.METHOD)
        ):
            decorators: list[str] = node.metadata.get("decorators", [])
            for d in decorators:
                if any(d.startswith(ep) for ep in self._ENDPOINT_DECORATORS):
                    endpoints.append(
                        Evidence(
                            file_path=node.file_path,
                            function_name=node.name,
                            line_start=node.line_start,
                            description=f"Endpoint: @{d}",
                        )
                    )
                    affected.append(node.id)
                    break

        return QueryResult(
            conclusion=f"Found {len(endpoints)} API endpoint(s).",
            evidence=endpoints,
            confidence=Confidence.HIGH,
            affected_nodes=affected,
        )
