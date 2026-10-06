from __future__ import annotations

from pathlib import PurePosixPath

from tree_sitter import Language, Node, Parser
import tree_sitter_javascript
import tree_sitter_typescript

from trace_engine.ingestion.classifier import FileCategory
from trace_engine.models.graph import EdgeType, GraphEdge, GraphNode, NodeType

from .base_parser import BaseParser, ImportInfo, ParseResult, UnresolvedCall


class _EcmaScriptParserBase(BaseParser):
    _TEST_PATH_MARKERS = ("/__tests__/", ".test.", ".spec.", ".cy.")
    _TEST_CONTENT_MARKERS = (
        "describe(",
        "it(",
        "test(",
        "expect(",
        "from \"vitest\"",
        "from 'vitest'",
        "from \"jest\"",
        "from 'jest'",
        "from \"@playwright/test\"",
        "from '@playwright/test'",
    )
    _IMPORT_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".css", ".html")

    def __init__(
        self,
        *,
        language_name: str,
        extensions: set[str],
        repository_markers: set[str],
        language: Language,
    ) -> None:
        self._language_name = language_name
        self._extensions = extensions
        self._repository_markers = repository_markers
        self._parser = Parser(language)

    def language_name(self) -> str:
        return self._language_name

    def supported_extensions(self) -> set[str]:
        return set(self._extensions)

    def repository_markers(self) -> set[str]:
        return set(self._repository_markers)

    def classify_file(self, file_path: str, content: str | None = None) -> str | None:
        path = PurePosixPath(file_path)
        if path.suffix not in self._extensions:
            return None
        normalized = "/" + "/".join(path.parts)
        if any(marker in normalized for marker in self._TEST_PATH_MARKERS):
            return FileCategory.TEST.value
        if content and any(marker in content for marker in self._TEST_CONTENT_MARKERS):
            return FileCategory.TEST.value
        return FileCategory.SOURCE.value

    def module_names(self, file_path: str) -> set[str]:
        path = PurePosixPath(file_path)
        if path.suffix not in self._extensions:
            return set()
        without_suffix = str(path.with_suffix("")).replace("\\", "/")
        names = {without_suffix}
        if path.stem == "index":
            parent = "/".join(path.parts[:-1])
            if parent:
                names.add(parent)
        return names

    def resolve_import_target(
        self,
        importer_path: str,
        module_path: str,
        module_map: dict[str, str],
        *,
        available_paths: set[str] | None = None,
    ) -> str | None:
        available = available_paths or set()
        if module_path.startswith("."):
            importer = PurePosixPath(importer_path)
            base = str((importer.parent / module_path).as_posix())
            resolved = self._resolve_path_candidates(base, available)
            if resolved is not None:
                return resolved

        if module_path in module_map:
            return module_map[module_path]

        resolved = self._resolve_path_candidates(module_path.lstrip("/"), available)
        if resolved is not None:
            return resolved

        suffix_matches = sorted(
            path for path in available if self._matches_suffix(path, module_path)
        )
        if len(suffix_matches) == 1:
            return suffix_matches[0]
        return None

    def parse_file(self, file_path: str, content: str) -> ParseResult:
        source = content.encode("utf-8")
        tree = self._parser_for(file_path).parse(source)
        visitor = _EcmaScriptVisitor(file_path, source)
        visitor.visit(tree.root_node)
        return visitor.result()

    def _parser_for(self, file_path: str) -> Parser:
        return self._parser

    def _resolve_path_candidates(self, base: str, available_paths: set[str]) -> str | None:
        normalized = base.replace("\\", "/")
        candidates = [normalized]
        candidates.extend(f"{normalized}{ext}" for ext in self._IMPORT_EXTENSIONS)
        candidates.extend(f"{normalized}/index{ext}" for ext in self._IMPORT_EXTENSIONS)
        for candidate in candidates:
            if candidate in available_paths:
                return candidate
        return None

    @staticmethod
    def _matches_suffix(path: str, module_path: str) -> bool:
        normalized = module_path.strip("/")
        for suffix in (f"/{normalized}", f"/{normalized}.js", f"/{normalized}.jsx", f"/{normalized}.mjs", f"/{normalized}.cjs", f"/{normalized}.ts", f"/{normalized}.tsx"):
            if path.endswith(suffix):
                return True
        return False


