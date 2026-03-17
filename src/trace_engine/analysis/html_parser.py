from __future__ import annotations

from html.parser import HTMLParser as BaseHtmlParser
from pathlib import PurePosixPath

from trace_engine.ingestion.classifier import FileCategory
from trace_engine.models.graph import GraphNode, NodeType

from .base_parser import BaseParser, ImportInfo, ParseResult


class HtmlParser(BaseParser):
    _IMPORTABLE_EXTENSIONS = (".html", ".css", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx")

    def language_name(self) -> str:
        return "HTML"

    def supported_extensions(self) -> set[str]:
        return {".html", ".htm"}

    def repository_markers(self) -> set[str]:
        return {"index.html"}

    def classify_file(self, file_path: str, content: str | None = None) -> str | None:
        if PurePosixPath(file_path).suffix not in self.supported_extensions():
            return None
        return FileCategory.SOURCE.value

    def module_names(self, file_path: str) -> set[str]:
        path = PurePosixPath(file_path)
        without_suffix = str(path.with_suffix(""))
        names = {without_suffix, file_path}
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
        path = self._resolve_relative(importer_path, module_path)
        if path in available:
            return path
        for ext in self._IMPORTABLE_EXTENSIONS:
            if f"{path}{ext}" in available:
                return f"{path}{ext}"
        if module_path in module_map:
            return module_map[module_path]
        return None

    def parse_file(self, file_path: str, content: str) -> ParseResult:
        collector = _HtmlCollector(file_path)
        collector.feed(content)
        collector.close()
        file_node = GraphNode(
            id=file_path,
            name=PurePosixPath(file_path).name,
            node_type=NodeType.FILE,
            file_path=file_path,
            line_start=1,
            line_end=len(content.splitlines()) or 1,
            metadata={
                "html_ids": sorted(collector.ids),
                "html_classes": sorted(collector.classes),
                "linked_assets": sorted(collector.assets),
            },
        )
        imports = [ImportInfo(local_name=asset, module_path=asset) for asset in sorted(collector.assets)]
        return ParseResult(file_path=file_path, nodes=[file_node], imports=imports)

    @staticmethod
    def _resolve_relative(importer_path: str, module_path: str) -> str:
        importer = PurePosixPath(importer_path)
        return str((importer.parent / module_path).as_posix()).replace("//", "/")


class _HtmlCollector(BaseHtmlParser):
    def __init__(self, file_path: str) -> None:
        super().__init__(convert_charrefs=True)
        self.file_path = file_path
        self.ids: set[str] = set()
        self.classes: set[str] = set()
        self.assets: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name: value for name, value in attrs}
        if attr_map.get("id"):
            self.ids.add(attr_map["id"] or "")
        if attr_map.get("class"):
            self.classes.update(part for part in (attr_map["class"] or "").split() if part)

        if tag == "script" and attr_map.get("src"):
            self.assets.add(attr_map["src"] or "")
        if tag == "link" and attr_map.get("href"):
            rel = (attr_map.get("rel") or "").lower()
            if "stylesheet" in rel:
                self.assets.add(attr_map["href"] or "")