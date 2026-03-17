from __future__ import annotations

from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from trace_engine.analysis.parser_registry import DEFAULT_PARSER_REGISTRY
from trace_engine.core import Trace
from trace_engine.ingestion.loader import RepoLoader
from trace_engine.ingestion.source_resolver import RepoSourceResolver, ResolvedRepoSource
from trace_engine.models.evidence import QueryResult

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

_trace: Trace | None = None


class IngestRequest(BaseModel):
    source: str
    ref: str | None = None


class StatusResponse(BaseModel):
    loaded: bool
    repo_path: str | None = None
    repo_source: str | None = None
    repo_source_type: str | None = None
    repo_ref: str | None = None
    node_count: int = 0
    edge_count: int = 0


class AboutResponse(BaseModel):
    product_name: str
    supported_languages: list[str]
    supported_extensions: list[str]
    ignored_directories: list[str]
    summary: str


class RepoSupportResponse(BaseModel):
    source: str
    source_type: str
    ref: str | None
    resolved_path: str
    supported: bool
    reason: str
    supported_file_count: int
    detected_extensions: list[str]
    detected_languages: list[str]
    active_extensions: list[str]


class AskRequest(BaseModel):
    question: str


class PullRequestReviewRequest(BaseModel):
    changed_files: list[str] | None = None
    diff_text: str | None = None
    base_ref: str | None = None
    head_ref: str | None = None


class MigrationTrackerRequest(BaseModel):
    legacy_terms: list[str]
    target_term: str | None = None


def _get_trace() -> Trace:
    if _trace is None:
        raise HTTPException(503, "No repository loaded. POST /api/ingest first.")
    return _trace