class JavaScriptParser(_EcmaScriptParserBase):
    def __init__(self) -> None:
        super().__init__(
            language_name="JavaScript",
            extensions={".js", ".jsx", ".mjs", ".cjs"},
            repository_markers={
                "package.json",
                "package-lock.json",
                "yarn.lock",
                "pnpm-lock.yaml",
                "vite.config.js",
                "webpack.config.js",
                "rollup.config.js",
                "next.config.js",
            },
            language=Language(tree_sitter_javascript.language()),
        )


class TypeScriptParser(_EcmaScriptParserBase):
    def __init__(self) -> None:
        super().__init__(
            language_name="TypeScript",
            extensions={".ts", ".tsx"},
            repository_markers={
                "package.json",
                "tsconfig.json",
                "jsconfig.json",
                "vite.config.ts",
                "next.config.ts",
            },
            language=Language(tree_sitter_typescript.language_typescript()),
        )
        # JSX is not part of the TypeScript grammar, which reads <Tag> as a
        # type assertion, so .tsx files are parsed with the TSX grammar.
        self._tsx_parser = Parser(Language(tree_sitter_typescript.language_tsx()))

    def _parser_for(self, file_path: str) -> Parser:
        if file_path.endswith(".tsx"):
            return self._tsx_parser
        return self._parser


