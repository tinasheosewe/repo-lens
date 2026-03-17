from __future__ import annotations

import re
from pathlib import PurePosixPath

from trace_engine.ingestion.classifier import FileCategory
from trace_engine.models.graph import GraphNode, NodeType

from .base_parser import BaseParser, ImportInfo, ParseResult


class CssParser(BaseParser):
    _IMPORT_PATTERN = re.compile(r"@import\s+(?:url\()?['\"]([^'\")]+)['\"]\)?")
    _CLASS_SELECTOR_PATTERN = re.compile(r"\.([A-Za-z_][\w-]*)")
    _ID_SELECTOR_PATTERN = re.compile(r"#([A-Za-z_][\w-]*)")

    def language_name(self) -> str:
        return "CSS"

    def supported_extensions(self) -> set[str]:
        return {".css"}

    def classify_file(self, file_path: str, content: str | None = None) -> str | None:
        if PurePosixPath(file_path).suffix != ".css":
            return None
        return FileCategory.SOURCE.value

    def module_names(self, file_path: str) -> set[str]:
        path = PurePosixPath(file_path)
        names = {str(path.with_suffix("")), file_path}
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
        importer = PurePosixPath(importer_path)
        candidate = str((importer.parent / module_path).as_posix())
        if candidate in available:
            return candidate
        if f"{candidate}.css" in available:
            return f"{candidate}.css"
        if module_path in module_map:
            return module_map[module_path]
        return None

    def parse_file(self, file_path: str, content: str) -> ParseResult:
        file_node = GraphNode(
            id=file_path,
            name=PurePosixPath(file_path).name,
            node_type=NodeType.FILE,
            file_path=file_path,
            line_start=1,
            line_end=len(content.splitlines()) or 1,
            metadata={
                "css_classes": sorted(set(self._CLASS_SELECTOR_PATTERN.findall(content))),
                "css_ids": sorted(set(self._ID_SELECTOR_PATTERN.findall(content))),
            },
        )
        imports = [
            ImportInfo(local_name=module_path, module_path=module_path)
            for module_path in self._IMPORT_PATTERN.findall(content)
        ]
        return ParseResult(file_path=file_path, nodes=[file_node], imports=imports)