from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trace_engine.analysis.base_parser import BaseParser
from trace_engine.analysis.parser_registry import DEFAULT_PARSER_REGISTRY, ParserRegistry


@dataclass(frozen=True)
class RepoInspection:
    path: str
    supported: bool
    reason: str
    supported_file_count: int
    detected_extensions: list[str]
    detected_languages: list[str]
    active_extensions: list[str]


class RepoLoader:
    """Load source files from a local repository."""

    IGNORED_DIRS: set[str] = {
        ".git", "__pycache__", ".venv", "venv", "env",
        "node_modules", ".trace", ".tox", ".mypy_cache",
        ".pytest_cache", "dist", "build", ".eggs",
    }

    def __init__(self, parsers: list[BaseParser] | None = None) -> None:
        self._parser_registry = ParserRegistry(parsers) if parsers is not None else DEFAULT_PARSER_REGISTRY
        self._parsers = tuple(parsers or self._parser_registry.parsers)

    @property
    def supported_extensions(self) -> set[str]:
        extensions: set[str] = set()
        for parser in self._parsers:
            extensions.update(parser.supported_extensions())
        return extensions

    @property
    def supported_languages(self) -> list[str]:
        return sorted({parser.language_name() for parser in self._parsers})

    def detect_parsers(self, path: Path | str) -> tuple[BaseParser, ...]:
        root = Path(path).resolve()
        if not root.exists():
            raise FileNotFoundError(f"Repository path does not exist: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"Repository path is not a directory: {root}")
        file_paths = [relative_path for _, relative_path in self._iter_repository_files(root)]
        return self._parser_registry.detect_parsers(file_paths)

    def inspect(self, path: Path | str) -> RepoInspection:
        """Return support information for a repository path."""
        root = Path(path).resolve()
        if not root.exists():
            raise FileNotFoundError(f"Repository path does not exist: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"Repository path is not a directory: {root}")

        repo_files = list(self._iter_repository_files(root))
        detected_extensions: set[str] = set()

        for file_path, _ in repo_files:
            suffix = file_path.suffix or "<no-extension>"
            detected_extensions.add(suffix)

        active_parsers = self._parser_registry.detect_parsers(
            relative_path for _, relative_path in repo_files
        )
        active_languages = sorted(
            parser.language_name() for parser in active_parsers
        )
        active_extensions: set[str] = set()
        for parser in active_parsers:
            active_extensions.update(parser.supported_extensions())

        supported_file_count = sum(
            1
            for _, relative_path in repo_files
            if any(parser.can_parse(relative_path) for parser in active_parsers)
        )

        if supported_file_count > 0:
            language_summary = ", ".join(active_languages) or "configured"
            reason = (
                f"Supported: detected {language_summary} and found {supported_file_count} analyzable source file(s)."
            )
            supported = True
        elif active_languages:
            extension_summary = ", ".join(sorted(active_extensions)) or "none"
            language_summary = ", ".join(active_languages)
            reason = (
                f"Unsupported repository. Detected {language_summary} project markers, "
                f"but found no analyzable source files ({extension_summary})."
            )
            supported = False
        else:
            extension_summary = ", ".join(sorted(self._parser_registry.supported_extensions)) or "none"
            language_summary = ", ".join(self._parser_registry.supported_languages) or "configured languages"
            reason = (
                f"Unsupported repository. Trace did not detect a supported language. "
                f"Registered parsers currently handle {language_summary} repositories ({extension_summary})."
            )
            supported = False

        return RepoInspection(
            path=str(root),
            supported=supported,
            reason=reason,
            supported_file_count=supported_file_count,
            detected_extensions=sorted(detected_extensions),
            detected_languages=active_languages,
            active_extensions=sorted(active_extensions),
        )

    def load(self, path: Path | str) -> dict[str, str]:
        """Return ``{relative_path: content}`` for every supported file."""
        root = Path(path).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Repository path does not exist: {root}")

        active_parsers = self.detect_parsers(root)

        files: dict[str, str] = {}
        for file_path, relative_path in self._iter_repository_files(root):
            if not any(parser.can_parse(relative_path) for parser in active_parsers):
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            files[relative_path] = content
        return files

    def _iter_repository_files(self, root: Path):
        for file_path in root.rglob("*"):
            # Symlinks are skipped: one inside a cloned repository can point at
            # any file on the machine that runs the analysis.
            if file_path.is_symlink() or not file_path.is_file():
                continue
            if self._is_ignored(file_path, root):
                continue
            rel = str(file_path.relative_to(root)).replace("\\", "/")
            yield file_path, rel

    def _is_ignored(self, file_path: Path, root: Path) -> bool:
        return any(
            part in self.IGNORED_DIRS
            for part in file_path.relative_to(root).parts
        )