class _EcmaScriptVisitor:
    def __init__(self, file_path: str, source: bytes) -> None:
        self.file_path = file_path
        self._source = source
        self._source_text = source.decode("utf-8")
        self._source_lines = self._source_text.splitlines()

        self.nodes: list[GraphNode] = []
        self.internal_edges: list[GraphEdge] = []
        self.imports: list[ImportInfo] = []
        self.unresolved_calls: list[UnresolvedCall] = []
        self.exports: dict[str, str] = {}

        self._scope_names: list[str] = []
        self._scope_ids: list[str] = [file_path]
        self._current_class: str | None = None
        self._local_defs: dict[str, str] = {}
        self._import_map: dict[str, ImportInfo] = {}
        self._var_types: dict[str, str] = {}

        file_node = GraphNode(
            id=file_path,
            name=PurePosixPath(file_path).name,
            node_type=NodeType.FILE,
            file_path=file_path,
            line_start=1,
            line_end=len(self._source_lines) or 1,
        )
        self.nodes.append(file_node)

    def visit(self, node: Node) -> None:
        self._visit_node(node)

    def _visit_node(self, node: Node) -> None:
        if node.type == "program":
            for child in node.named_children:
                self._visit_node(child)
            return
        if node.type == "import_statement":
            self._visit_import_statement(node)
            return
        if node.type == "export_statement":
            self._visit_export_statement(node)
            return
        if node.type == "function_declaration":
            self._process_function(node)
            return
        if node.type == "class_declaration":
            self._visit_class_declaration(node)
            return
        if node.type in {"lexical_declaration", "variable_declaration"}:
            self._visit_variable_declaration(node)
            return
        if node.type == "method_definition":
            self._visit_method_definition(node)
            return
        if node.type == "call_expression":
            self._visit_call_expression(node)
        if node.type == "assignment_expression":
            self._visit_assignment_expression(node)
        for child in node.named_children:
            self._visit_node(child)

    def _visit_body(self, body: Node | None) -> None:
        if body is None:
            return
        if body.type == "statement_block":
            for child in body.named_children:
                self._visit_node(child)
            return
        self._visit_node(body)

    def _visit_import_statement(self, node: Node) -> None:
        source_node = node.child_by_field_name("source")
        if source_node is None:
            return
        module_path = self._string_value(source_node)
        clause = next((child for child in node.named_children if child.type == "import_clause"), None)
        if clause is None:
            self.imports.append(ImportInfo(local_name=module_path, module_path=module_path))
            return

        for child in clause.named_children:
            if child.type in {"identifier", "type_identifier"}:
                info = ImportInfo(local_name=self._text(child), module_path=module_path, original_name="default")
                self.imports.append(info)
                self._import_map[info.local_name] = info
            elif child.type == "namespace_import":
                alias_node = child.child_by_field_name("name") or child.named_children[-1]
                info = ImportInfo(local_name=self._text(alias_node), module_path=module_path, original_name="*", is_star=True)
                self.imports.append(info)
                self._import_map[info.local_name] = info
            elif child.type == "named_imports":
                for spec in child.named_children:
                    if spec.type != "import_specifier":
                        continue
                    original_node = spec.child_by_field_name("name") or spec.named_children[0]
                    alias_node = spec.child_by_field_name("alias") or original_node
                    info = ImportInfo(
                        local_name=self._text(alias_node),
                        module_path=module_path,
                        original_name=self._text(original_node),
                    )
                    self.imports.append(info)
                    self._import_map[info.local_name] = info

    def _visit_export_statement(self, node: Node) -> None:
        declaration = node.child_by_field_name("declaration")
        has_default = any(child.type == "default" for child in node.children)
        if declaration is not None:
            if declaration.type == "function_declaration":
                node_id = self._process_function(declaration)
                if node_id is not None:
                    name = self._name_text(declaration)
                    if name:
                        self.exports.setdefault(name, node_id)
                    if has_default:
                        self.exports["default"] = node_id
                return
            if declaration.type == "class_declaration":
                node_id = self._visit_class_declaration(declaration)
                if node_id is not None:
                    name = self._name_text(declaration)
                    if name:
                        self.exports.setdefault(name, node_id)
                    if has_default:
                        self.exports["default"] = node_id
                return
            if declaration.type in {"lexical_declaration", "variable_declaration"}:
                exported = self._visit_variable_declaration(declaration)
                for export_name, node_id in exported.items():
                    self.exports[export_name] = node_id
                return

        export_clause = next((child for child in node.named_children if child.type == "export_clause"), None)
        if export_clause is not None:
            for spec in export_clause.named_children:
                if spec.type != "export_specifier":
                    continue
                local_node = spec.child_by_field_name("name") or spec.named_children[0]
                alias_node = spec.child_by_field_name("alias") or local_node
                local_name = self._text(local_node)
                alias_name = self._text(alias_node)
                if local_name in self._local_defs:
                    self.exports[alias_name] = self._local_defs[local_name]
            return

        if has_default:
            named_children = node.named_children
            if len(named_children) == 1 and named_children[0].type in {"identifier", "type_identifier"}:
                name = self._text(named_children[0])
                if name in self._local_defs:
                    self.exports["default"] = self._local_defs[name]

    def _process_function(self, node: Node) -> str | None:
        name = self._name_text(node)
        if not name:
            return None
        node_id = self._make_node_id(name)
        ntype = NodeType.METHOD if self._current_class is not None else NodeType.FUNCTION
        graph_node = GraphNode(
            id=node_id,
            name=name,
            node_type=ntype,
            file_path=self.file_path,
            line_start=node.start_point.row + 1,
            line_end=node.end_point.row + 1,
            metadata={},
        )
        self.nodes.append(graph_node)

        if self._current_class is None and not self._scope_names:
            self._local_defs[name] = node_id

        self.internal_edges.append(
            GraphEdge(
                source_id=self._current_scope_id(),
                target_id=node_id,
                edge_type=EdgeType.DEFINES,
                metadata={"line": node.start_point.row + 1},
            )
        )

        self._scope_names.append(name)
        self._scope_ids.append(node_id)
        body = node.child_by_field_name("body")
        self._visit_body(body)
        self._scope_ids.pop()
        self._scope_names.pop()
        return node_id

    def _visit_class_declaration(self, node: Node) -> str | None:
        name = self._name_text(node)
        if not name:
            return None
        node_id = self._make_node_id(name)
        graph_node = GraphNode(
            id=node_id,
            name=name,
            node_type=NodeType.CLASS,
            file_path=self.file_path,
            line_start=node.start_point.row + 1,
            line_end=node.end_point.row + 1,
            metadata={},
        )
        self.nodes.append(graph_node)
        self._local_defs[name] = node_id

        self.internal_edges.append(
            GraphEdge(
                source_id=self._current_scope_id(),
                target_id=node_id,
                edge_type=EdgeType.DEFINES,
                metadata={"line": node.start_point.row + 1},
            )
        )

        previous_class = self._current_class
        self._current_class = name
        self._scope_names.append(name)
        self._scope_ids.append(node_id)
        body = node.child_by_field_name("body")
        self._visit_body(body)
        self._scope_ids.pop()
        self._scope_names.pop()
        self._current_class = previous_class
        return node_id

    def _visit_method_definition(self, node: Node) -> str | None:
        name = self._name_text(node)
        if not name:
            return None
        node_id = self._make_node_id(name)
        graph_node = GraphNode(
            id=node_id,
            name=name,
            node_type=NodeType.METHOD,
            file_path=self.file_path,
            line_start=node.start_point.row + 1,
            line_end=node.end_point.row + 1,
            metadata={},
        )
        self.nodes.append(graph_node)
        self.internal_edges.append(
            GraphEdge(
                source_id=self._current_scope_id(),
                target_id=node_id,
                edge_type=EdgeType.DEFINES,
                metadata={"line": node.start_point.row + 1},
            )
        )

        self._scope_names.append(name)
        self._scope_ids.append(node_id)
        body = node.child_by_field_name("body")
        self._visit_body(body)
        self._scope_ids.pop()
        self._scope_names.pop()
        return node_id

    def _visit_variable_declaration(self, node: Node) -> dict[str, str]:
        exported: dict[str, str] = {}
        for declarator in node.named_children:
            if declarator.type != "variable_declarator":
                continue
            name_node = declarator.child_by_field_name("name")
            value_node = declarator.child_by_field_name("value")
            if name_node is None:
                continue

            if value_node is not None and self._is_require_call(value_node):
                module_path = self._require_source(value_node)
                if module_path:
                    self._register_require_import(name_node, module_path)

            if value_node is not None and value_node.type in {"arrow_function", "function_expression"}:
                name = self._binding_name(name_node)
                if not name:
                    continue
                node_id = self._make_node_id(name)
                graph_node = GraphNode(
                    id=node_id,
                    name=name,
                    node_type=NodeType.METHOD if self._current_class is not None else NodeType.FUNCTION,
                    file_path=self.file_path,
                    line_start=declarator.start_point.row + 1,
                    line_end=declarator.end_point.row + 1,
                    metadata={"is_arrow": value_node.type == "arrow_function"},
                )
                self.nodes.append(graph_node)
                if self._current_class is None and not self._scope_names:
                    self._local_defs[name] = node_id
                self.internal_edges.append(
                    GraphEdge(
                        source_id=self._current_scope_id(),
                        target_id=node_id,
                        edge_type=EdgeType.DEFINES,
                        metadata={"line": declarator.start_point.row + 1},
                    )
                )
                self._scope_names.append(name)
                self._scope_ids.append(node_id)
                body = value_node.child_by_field_name("body")
                if body is not None:
                    self._visit_body(body)
                else:
                    for child in value_node.named_children:
                        self._visit_node(child)
                self._scope_ids.pop()
                self._scope_names.pop()
                exported[name] = node_id
                continue

            if value_node is not None and value_node.type == "new_expression":
                type_name = self._constructor_name(value_node)
                binding_name = self._binding_name(name_node)
                if type_name and binding_name:
                    self._var_types[binding_name] = type_name
            if value_node is not None:
                self._visit_node(value_node)
        return exported

    def _visit_assignment_expression(self, node: Node) -> None:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None:
            return

        if right.type == "new_expression":
            type_name = self._constructor_name(right)
            binding_name = self._binding_name(left)
            if type_name and binding_name:
                self._var_types[binding_name] = type_name

        export_name = self._commonjs_export_name(left)
        if export_name is None:
            return
        if right.type in {"identifier", "type_identifier"}:
            local_name = self._text(right)
            if local_name in self._local_defs:
                self.exports[export_name] = self._local_defs[local_name]
        elif right.type == "object":
            for child in right.named_children:
                if child.type != "pair":
                    continue
                key = child.child_by_field_name("key")
                value = child.child_by_field_name("value")
                if key is None or value is None:
                    continue
                value_name = self._binding_name(value)
                if value_name and value_name in self._local_defs:
                    self.exports[self._text(key)] = self._local_defs[value_name]

    def _visit_call_expression(self, node: Node) -> None:
        caller_id = self._current_scope_id()
        object_ref, method_name = self._extract_call_info(node)
        if object_ref is None and method_name:
            self._record_direct_call(caller_id, method_name, node.start_point.row + 1)
        elif object_ref == "this" and self._current_class and method_name:
            target_id = f"{self.file_path}::{self._current_class}.{method_name}"
            self.internal_edges.append(
                GraphEdge(
                    source_id=caller_id,
                    target_id=target_id,
                    edge_type=EdgeType.CALLS,
                    metadata={"line": node.start_point.row + 1},
                )
            )
        elif object_ref and method_name:
            self._record_attribute_call(caller_id, object_ref, method_name, node.start_point.row + 1)

    def _register_require_import(self, name_node: Node, module_path: str) -> None:
        if name_node.type in {"identifier", "type_identifier"}:
            local_name = self._text(name_node)
            info = ImportInfo(local_name=local_name, module_path=module_path, original_name="default")
            self.imports.append(info)
            self._import_map[local_name] = info
            return
        if name_node.type == "object_pattern":
            for child in name_node.named_children:
                if child.type == "pair_pattern":
                    key = child.child_by_field_name("key") or child.named_children[0]
                    value = child.child_by_field_name("value") or child.named_children[-1]
                    info = ImportInfo(
                        local_name=self._binding_name(value),
                        module_path=module_path,
                        original_name=self._text(key),
                    )
                    self.imports.append(info)
                    self._import_map[info.local_name] = info
                elif child.type == "shorthand_property_identifier_pattern":
                    name = self._text(child)
                    info = ImportInfo(local_name=name, module_path=module_path, original_name=name)
                    self.imports.append(info)
                    self._import_map[name] = info

    def _record_direct_call(self, caller_id: str, called_name: str, line: int) -> None:
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
                    source_file=self.file_path,
                    caller_id=caller_id,
                    called_name=called_name,
                    import_info=self._import_map[called_name],
                    line=line,
                )
            )

    def _record_attribute_call(self, caller_id: str, obj_ref: str, method_name: str, line: int) -> None:
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
                        source_file=self.file_path,
                        caller_id=caller_id,
                        called_name=full_call,
                        import_info=self._import_map[type_name],
                        line=line,
                    )
                )
            return

        root = obj_ref.split(".")[0]
        if root in self._import_map:
            self.unresolved_calls.append(
                UnresolvedCall(
                    source_file=self.file_path,
                    caller_id=caller_id,
                    called_name=f"{obj_ref}.{method_name}",
                    import_info=self._import_map[root],
                    line=line,
                )
            )

    def _make_node_id(self, name: str) -> str:
        qualified = ".".join([*self._scope_names, name])
        return f"{self.file_path}::{qualified}"

    def _current_scope_id(self) -> str:
        return self._scope_ids[-1]

    def _text(self, node: Node) -> str:
        return self._source[node.start_byte:node.end_byte].decode("utf-8")

    def _name_text(self, node: Node) -> str:
        name_node = node.child_by_field_name("name")
        return self._text(name_node) if name_node is not None else ""

    def _binding_name(self, node: Node) -> str:
        if node.type in {"identifier", "type_identifier", "property_identifier", "private_property_identifier"}:
            return self._text(node)
        if node.type == "member_expression":
            parts = self._member_parts(node)
            return ".".join(parts)
        return ""

    def _string_value(self, node: Node) -> str:
        text = self._text(node)
        if len(text) >= 2 and text[0] in {'"', "'", "`"} and text[-1] == text[0]:
            return text[1:-1]
        return text

    def _constructor_name(self, node: Node) -> str:
        constructor = node.child_by_field_name("constructor") or node.child_by_field_name("function")
        if constructor is None:
            return ""
        return self._binding_name(constructor)

    def _extract_call_info(self, node: Node) -> tuple[str | None, str]:
        function_node = node.child_by_field_name("function")
        if function_node is None:
            return None, ""
        if function_node.type in {"identifier", "type_identifier", "property_identifier"}:
            return None, self._text(function_node)
        if function_node.type == "member_expression":
            parts = self._member_parts(function_node)
            if len(parts) >= 2:
                return ".".join(parts[:-1]), parts[-1]
        return None, ""

    def _member_parts(self, node: Node) -> list[str]:
        if node.type in {"identifier", "type_identifier", "property_identifier", "private_property_identifier"}:
            return [self._text(node)]
        if node.type == "this":
            return ["this"]
        if node.type == "member_expression":
            object_node = node.child_by_field_name("object")
            property_node = node.child_by_field_name("property")
            parts: list[str] = []
            if object_node is not None:
                parts.extend(self._member_parts(object_node))
            if property_node is not None:
                parts.extend(self._member_parts(property_node))
            return parts
        return []

    def _commonjs_export_name(self, node: Node) -> str | None:
        parts = self._member_parts(node)
        if parts == ["module", "exports"]:
            return "default"
        if len(parts) == 3 and parts[:2] == ["module", "exports"]:
            return parts[2]
        if len(parts) == 2 and parts[0] == "exports":
            return parts[1]
        return None

    def _is_require_call(self, node: Node) -> bool:
        function_node = node.child_by_field_name("function")
        return function_node is not None and self._text(function_node) == "require"

    def _require_source(self, node: Node) -> str | None:
        args = node.child_by_field_name("arguments")
        if args is None:
            return None
        for child in args.named_children:
            if child.type == "string":
                return self._string_value(child)
        return None

    def result(self) -> ParseResult:
        return ParseResult(
            file_path=self.file_path,
            nodes=self.nodes,
            internal_edges=self.internal_edges,
            imports=self.imports,
            unresolved_calls=self.unresolved_calls,
            exports=dict(self.exports),
        )