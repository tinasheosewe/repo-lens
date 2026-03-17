from __future__ import annotations

from pathlib import PurePosixPath
from typing import Iterable

from trace_engine.ingestion.classifier import FileCategory, FileClassifier
from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.graph import EdgeType, GraphEdge, NodeType

from .base_parser import BaseParser, ParseResult, UnresolvedCall


class GraphBuilder:
    """Build a :class:`CodeGraph` from parsed source files."""

    def __init__(
        self,
        parsers: list[BaseParser],
        classifier: FileClassifier | None = None,
    ) -> None:
        self._parsers: dict[str, BaseParser] = {}
        for parser in parsers:
            for ext in parser.supported_extensions():
                self._parsers[ext] = parser
        self._classifier = classifier or FileClassifier()

    def build(self, files: dict[str, str]) -> CodeGraph:
        graph = CodeGraph()
        parse_results: list[ParseResult] = []

        # Phase 1 — parse each file
        for file_path, content in files.items():
            ext = PurePosixPath(file_path).suffix
            parser = self._parsers.get(ext)
            if parser is None:
                continue
            result = parser.parse_file(file_path, content)
            parse_results.append(result)

        # Phase 2 — add all nodes + internal edges
        for result in parse_results:
            for node in result.nodes:
                if node.node_type == NodeType.FILE:
                    cat = self._classifier.classify(node.file_path)
                    node.metadata["category"] = cat.value
                graph.add_node(node)
            for edge in result.internal_edges:
                graph.add_edge(edge)

        # Phase 3 — build module → file-path mapping
        module_map = self._build_module_map(files.keys())

        # Phase 4 — resolve import edges (file → file)
        for result in parse_results:
            for imp in result.imports:
                if imp.is_star:
                    continue
                target_file = self._resolve_module(imp.module_path, module_map)
                if target_file and graph.has_node(target_file):
                    graph.add_edge(
                        GraphEdge(
                            source_id=result.file_path,
                            target_id=target_file,
                            edge_type=EdgeType.IMPORTS,
                            metadata={
                                "imported_name": imp.original_name or imp.module_path,
                            },
                        )
                    )

        # Phase 5 — resolve cross-file calls
        for result in parse_results:
            for call in result.unresolved_calls:
                target_id = self._resolve_call(call, module_map, graph)
                if target_id and graph.has_node(target_id):
                    graph.add_edge(
                        GraphEdge(
                            source_id=call.caller_id,
                            target_id=target_id,
                            edge_type=EdgeType.CALLS,
                            metadata={"line": call.line},
                        )
                    )

        return graph

    # ------------------------------------------------------------------
    # Module resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _build_module_map(file_paths: Iterable[str]) -> dict[str, str]:
        """Map dotted module paths → file paths."""
        module_map: dict[str, str] = {}
        for fp in file_paths:
            if not fp.endswith(".py"):
                continue
            module = fp.replace("/", ".").replace("\\", ".")
            module = module[:-3]  # strip .py
            if module.endswith(".__init__"):
                pkg = module[:-9]
                module_map[pkg] = fp
            module_map[module] = fp
        return module_map

    @staticmethod
    def _resolve_module(
        module_path: str, module_map: dict[str, str]
    ) -> str | None:
        if module_path in module_map:
            return module_map[module_path]
        # Try suffix match (handles projects not rooted at the repo top)
        for mod, fp in module_map.items():
            if mod.endswith(f".{module_path}") or mod == module_path:
                return fp
        return None

    @staticmethod
    def _resolve_call(
        call: UnresolvedCall,
        module_map: dict[str, str],
        graph: CodeGraph,
    ) -> str | None:
        imp = call.import_info
        target_file = GraphBuilder._resolve_module(imp.module_path, module_map)
        if target_file is None:
            return None

        called = call.called_name
        if "." in called:
            # Class.method  or  module.func
            candidate = f"{target_file}::{called}"
            if graph.has_node(candidate):
                return candidate
            # Fallback: try just the last part
            last = called.rsplit(".", 1)[-1]
            candidate2 = f"{target_file}::{last}"
            if graph.has_node(candidate2):
                return candidate2
            return candidate  # return best guess even if not yet in graph
        else:
            original = imp.original_name or called
            return f"{target_file}::{original}"
