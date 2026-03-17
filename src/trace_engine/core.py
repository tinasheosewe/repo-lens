from __future__ import annotations

from pathlib import Path

from trace_engine.analysis.graph_builder import GraphBuilder
from trace_engine.analysis.parser_registry import DEFAULT_PARSER_REGISTRY, ParserRegistry
from trace_engine.ingestion.classifier import FileClassifier
from trace_engine.ingestion.loader import RepoLoader
from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.evidence import QueryResult
from trace_engine.query.dead_code import DeadCodeDetector
from trace_engine.query.dependencies import DependencyAnalyzer
from trace_engine.query.advanced import AdvancedAnalyzer
from trace_engine.query.engine import QueryEngine
from trace_engine.query.impact import ImpactAnalyzer
from trace_engine.query.navigation import CodeNavigator
from trace_engine.storage.repository import FileGraphRepository


_PROJECT_ID = "default"


class Trace:
    """Top-level façade for the Trace system."""

    def __init__(
        self,
        repo_path: str | Path,
        *,
        source: str | None = None,
        ref: str | None = None,
        parser_registry: ParserRegistry | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.source = source or str(self.repo_path)
        self.source_ref = ref
        self._parser_registry = parser_registry or DEFAULT_PARSER_REGISTRY
        detection_loader = RepoLoader(parsers=list(self._parser_registry.parsers))
        self._parsers = list(detection_loader.detect_parsers(self.repo_path))
        self._loader = RepoLoader(parsers=self._parsers)
        self._classifier = FileClassifier(parsers=self._parsers)
        self._builder = GraphBuilder(
            parsers=self._parsers, classifier=self._classifier
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
        return ImpactAnalyzer(self.graph, repo_root=self.repo_path).analyze_by_name(name)

    def dependents(self, name: str) -> QueryResult:
        return QueryEngine(self.graph, repo_root=self.repo_path).find_dependents(name)

    def usages(self, name: str) -> QueryResult:
        return QueryEngine(self.graph, repo_root=self.repo_path).find_usages(name)

    def dead_code(self) -> QueryResult:
        return DeadCodeDetector(self.graph, repo_root=self.repo_path).detect()

    def endpoints(self) -> QueryResult:
        return QueryEngine(self.graph, repo_root=self.repo_path).list_endpoints()

    def cycles(self) -> QueryResult:
        return DependencyAnalyzer(self.graph, repo_root=self.repo_path).find_circular_dependencies()

    def hotspots(self, threshold: int = 3) -> QueryResult:
        return DependencyAnalyzer(self.graph, repo_root=self.repo_path).find_hotspots(threshold=threshold)

    def coupling(self, threshold: int = 2) -> QueryResult:
        return DependencyAnalyzer(self.graph, repo_root=self.repo_path).find_coupled_files(threshold=threshold)

    def search(self, query: str) -> QueryResult:
        return CodeNavigator(self.graph, repo_root=self.repo_path).search(query)

    def path(self, from_name: str, to_name: str) -> QueryResult:
        return CodeNavigator(self.graph, repo_root=self.repo_path).find_path(from_name, to_name)

    def stale_modules(self) -> QueryResult:
        return AdvancedAnalyzer(self.graph, repo_root=self.repo_path).find_stale_modules()

    def entry_flows(self, *, kind: str = "all", max_depth: int = 5) -> QueryResult:
        return AdvancedAnalyzer(self.graph, repo_root=self.repo_path).trace_entry_flows(kind=kind, max_depth=max_depth)

    def criticality(self, *, limit: int = 10) -> QueryResult:
        return AdvancedAnalyzer(self.graph, repo_root=self.repo_path).rank_criticality(limit=limit)

    def onboarding(self) -> QueryResult:
        return AdvancedAnalyzer(self.graph, repo_root=self.repo_path).onboarding_summary()

    def concept_search(self, concept: str) -> QueryResult:
        return AdvancedAnalyzer(self.graph, repo_root=self.repo_path).concept_search(concept)

    def call_flow(self, name: str, *, max_depth: int = 6) -> QueryResult:
        return AdvancedAnalyzer(self.graph, repo_root=self.repo_path).call_flow(name, max_depth=max_depth)

    def history_drift(self, *, limit: int = 10) -> QueryResult:
        return AdvancedAnalyzer(self.graph, repo_root=self.repo_path).history_drift(limit=limit)

    def pr_review(
        self,
        *,
        changed_files: list[str] | None = None,
        diff_text: str | None = None,
        base_ref: str | None = None,
        head_ref: str | None = None,
    ) -> QueryResult:
        return AdvancedAnalyzer(self.graph, repo_root=self.repo_path).pr_review(
            changed_files=changed_files,
            diff_text=diff_text,
            base_ref=base_ref,
            head_ref=head_ref,
        )

    def refactor_plan(self) -> QueryResult:
        return AdvancedAnalyzer(self.graph, repo_root=self.repo_path).refactor_plan()

    def ask_architecture(self, question: str) -> QueryResult:
        return AdvancedAnalyzer(self.graph, repo_root=self.repo_path).ask_architecture(question)
