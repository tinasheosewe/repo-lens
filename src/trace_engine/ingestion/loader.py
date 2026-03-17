from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoInspection:
    path: str
    supported: bool
    reason: str
    supported_file_count: int
    detected_extensions: list[str]


class RepoLoader:
    """Load source files from a local repository."""

    IGNORED_DIRS: set[str] = {
        ".git", "__pycache__", ".venv", "venv", "env",
        "node_modules", ".trace", ".tox", ".mypy_cache",
        ".pytest_cache", "dist", "build", ".eggs",
    }
    SUPPORTED_EXTENSIONS: set[str] = {".py"}

    def inspect(self, path: Path | str) -> RepoInspection:
        """Return support information for a repository path."""
        root = Path(path).resolve()
        if not root.exists():
            raise FileNotFoundError(f"Repository path does not exist: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"Repository path is not a directory: {root}")

        detected_extensions: set[str] = set()
        supported_file_count = 0

        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            if self._is_ignored(file_path, root):
                continue

            suffix = file_path.suffix or "<no-extension>"
            detected_extensions.add(suffix)
            if file_path.suffix in self.SUPPORTED_EXTENSIONS:
                supported_file_count += 1

        if supported_file_count > 0:
            reason = (
                f"Supported: found {supported_file_count} Python source file(s) that Trace can analyze."
            )
            supported = True
        else:
            reason = (
                "Unsupported repository. Trace currently analyzes Python repositories only "
                f"and did not find any supported files ({', '.join(sorted(self.SUPPORTED_EXTENSIONS))})."
            )
            supported = False

        return RepoInspection(
            path=str(root),
            supported=supported,
            reason=reason,
            supported_file_count=supported_file_count,
            detected_extensions=sorted(detected_extensions),
        )

    def load(self, path: Path | str) -> dict[str, str]:
        """Return ``{relative_path: content}`` for every supported file."""
        root = Path(path).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Repository path does not exist: {root}")

        files: dict[str, str] = {}
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            if self._is_ignored(file_path, root):
                continue
            if file_path.suffix not in self.SUPPORTED_EXTENSIONS:
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            rel = str(file_path.relative_to(root))
            # Normalise to forward slashes for cross-platform consistency.
            files[rel.replace("\\", "/")] = content
        return files

    def _is_ignored(self, file_path: Path, root: Path) -> bool:
        return any(
            part in self.IGNORED_DIRS
            for part in file_path.relative_to(root).parts
        )