def create_app(repo_path: str | None = None) -> FastAPI:
    app = FastAPI(title="Trace", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if repo_path:
        _init_trace(repo_path)

    # -----------------------------------------------------------------------
    # Routes
    # -----------------------------------------------------------------------

    loader = RepoLoader(parsers=list(DEFAULT_PARSER_REGISTRY.parsers))
    source_resolver = RepoSourceResolver()

    def inspect_repo(source: str, ref: str | None = None) -> tuple[ResolvedRepoSource, RepoSupportResponse]:
        try:
            resolved = source_resolver.resolve(source, ref=ref)
            inspection = loader.inspect(resolved.local_path)
        except FileNotFoundError as exc:
            raise HTTPException(400, str(exc)) from exc
        except NotADirectoryError as exc:
            raise HTTPException(400, str(exc)) from exc
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc

        return resolved, RepoSupportResponse(
            source=resolved.source,
            source_type=resolved.source_type,
            ref=resolved.ref,
            resolved_path=inspection.path,
            supported=inspection.supported,
            reason=inspection.reason,
            supported_file_count=inspection.supported_file_count,
            detected_extensions=inspection.detected_extensions,
            detected_languages=inspection.detected_languages,
            active_extensions=inspection.active_extensions,
        )

    @app.get("/api/status", response_model=StatusResponse)
    def status():
        if _trace is None:
            return StatusResponse(loaded=False)
        try:
            g = _trace.graph
            return StatusResponse(
                loaded=True,
                repo_path=str(_trace.repo_path),
                repo_source=_trace.source,
                repo_source_type="remote" if RepoSourceResolver.is_remote_source(_trace.source) else "local",
                repo_ref=_trace.source_ref,
                node_count=g.node_count,
                edge_count=g.edge_count,
            )
        except RuntimeError:
            return StatusResponse(
                loaded=False,
                repo_path=str(_trace.repo_path),
                repo_source=_trace.source,
                repo_source_type="remote" if RepoSourceResolver.is_remote_source(_trace.source) else "local",
                repo_ref=_trace.source_ref,
            )

    @app.post("/api/ingest", response_model=StatusResponse)
    def ingest(req: IngestRequest = Body(...)):
        resolved, inspection = inspect_repo(req.source, ref=req.ref)
        if not inspection.supported:
            raise HTTPException(400, inspection.reason)
        _init_trace(resolved)
        t = _get_trace()
        g = t.ingest()
        return StatusResponse(
            loaded=True,
            repo_path=str(t.repo_path),
            repo_source=t.source,
            repo_source_type=inspection.source_type,
            repo_ref=t.source_ref,
            node_count=g.node_count,
            edge_count=g.edge_count,
        )

    @app.get("/api/about", response_model=AboutResponse)
    def about():
        return AboutResponse(
            product_name="Trace",
            supported_languages=DEFAULT_PARSER_REGISTRY.supported_languages,
            supported_extensions=sorted(DEFAULT_PARSER_REGISTRY.supported_extensions),
            ignored_directories=sorted(loader.IGNORED_DIRS),
            summary=(
                "Trace loads Git repository sources, detects supported languages automatically, "
                "and activates the matching parsers without repo-specific setup. "
                "It builds a graph from analyzable source files and ignores generated, cached, and dependency directories."
            ),
        )

    @app.get("/api/repo-support", response_model=RepoSupportResponse)
    def repo_support(
        source: str = Query(..., min_length=1),
        ref: str | None = Query(None),
    ):
        _, inspection = inspect_repo(source, ref=ref)
        return inspection

    @app.get("/api/graph/stats")
    def graph_stats():
        t = _get_trace()
        g = t.graph
        from trace_engine.models.graph import NodeType, EdgeType

        node_counts = {}
        for nt in NodeType:
            node_counts[nt.value] = len(g.get_nodes_by_type(nt))
        edge_counts: dict[str, int] = {}
        for e in g.edges:
            edge_counts[e.edge_type.value] = edge_counts.get(e.edge_type.value, 0) + 1
        return {
            "total_nodes": g.node_count,
            "total_edges": g.edge_count,
            "nodes_by_type": node_counts,
            "edges_by_type": edge_counts,
        }

    @app.get("/api/graph/nodes")
    def graph_nodes():
        t = _get_trace()
        return [n.model_dump() for n in t.graph.nodes.values()]

    @app.get("/api/graph/edges")
    def graph_edges():
        t = _get_trace()
        return [e.model_dump() for e in t.graph.edges]

    @app.get("/api/impact/{name}", response_model=QueryResult)
    def impact(name: str):
        return _get_trace().impact(name)

    @app.get("/api/dependents/{name}", response_model=QueryResult)
    def dependents(name: str):
        return _get_trace().dependents(name)

    @app.get("/api/usages/{name}", response_model=QueryResult)
    def usages(name: str):
        return _get_trace().usages(name)

    @app.get("/api/dead-code", response_model=QueryResult)
    def dead_code():
        return _get_trace().dead_code()

    @app.get("/api/endpoints", response_model=QueryResult)
    def endpoints():
        return _get_trace().endpoints()

    @app.get("/api/cycles", response_model=QueryResult)
    def cycles():
        return _get_trace().cycles()

    @app.get("/api/hotspots", response_model=QueryResult)
    def hotspots(threshold: int = Query(3, ge=1)):
        return _get_trace().hotspots(threshold)

    @app.get("/api/coupling", response_model=QueryResult)
    def coupling(threshold: int = Query(2, ge=1)):
        return _get_trace().coupling(threshold)

    @app.get("/api/search", response_model=QueryResult)
    def search(q: str = Query(..., min_length=1)):
        return _get_trace().search(q)

    @app.get("/api/path", response_model=QueryResult)
    def find_path(
        from_name: str = Query(..., alias="from"),
        to_name: str = Query(..., alias="to"),
    ):
        return _get_trace().path(from_name, to_name)

    @app.get("/api/stale-modules", response_model=QueryResult)
    def stale_modules():
        return _get_trace().stale_modules()

    @app.get("/api/entry-flows", response_model=QueryResult)
    def entry_flows(
        kind: str = Query("all", pattern="^(all|route|job|cli)$"),
        max_depth: int = Query(5, ge=1, le=12),
    ):
        return _get_trace().entry_flows(kind=kind, max_depth=max_depth)

    @app.get("/api/criticality", response_model=QueryResult)
    def criticality(limit: int = Query(10, ge=1, le=25)):
        return _get_trace().criticality(limit=limit)

    @app.get("/api/onboarding", response_model=QueryResult)
    def onboarding():
        return _get_trace().onboarding()

    @app.get("/api/concept-search", response_model=QueryResult)
    def concept_search(q: str = Query(..., min_length=1)):
        return _get_trace().concept_search(q)

    @app.get("/api/call-flow", response_model=QueryResult)
    def call_flow(
        name: str = Query(..., min_length=1),
        max_depth: int = Query(6, ge=1, le=12),
    ):
        return _get_trace().call_flow(name, max_depth=max_depth)

    @app.get("/api/history-drift", response_model=QueryResult)
    def history_drift(limit: int = Query(10, ge=1, le=25)):
        return _get_trace().history_drift(limit=limit)

    @app.post("/api/pr-review", response_model=QueryResult)
    def pr_review(req: PullRequestReviewRequest = Body(...)):
        return _get_trace().pr_review(
            changed_files=req.changed_files,
            diff_text=req.diff_text,
            base_ref=req.base_ref,
            head_ref=req.head_ref,
        )

    @app.get("/api/refactor-plan", response_model=QueryResult)
    def refactor_plan():
        return _get_trace().refactor_plan()

    @app.post("/api/migration-tracker", response_model=QueryResult)
    def migration_tracker(req: MigrationTrackerRequest = Body(...)):
        return _get_trace().migration_tracker(
            legacy_terms=req.legacy_terms,
            target_term=req.target_term,
        )

    @app.post("/api/ask", response_model=QueryResult)
    def ask_architecture(req: AskRequest = Body(...)):
        return _get_trace().ask_architecture(req.question)

    # -----------------------------------------------------------------------
    # Serve built frontend (production)
    # -----------------------------------------------------------------------
    dist = Path(__file__).parent.parent.parent.parent / "web" / "dist"
    if dist.is_dir():
        from fastapi.responses import FileResponse

        @app.get("/{full_path:path}")
        def spa(full_path: str):
            file = dist / full_path
            if file.is_file():
                return FileResponse(file)
            return FileResponse(dist / "index.html")

    return app


def _init_trace(repo_source: str | ResolvedRepoSource) -> None:
    global _trace
    resolved = (
        repo_source
        if isinstance(repo_source, ResolvedRepoSource)
        else RepoSourceResolver().resolve(repo_source)
    )
    _trace = Trace(
        resolved.local_path,
        source=resolved.source,
        ref=resolved.ref,
        parser_registry=DEFAULT_PARSER_REGISTRY,
    )
    try:
        _trace.graph  # load cached graph if available
    except RuntimeError:
        _trace.ingest()
