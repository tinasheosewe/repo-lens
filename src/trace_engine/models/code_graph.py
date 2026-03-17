from __future__ import annotations

from collections import deque

import networkx as nx

from .graph import EdgeType, GraphEdge, GraphNode, NodeType


class CodeGraph:
    """NetworkX-backed directed multigraph of code elements.

    Nodes are code elements (files, classes, functions, methods).
    Edges are relationships (imports, calls, defines, inherits).

    Edge direction: source *depends on* / *uses* target.
      - A imports B  ⟹  edge A → B
      - A calls B    ⟹  edge A → B
      - A defines B  ⟹  edge A → B  (containment)
      - A inherits B ⟹  edge A → B

    "What depends on X?" = predecessors of X.
    """

    def __init__(self) -> None:
        self._graph: nx.MultiDiGraph = nx.MultiDiGraph()
        self._nodes: dict[str, GraphNode] = {}

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_node(self, node: GraphNode) -> None:
        self._nodes[node.id] = node
        self._graph.add_node(node.id)

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    @property
    def nodes(self) -> dict[str, GraphNode]:
        return dict(self._nodes)

    def get_nodes_by_type(self, node_type: NodeType) -> list[GraphNode]:
        return [n for n in self._nodes.values() if n.node_type == node_type]

    def get_nodes_by_file(self, file_path: str) -> list[GraphNode]:
        return [n for n in self._nodes.values() if n.file_path == file_path]

    def find_nodes(
        self, name: str, node_type: NodeType | None = None
    ) -> list[GraphNode]:
        results = [n for n in self._nodes.values() if n.name == name]
        if node_type is not None:
            results = [n for n in results if n.node_type == node_type]
        return results

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def add_edge(self, edge: GraphEdge) -> None:
        self._graph.add_edge(
            edge.source_id,
            edge.target_id,
            key=edge.edge_type.value,
            data=edge,
        )

    @property
    def edges(self) -> list[GraphEdge]:
        result: list[GraphEdge] = []
        for _u, _v, _key, data in self._graph.edges(keys=True, data=True):
            edge = data.get("data")
            if edge is not None:
                result.append(edge)
        return result

    def get_edges_from(
        self, node_id: str, edge_types: set[EdgeType] | None = None
    ) -> list[GraphEdge]:
        if node_id not in self._graph:
            return []
        edges: list[GraphEdge] = []
        for succ in self._graph.successors(node_id):
            for _key, attrs in self._graph[node_id][succ].items():
                edge = attrs.get("data")
                if edge and (edge_types is None or edge.edge_type in edge_types):
                    edges.append(edge)
        return edges

    def get_edges_to(
        self, node_id: str, edge_types: set[EdgeType] | None = None
    ) -> list[GraphEdge]:
        if node_id not in self._graph:
            return []
        edges: list[GraphEdge] = []
        for pred in self._graph.predecessors(node_id):
            for _key, attrs in self._graph[pred][node_id].items():
                edge = attrs.get("data")
                if edge and (edge_types is None or edge.edge_type in edge_types):
                    edges.append(edge)
        return edges

    # ------------------------------------------------------------------
    # Graph traversal
    # ------------------------------------------------------------------

    def get_dependents(
        self, node_id: str, edge_types: set[EdgeType] | None = None
    ) -> list[GraphNode]:
        """Direct dependents — nodes that point TO *node_id*."""
        edges = self.get_edges_to(node_id, edge_types)
        return [
            self._nodes[e.source_id]
            for e in edges
            if e.source_id in self._nodes
        ]

    def get_dependencies(
        self, node_id: str, edge_types: set[EdgeType] | None = None
    ) -> list[GraphNode]:
        """Direct dependencies — nodes *node_id* points TO."""
        edges = self.get_edges_from(node_id, edge_types)
        return [
            self._nodes[e.target_id]
            for e in edges
            if e.target_id in self._nodes
        ]

    def get_transitive_dependents(
        self, node_id: str, edge_types: set[EdgeType] | None = None
    ) -> list[GraphNode]:
        """All nodes transitively depending on *node_id* (BFS)."""
        visited: set[str] = set()
        queue: deque[str] = deque([node_id])
        while queue:
            current = queue.popleft()
            for dep in self.get_dependents(current, edge_types):
                if dep.id not in visited:
                    visited.add(dep.id)
                    queue.append(dep.id)
        return [self._nodes[nid] for nid in visited if nid in self._nodes]

    def get_transitive_dependencies(
        self, node_id: str, edge_types: set[EdgeType] | None = None
    ) -> list[GraphNode]:
        """All nodes *node_id* transitively depends on (BFS)."""
        visited: set[str] = set()
        queue: deque[str] = deque([node_id])
        while queue:
            current = queue.popleft()
            for dep in self.get_dependencies(current, edge_types):
                if dep.id not in visited:
                    visited.add(dep.id)
                    queue.append(dep.id)
        return [self._nodes[nid] for nid in visited if nid in self._nodes]

    def get_all_paths(
        self, from_id: str, to_id: str, max_depth: int = 10
    ) -> list[list[str]]:
        """All simple paths between two nodes (capped at *max_depth*)."""
        if from_id not in self._graph or to_id not in self._graph:
            return []
        return [
            list(p)
            for p in nx.all_simple_paths(
                self._graph, from_id, to_id, cutoff=max_depth
            )
        ]

    def find_cycles(self) -> list[list[str]]:
        """All simple cycles in the graph."""
        return [list(c) for c in nx.simple_cycles(self._graph)]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return self._graph.number_of_edges()

    def fan_in(self, node_id: str) -> int:
        if node_id not in self._graph:
            return 0
        return self._graph.in_degree(node_id)

    def fan_out(self, node_id: str) -> int:
        if node_id not in self._graph:
            return 0
        return self._graph.out_degree(node_id)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "nodes": {nid: node.model_dump() for nid, node in self._nodes.items()},
            "edges": [edge.model_dump() for edge in self.edges],
        }

    @classmethod
    def from_dict(cls, data: dict) -> CodeGraph:
        graph = cls()
        for node_data in data["nodes"].values():
            graph.add_node(GraphNode.model_validate(node_data))
        for edge_data in data["edges"]:
            graph.add_edge(GraphEdge.model_validate(edge_data))
        return graph
