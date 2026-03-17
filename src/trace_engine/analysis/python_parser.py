from __future__ import annotations

import ast
from pathlib import PurePosixPath

from trace_engine.models.graph import EdgeType, GraphEdge, GraphNode, NodeType

from .base_parser import BaseParser, ImportInfo, ParseResult, UnresolvedCall


class PythonParser(BaseParser):
    """Extract structure from Python source files."""

    def supported_extensions(self) -> set[str]:
        return {".py"}

    def parse_file(self, file_path: str, content: str) -> ParseResult:
        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError:
            return ParseResult(file_path=file_path)

        visitor = _PythonVisitor(file_path, content)
        visitor.visit(tree)
        return visitor.result()


# ------------------------------------------------------------------
# AST visitor (private)
# ------------------------------------------------------------------


class _PythonVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, source: str) -> None:
        self.file_path = file_path
        self._source = source
        self._source_lines = source.splitlines()

        self.nodes: list[GraphNode] = []
        self.internal_edges: list[GraphEdge] = []
        self.imports: list[ImportInfo] = []
        self.unresolved_calls: list[UnresolvedCall] = []

        # Scope tracking
        self._scope_names: list[str] = []
        self._scope_ids: list[str] = []        # parallel stack of node IDs
        self._current_class: str | None = None

        # Symbol tables (file-level only for MVP)
        self._local_defs: dict[str, str] = {}        # name → node_id
        self._import_map: dict[str, ImportInfo] = {}  # local_name → ImportInfo
        self._var_types: dict[str, str] = {}           # var_name → type_name

        # Create FILE node
        last_line = len(self._source_lines) or 1
        file_node = GraphNode(
            id=file_path,
            name=PurePosixPath(file_path).name,
            node_type=NodeType.FILE,
            file_path=file_path,
            line_start=1,
            line_end=last_line,
        )
        self.nodes.append(file_node)
        self._scope_ids.append(file_path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_node_id(self, name: str) -> str:
        qualified = ".".join([*self._scope_names, name])
        return f"{self.file_path}::{qualified}"

    def _current_scope_id(self) -> str:
        return self._scope_ids[-1] if self._scope_ids else self.file_path

    @staticmethod
    def _decorator_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parts: list[str] = []
            cur: ast.expr = node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            return ".".join(reversed(parts))
        if isinstance(node, ast.Call):
            return _PythonVisitor._decorator_name(node.func)
        return ""

    def _snippet(self, line_start: int, line_end: int) -> str:
        return "\n".join(self._source_lines[line_start - 1 : line_end])

    # ------------------------------------------------------------------
    # Visitors
    # ------------------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            local_name = alias.asname or alias.name
            info = ImportInfo(
                local_name=local_name,
                module_path=alias.name,
                original_name=None,
            )
            self.imports.append(info)
            self._import_map[local_name] = info
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in (node.names or []):
            if alias.name == "*":
                self.imports.append(
                    ImportInfo(local_name="*", module_path=module, is_star=True)
                )
                continue
            local_name = alias.asname or alias.name
            info = ImportInfo(
                local_name=local_name,
                module_path=module,
                original_name=alias.name,
            )
            self.imports.append(info)
            self._import_map[local_name] = info
        self.generic_visit(node)

    # --- functions / async functions ---

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._process_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._process_function(node)

    def _process_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        name = node.name
        node_id = self._make_node_id(name)
        is_method = self._current_class is not None
        ntype = NodeType.METHOD if is_method else NodeType.FUNCTION

        decorators = [self._decorator_name(d) for d in node.decorator_list]
        end_line = node.end_lineno or node.lineno

        gnode = GraphNode(
            id=node_id,
            name=name,
            node_type=ntype,
            file_path=self.file_path,
            line_start=node.lineno,
            line_end=end_line,
            metadata={
                "decorators": decorators,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "args": [a.arg for a in node.args.args],
            },
        )
        self.nodes.append(gnode)

        # Register in local defs (file-level)
        if not self._scope_names or (len(self._scope_names) == 1 and self._current_class):
            self._local_defs[name] = node_id

        # DEFINES edge from parent scope
        parent_id = self._current_scope_id()
        self.internal_edges.append(
            GraphEdge(
                source_id=parent_id,
                target_id=node_id,
                edge_type=EdgeType.DEFINES,
                metadata={"line": node.lineno},
            )
        )

        # Walk body
        self._scope_names.append(name)
        self._scope_ids.append(node_id)
        self.generic_visit(node)
        self._scope_ids.pop()
        self._scope_names.pop()

    # --- classes ---

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        name = node.name
        node_id = self._make_node_id(name)
        decorators = [self._decorator_name(d) for d in node.decorator_list]
        end_line = node.end_lineno or node.lineno

        gnode = GraphNode(
            id=node_id,
            name=name,
            node_type=NodeType.CLASS,
            file_path=self.file_path,
            line_start=node.lineno,
            line_end=end_line,
            metadata={"decorators": decorators},
        )
        self.nodes.append(gnode)
        self._local_defs[name] = node_id

        # DEFINES edge
        parent_id = self._current_scope_id()
        self.internal_edges.append(
            GraphEdge(
                source_id=parent_id,
                target_id=node_id,
                edge_type=EdgeType.DEFINES,
                metadata={"line": node.lineno},
            )
        )

        # INHERITS edges
        for base in node.bases:
            base_name = self._extract_name(base)
            if base_name:
                if base_name in self._local_defs:
                    self.internal_edges.append(
                        GraphEdge(
                            source_id=node_id,
                            target_id=self._local_defs[base_name],
                            edge_type=EdgeType.INHERITS,
                        )
                    )
                elif base_name in self._import_map:
                    self.unresolved_calls.append(
                        UnresolvedCall(
                            caller_id=node_id,
                            called_name=base_name,
                            import_info=self._import_map[base_name],
                            line=node.lineno,
                        )
                    )

        # Walk body
        prev_class = self._current_class
        self._current_class = name
        self._scope_names.append(name)
        self._scope_ids.append(node_id)
        self.generic_visit(node)
        self._scope_ids.pop()
        self._scope_names.pop()
        self._current_class = prev_class

    # --- calls ---

    def visit_Call(self, node: ast.Call) -> None:
        caller_id = self._current_scope_id()
        if caller_id == self.file_path:
            # Module-level call — attribute to the file node
            pass

        obj_ref, method_name = self._extract_call_info(node)

        if obj_ref is None and method_name:
            # Direct call: func()
            self._record_direct_call(caller_id, method_name, node.lineno)
        elif obj_ref == "self" and self._current_class and method_name:
            # self.method()
            target_id = f"{self.file_path}::{self._current_class}.{method_name}"
            self.internal_edges.append(
                GraphEdge(
                    source_id=caller_id,
                    target_id=target_id,
                    edge_type=EdgeType.CALLS,
                    metadata={"line": node.lineno},
                )
            )
        elif obj_ref and method_name:
            self._record_attribute_call(caller_id, obj_ref, method_name, node.lineno)

        self.generic_visit(node)

    # --- assignments (for basic type tracking) ---

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Call):
            type_name = self._extract_name(node.value.func)
            if type_name:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self._var_types[target.id] = type_name
                    elif (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                    ):
                        self._var_types[f"self.{target.attr}"] = type_name
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Call resolution helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_call_info(node: ast.Call) -> tuple[str | None, str]:
        """Return ``(object_ref, method_name)``."""
        func = node.func
        if isinstance(func, ast.Name):
            return None, func.id

        if isinstance(func, ast.Attribute):
            parts: list[str] = []
            cur: ast.expr = func
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            parts.reverse()
            if len(parts) >= 2:
                return ".".join(parts[:-1]), parts[-1]

        return None, ""

    @staticmethod
    def _extract_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        return ""

    def _record_direct_call(
        self, caller_id: str, called_name: str, line: int
    ) -> None:
        if called_name in self._local_defs:
            self.internal_edges.append(
                GraphEdge(
                    source_id=caller_id,
                    target_id=self._local_defs[called_name],
                    edge_type=EdgeType.CALLS,
                    metadata={"line": line},
                )
            )
        elif called_name in self._import_map:
            self.unresolved_calls.append(
                UnresolvedCall(
                    caller_id=caller_id,
                    called_name=called_name,
                    import_info=self._import_map[called_name],
                    line=line,
                )
            )

    def _record_attribute_call(
        self, caller_id: str, obj_ref: str, method_name: str, line: int
    ) -> None:
        # Check var_types first (e.g.  auth_service = AuthService(); auth_service.foo())
        if obj_ref in self._var_types:
            type_name = self._var_types[obj_ref]
            full_call = f"{type_name}.{method_name}"
            if type_name in self._local_defs:
                target_id = f"{self.file_path}::{type_name}.{method_name}"
                self.internal_edges.append(
                    GraphEdge(
                        source_id=caller_id,
                        target_id=target_id,
                        edge_type=EdgeType.CALLS,
                        metadata={"line": line},
                    )
                )
            elif type_name in self._import_map:
                self.unresolved_calls.append(
                    UnresolvedCall(
                        caller_id=caller_id,
                        called_name=full_call,
                        import_info=self._import_map[type_name],
                        line=line,
                    )
                )
            return

        # Check if root obj is an imported module (e.g. os.path.join)
        root = obj_ref.split(".")[0]
        if root in self._import_map:
            self.unresolved_calls.append(
                UnresolvedCall(
                    caller_id=caller_id,
                    called_name=f"{obj_ref}.{method_name}",
                    import_info=self._import_map[root],
                    line=line,
                )
            )

    # ------------------------------------------------------------------
    # Build result
    # ------------------------------------------------------------------

    def result(self) -> ParseResult:
        return ParseResult(
            file_path=self.file_path,
            nodes=self.nodes,
            internal_edges=self.internal_edges,
            imports=self.imports,
            unresolved_calls=self.unresolved_calls,
        )
