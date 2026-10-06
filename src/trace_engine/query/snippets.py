from __future__ import annotations

from pathlib import Path

from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.graph import EdgeType, GraphNode


class QuerySnippetResolver:
    """Resolve code snippets and textual details for query evidence."""

    def __init__(
        self,
        graph: CodeGraph,
        repo_root: str | Path | None = None,
    ) -> None:
        self._graph = graph
        self._repo_root = Path(repo_root).resolve() if repo_root else None

    def for_node(self, node: GraphNode) -> str | None:
        return self.for_location(node.file_path, node.line_start, node.line_end)

    def for_location(
        self,
        file_path: str,
        line_start: int | None,
        line_end: int | None,
    ) -> str | None:
        if line_start is None:
            return None

        candidates = self._candidate_paths(file_path)
        for candidate in candidates:
            try:
                lines = candidate.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue

            start_index = max(line_start - 1, 0)
            end_index = min(line_end or line_start, len(lines))
            if start_index >= end_index:
                continue
            return "\n".join(lines[start_index:end_index])

        return None

    def for_coupled_files(
        self,
        source_id: str,
        target_id: str,
    ) -> str | None:
        sections: list[str] = []

        forward = self._describe_import_direction(source_id, target_id)
        if forward:
            sections.append(forward)

        reverse = self._describe_import_direction(target_id, source_id)
        if reverse:
            sections.append(reverse)

        if not sections:
            return None
        return "\n\n".join(sections)

    def for_cycle(self, cycle: list[str]) -> str | None:
        if not cycle:
            return None

        sections: list[str] = []
        for index, source_id in enumerate(cycle):
            target_id = cycle[(index + 1) % len(cycle)]
            section = self._describe_import_direction(source_id, target_id)
            if section:
                sections.append(section)

        if not sections:
            return None
        return "\n\n".join(sections)

    def _describe_import_direction(
        self,
        source_id: str,
        target_id: str,
    ) -> str | None:
        source_node = self._graph.get_node(source_id)
        target_node = self._graph.get_node(target_id)
        if source_node is None or target_node is None:
            return None

        edges = [
            edge
            for edge in self._graph.get_edges_from(source_id, {EdgeType.IMPORTS})
            if edge.target_id == target_id
        ]
        if not edges:
            return None

        names = [
            str(edge.metadata.get("imported_name", target_node.name))
            for edge in edges
        ]
        source_preview = self._find_import_lines(source_node.file_path, names)

        header = f"{source_node.file_path} imports {target_node.file_path}"
        if source_preview:
            return f"{header}\n{source_preview}"
        return header

    def _find_import_lines(self, file_path: str, terms: list[str]) -> str | None:
        if not terms:
            return None

        candidates = self._candidate_paths(file_path)
        normalized_terms = [term for term in terms if term]

        for candidate in candidates:
            try:
                lines = candidate.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue

            matches: list[str] = []
            for index, line in enumerate(lines, start=1):
                if "import" not in line:
                    continue
                if any(term in line for term in normalized_terms):
                    matches.append(f"{index}: {line.rstrip()}")
                if len(matches) >= 5:
                    break

            if matches:
                return "\n".join(matches)

        return None

    def _candidate_paths(self, file_path: str) -> list[Path]:
        raw_path = Path(file_path)
        candidates: list[Path] = []

        if raw_path.is_absolute():
            candidates.append(raw_path)
        if self._repo_root is not None:
            candidates.append(self._repo_root / file_path)
        candidates.append(Path.cwd() / file_path)

        seen: set[Path] = set()
        resolved_candidates: list[Path] = []
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if not self._inside_repo(resolved):
                continue
            if resolved.is_file():
                resolved_candidates.append(resolved)
        return resolved_candidates

    def _inside_repo(self, resolved: Path) -> bool:
        """With a repository root, only read files that resolve inside it.

        Paths reach this class from a stored graph, from git and from LLM tool
        calls, and ``resolve()`` follows symlinks, so this check is what keeps
        a snippet from being read from elsewhere on the machine.
        """
        if self._repo_root is None:
            return True
        try:
            resolved.relative_to(self._repo_root)
        except ValueError:
            return False
        return True