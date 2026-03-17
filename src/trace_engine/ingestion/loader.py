from __future__ import annotations

from pathlib import Path


class RepoLoader:
    """Load source files from a local repository."""

    IGNORED_DIRS: set[str] = {
        ".git", "__pycache__", ".venv", "venv", "env",
        "node_modules", ".trace", ".tox", ".mypy_cache",
        ".pytest_cache", "dist", "build", ".eggs",
    }
    SUPPORTED_EXTENSIONS: set[str] = {".py"}

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
