from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from trace_engine.models.code_graph import CodeGraph


class GraphRepository(ABC):
    """Persist and retrieve :class:`CodeGraph` instances."""

    @abstractmethod
    def save(self, project_id: str, graph: CodeGraph) -> None: ...

    @abstractmethod
    def load(self, project_id: str) -> CodeGraph | None: ...

    @abstractmethod
    def exists(self, project_id: str) -> bool: ...


class FileGraphRepository(GraphRepository):
    """JSON-file-backed graph storage."""

    def __init__(self, base_dir: Path | str) -> None:
        self._base = Path(base_dir)

    def _path(self, project_id: str) -> Path:
        return self._base / f"{project_id}.json"

    def save(self, project_id: str, graph: CodeGraph) -> None:
        self._base.mkdir(parents=True, exist_ok=True)
        data = graph.to_dict()
        self._path(project_id).write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )

    def load(self, project_id: str) -> CodeGraph | None:
        p = self._path(project_id)
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        return CodeGraph.from_dict(data)

    def exists(self, project_id: str) -> bool:
        return self._path(project_id).exists()
