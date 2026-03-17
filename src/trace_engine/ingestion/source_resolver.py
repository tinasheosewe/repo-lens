from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class ResolvedRepoSource:
    source: str
    source_type: str
    ref: str | None
    local_path: Path


class RepoSourceResolver:
    """Resolve a repo source into a local directory, cloning remotes when needed."""

    CACHE_DIR = Path.home() / ".trace" / "remote_repos"

    def resolve(self, source: str, ref: str | None = None) -> ResolvedRepoSource:
        normalized = source.strip()
        normalized_ref = ref.strip() if ref else None
        if not normalized:
            raise ValueError("Repository source cannot be empty.")

        if self.is_remote_source(normalized):
            return ResolvedRepoSource(
                source=normalized,
                source_type="remote",
                ref=normalized_ref,
                local_path=self._clone_or_update(normalized, normalized_ref),
            )

        return ResolvedRepoSource(
            source=normalized,
            source_type="local",
            ref=normalized_ref,
            local_path=Path(normalized).expanduser().resolve(),
        )

    @staticmethod
    def is_remote_source(source: str) -> bool:
        parsed = urlparse(source)
        if parsed.scheme in {"http", "https", "git", "ssh", "file"}:
            return True
        if source.startswith("git@"):
            return True
        return False

    def _clone_or_update(self, source: str, ref: str | None) -> Path:
        git_bin = shutil.which("git")
        if git_bin is None:
            raise RuntimeError("git is required to load remote repositories.")

        repo_dir = self._cache_path_for(source, ref)
        repo_dir.parent.mkdir(parents=True, exist_ok=True)

        branch_args = ["--branch", ref] if ref else []
        fetch_target = ref or "HEAD"

        if (repo_dir / ".git").is_dir():
            self._run(
                git_bin,
                ["-C", str(repo_dir), "fetch", "--depth", "1", "origin", fetch_target],
                source,
            )
            self._run(
                git_bin,
                ["-C", str(repo_dir), "reset", "--hard", "FETCH_HEAD"],
                source,
            )
            self._run(
                git_bin,
                ["-C", str(repo_dir), "clean", "-fd"],
                source,
            )
            return repo_dir.resolve()

        if repo_dir.exists():
            shutil.rmtree(repo_dir)

        self._run(
            git_bin,
            ["clone", "--depth", "1", *branch_args, source, str(repo_dir)],
            source,
        )
        return repo_dir.resolve()

    def _cache_path_for(self, source: str, ref: str | None) -> Path:
        parsed = urlparse(source)
        stem = Path(parsed.path or source).stem or "repo"
        safe_stem = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in stem)
        cache_key = source if ref is None else f"{source}@{ref}"
        digest = hashlib.sha1(cache_key.encode("utf-8")).hexdigest()[:12]
        return self.CACHE_DIR / f"{safe_stem}-{digest}"

    @staticmethod
    def _run(git_bin: str, args: list[str], source: str) -> None:
        proc = subprocess.run(
            [git_bin, *args],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return

        stderr = proc.stderr.strip() or proc.stdout.strip() or "unknown git error"
        raise RuntimeError(f"Unable to fetch repository '{source}': {stderr}")