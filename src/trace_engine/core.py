from __future__ import annotations

from pathlib import Path

from trace_engine.analysis.graph_builder import GraphBuilder
from trace_engine.analysis.python_parser import PythonParser
from trace_engine.ingestion.classifier import FileClassifier
from trace_engine.ingestion.loader import RepoLoader
from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.evidence import QueryResult
from trace_engine.query.dead_code import DeadCodeDetector
from trace_engine.query.dependencies import DependencyAnalyzer
from trace_engine.query.engine import QueryEngine
from trace_engine.query.impact import ImpactAnalyzer
from trace_engine.query.navigation import CodeNavigator
from trace_engine.storage.repository import FileGraphRepository


_PROJECT_ID = "default"


class Trace:
    """Top-level façade for the Trace system."""

    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = Path(repo_path).resolve()
        self._loader = RepoLoader()
        self._classifier = FileClassifier()
        self._builder = GraphBuilder(
            parsers=[PythonParser()], classifier=self._classifier
        )
        self._repo = FileGraphRepository(self.repo_path / ".trace")
        self._graph: CodeGraph | None = None

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest(self) -> CodeGraph:
        files = self._loader.load(self.repo_path)
        self._graph = self._builder.build(files)
        self._repo.save(_PROJECT_ID, self._graph)
        return self._graph

    # ------------------------------------------------------------------
    # Graph access
    # ------------------------------------------------------------------

    @property
    def graph(self) -> CodeGraph:
        if self._graph is None:
            self._graph = self._repo.load(_PROJECT_ID)
        if self._graph is None:
            raise RuntimeError(
                "No graph found. Run 'trace ingest <path>' first."
            )
        return self._graph

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def impact(self, name: str) -> QueryResult:
        return ImpactAnalyzer(self.graph).analyze_by_name(name)

    def dependents(self, name: str) -> QueryResult:
        return QueryEngine(self.graph).find_dependents(name)

    def usages(self, name: str) -> QueryResult:
        return QueryEngine(self.graph).find_usages(name)

    def dead_code(self) -> QueryResult:
        return DeadCodeDetector(self.graph).detect()

    def endpoints(self) -> QueryResult:
        return QueryEngine(self.graph).list_endpoints()

    def cycles(self) -> QueryResult:
        return DependencyAnalyzer(self.graph).find_circular_dependencies()

    def hotspots(self, threshold: int = 3) -> QueryResult:
        return DependencyAnalyzer(self.graph).find_hotspots(threshold=threshold)

    def coupling(self, threshold: int = 2) -> QueryResult:
        return DependencyAnalyzer(self.graph).find_coupled_files(threshold=threshold)

    def search(self, query: str) -> QueryResult:
        return CodeNavigator(self.graph).search(query)

    def path(self, from_name: str, to_name: str) -> QueryResult:
        return CodeNavigator(self.graph).find_path(from_name, to_name)
