from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class ResolvedRepoSource:
    source: str
    display_source: str
    source_type: str
    ref: str | None
    local_path: Path


@dataclass(frozen=True)
class RepoBranchRef:
    name: str
    sha: str
    is_default: bool = False


@dataclass(frozen=True)
class RepoCommitRef:
    sha: str
    short_sha: str
    summary: str


@dataclass(frozen=True)
class RepoRefCatalog:
    default_branch: str | None
    branches: list[RepoBranchRef]
    commits: list[RepoCommitRef]


class RepoSourceResolver:
    """Resolve a repo source into a local directory, cloning remotes when needed."""

    CACHE_DIR = Path.home() / ".trace" / "remote_repos"
    DEFAULT_MAX_CLONE_BYTES = 250 * 1024 * 1024

    @classmethod
    def is_managed_cache_path(cls, path: str | Path) -> bool:
        try:
            resolved = Path(path).resolve()
        except OSError:
            return False

        try:
            resolved.relative_to(cls.CACHE_DIR.resolve())
        except ValueError:
            return False
        return True

    @classmethod
    def remove_managed_cache_path(cls, path: str | Path) -> None:
        resolved = Path(path).resolve()
        if not cls.is_managed_cache_path(resolved):
            return
        shutil.rmtree(resolved, ignore_errors=True)

    def list_review_refs(
        self,
        repo_path: str | Path,
        *,
        current_ref: str | None = None,
        commit_limit: int = 20,
    ) -> RepoRefCatalog:
        git_bin = shutil.which("git")
        if git_bin is None:
            raise RuntimeError("git is required to inspect repository refs.")

        local_repo = Path(repo_path).resolve()
        if not (local_repo / ".git").is_dir():
            raise RuntimeError("A Git checkout is required to inspect repository refs.")

        default_branch = self._default_remote_branch(git_bin, local_repo)
        branches = self._remote_branches(git_bin, local_repo, default_branch)
        active_ref = current_ref or default_branch or (branches[0].name if branches else None)

        if active_ref:
            self._fetch_ref(git_bin, local_repo, active_ref, depth=max(commit_limit, 20))

        commits = self._recent_commits(git_bin, local_repo, active_ref, limit=commit_limit)
        return RepoRefCatalog(
            default_branch=default_branch,
            branches=branches,
            commits=commits,
        )

    def resolve(self, source: str, ref: str | None = None, *, session_id: str | None = None) -> ResolvedRepoSource:
        normalized = source.strip()
        normalized_ref = ref.strip() if ref else None
        if not normalized:
            raise ValueError("Repository source cannot be empty.")

        if self.is_remote_source(normalized):
            local_path = self._clone_or_update(normalized, normalized_ref, session_id=session_id)
            return ResolvedRepoSource(
                source=normalized,
                display_source=normalized,
                source_type="remote",
                ref=normalized_ref,
                local_path=local_path,
            )

        local_path = Path(normalized).expanduser().resolve()

        return ResolvedRepoSource(
            source=normalized,
            display_source=self.display_source_for(normalized, local_path),
            source_type="local",
            ref=normalized_ref,
            local_path=local_path,
        )

    @staticmethod
    def is_remote_source(source: str) -> bool:
        parsed = urlparse(source)
        if parsed.scheme in {"http", "https", "git", "ssh", "file"}:
            return True
        if source.startswith("git@"):
            return True
        return False

    def _clone_or_update(self, source: str, ref: str | None, *, session_id: str | None = None) -> Path:
        git_bin = shutil.which("git")
        if git_bin is None:
            raise RuntimeError("git is required to load remote repositories.")

        repo_dir = self._cache_path_for(source, ref, session_id=session_id)
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
            self._enforce_repo_size_limit(repo_dir, source)
            return repo_dir.resolve()

        if repo_dir.exists():
            shutil.rmtree(repo_dir)

        self._run(
            git_bin,
            ["clone", "--depth", "1", *branch_args, source, str(repo_dir)],
            source,
        )
        self._enforce_repo_size_limit(repo_dir, source)
        return repo_dir.resolve()

    def display_source_for(self, source: str, local_path: Path) -> str:
        normalized = source.strip()
        if self.is_remote_source(normalized):
            return normalized
        if normalized not in {".", "./"}:
            return normalized

        remote_url = self._git_remote_url(local_path)
        return remote_url or normalized

    def _cache_path_for(self, source: str, ref: str | None, *, session_id: str | None = None) -> Path:
        parsed = urlparse(source)
        stem = Path(parsed.path or source).stem or "repo"
        safe_stem = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in stem)
        cache_key = source if ref is None else f"{source}@{ref}"
        if session_id:
            cache_key = f"{cache_key}#{session_id}"
        digest = hashlib.sha1(cache_key.encode("utf-8")).hexdigest()[:12]
        return self.CACHE_DIR / f"{safe_stem}-{digest}"

    def _max_clone_bytes(self) -> int:
        raw = os.environ.get("TRACE_MAX_CLONE_BYTES", "").strip()
        if not raw:
            return self.DEFAULT_MAX_CLONE_BYTES
        try:
            value = int(raw)
        except ValueError as exc:
            raise RuntimeError("TRACE_MAX_CLONE_BYTES must be an integer.") from exc
        if value <= 0:
            raise RuntimeError("TRACE_MAX_CLONE_BYTES must be positive.")
        return value

    def _enforce_repo_size_limit(self, repo_dir: Path, source: str) -> None:
        limit = self._max_clone_bytes()
        repo_size = self._directory_size(repo_dir)
        if repo_size <= limit:
            return

        shutil.rmtree(repo_dir, ignore_errors=True)
        raise RuntimeError(
            f"Repository '{source}' exceeds the clone size limit of {self._human_size(limit)} "
            f"({self._human_size(repo_size)} checked out)."
        )

    def _default_remote_branch(self, git_bin: str, repo_path: Path) -> str | None:
        proc = subprocess.run(
            [git_bin, "-C", str(repo_path), "ls-remote", "--symref", "origin", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return None

        for line in proc.stdout.splitlines():
            if not line.startswith("ref: ") or not line.endswith("\tHEAD"):
                continue
            ref_name = line.split()[1]
            prefix = "refs/heads/"
            if ref_name.startswith(prefix):
                return ref_name[len(prefix):]
        return None

    def _remote_branches(self, git_bin: str, repo_path: Path, default_branch: str | None) -> list[RepoBranchRef]:
        proc = subprocess.run(
            [git_bin, "-C", str(repo_path), "ls-remote", "--heads", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "Unable to inspect remote branches.")

        branches: list[RepoBranchRef] = []
        prefix = "refs/heads/"
        for line in proc.stdout.splitlines():
            parts = line.split()
            if len(parts) != 2 or not parts[1].startswith(prefix):
                continue
            name = parts[1][len(prefix):]
            branches.append(
                RepoBranchRef(
                    name=name,
                    sha=parts[0],
                    is_default=name == default_branch,
                )
            )
        return sorted(branches, key=lambda branch: (not branch.is_default, branch.name.lower()))

    def _fetch_ref(self, git_bin: str, repo_path: Path, ref: str, *, depth: int) -> None:
        refspec = ref if self._looks_like_commit_sha(ref) else f"+refs/heads/{ref}:refs/remotes/origin/{ref}"
        subprocess.run(
            [git_bin, "-C", str(repo_path), "fetch", "--depth", str(depth), "origin", refspec],
            capture_output=True,
            text=True,
            check=False,
        )

    def _recent_commits(
        self,
        git_bin: str,
        repo_path: Path,
        ref: str | None,
        *,
        limit: int,
    ) -> list[RepoCommitRef]:
        target = ref or "HEAD"
        remote_target = f"origin/{target}"
        rev = remote_target
        probe = subprocess.run(
            [git_bin, "-C", str(repo_path), "rev-parse", "--verify", remote_target],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode != 0:
            rev = target

        proc = subprocess.run(
            [git_bin, "-C", str(repo_path), "log", f"--max-count={limit}", "--pretty=format:%H%x09%h%x09%s", rev],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return []

        commits: list[RepoCommitRef] = []
        for line in proc.stdout.splitlines():
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            commits.append(RepoCommitRef(sha=parts[0], short_sha=parts[1], summary=parts[2]))
        return commits

    @staticmethod
    def _looks_like_commit_sha(value: str) -> bool:
        lowered = value.lower()
        return 7 <= len(lowered) <= 40 and all(ch in "0123456789abcdef" for ch in lowered)

    @staticmethod
    def _directory_size(path: Path) -> int:
        total = 0
        for child in path.rglob("*"):
            if child.is_file():
                total += child.stat().st_size
        return total

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        units = ["B", "KB", "MB", "GB"]
        size = float(size_bytes)
        for unit in units:
            if size < 1024 or unit == units[-1]:
                return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}B"
            size /= 1024
        return f"{size_bytes}B"

    @staticmethod
    def _git_remote_url(repo_path: Path) -> str | None:
        git_bin = shutil.which("git")
        if git_bin is None or not (repo_path / ".git").exists():
            return None

        proc = subprocess.run(
            [git_bin, "-C", str(repo_path), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return None
        remote = proc.stdout.strip()
        return remote or None

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
        raise RuntimeError(RepoSourceResolver._format_git_error(source, stderr))

    @staticmethod
    def _format_git_error(source: str, raw_error: str) -> str:
        normalized = raw_error.lower()

        if (
            "could not read username" in normalized
            or "authentication failed" in normalized
            or "permission denied (publickey)" in normalized
            or "permission denied (keyboard-interactive)" in normalized
            or "fatal: could not read from remote repository" in normalized
        ):
            return (
                f"Unable to fetch repository '{source}': authentication failed. "
                "If this is a private repository, provide a clone URL that already includes access credentials "
                "or configure git credentials/token access in this environment."
            )

        if "repository not found" in normalized:
            return (
                f"Unable to fetch repository '{source}': repository not found or not accessible. "
                "Check that the URL is correct and that this environment has permission to access it."
            )

        return f"Unable to fetch repository '{source}': {raw_error}"