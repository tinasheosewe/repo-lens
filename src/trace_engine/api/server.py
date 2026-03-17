from __future__ import annotations

from contextlib import asynccontextmanager
import os
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Thread

from fastapi import Body, FastAPI, HTTPException, Query, Request
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

TRACE_SESSION_HEADER = "X-Trace-Session"
DEFAULT_SESSION_TTL_SECONDS = 60 * 60
DEFAULT_SESSION_SWEEP_INTERVAL_SECONDS = 60
DEFAULT_STARTUP_REPO_SOURCE = "https://github.com/miguelgrinberg/flasky.git"


@dataclass
class SessionTraceState:
    trace: Trace
    last_accessed_at: float


class IngestRequest(BaseModel):
    source: str
    ref: str | None = None


class StatusResponse(BaseModel):
    loaded: bool
    repo_path: str | None = None
    repo_source: str | None = None
    repo_display_source: str | None = None
    repo_source_type: str | None = None
    repo_ref: str | None = None
    node_count: int = 0
    edge_count: int = 0


class HealthResponse(BaseModel):
    ok: bool


class AboutResponse(BaseModel):
    product_name: str
    supported_languages: list[str]
    supported_extensions: list[str]
    ignored_directories: list[str]
    summary: str


class RepoSupportResponse(BaseModel):
    source: str
    display_source: str
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
    base_ref: str | None = None
    head_ref: str | None = None


class RepoRefOptionResponse(BaseModel):
    value: str
    label: str
    kind: str
    is_default: bool = False


class RepoRefsResponse(BaseModel):
    source_type: str
    current_ref: str | None
    default_branch: str | None
    branches: list[RepoRefOptionResponse]
    commits: list[RepoRefOptionResponse]


def _get_session_id(request: Request) -> str:
    session_id = request.headers.get(TRACE_SESSION_HEADER, "").strip()
    if not session_id:
        raise HTTPException(400, f"Missing required {TRACE_SESSION_HEADER} header.")
    return session_id


def _get_session_traces(app: FastAPI) -> dict[str, SessionTraceState]:
    return app.state.trace_sessions


def _get_session_lock(app: FastAPI) -> Lock:
    return app.state.trace_sessions_lock


def _current_time() -> float:
    return time.time()


def _positive_int_from_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be positive.")
    return value


def _session_ttl_seconds() -> int:
    return _positive_int_from_env("TRACE_SESSION_TTL_SECONDS", DEFAULT_SESSION_TTL_SECONDS)


def _session_sweep_interval_seconds() -> int:
    interval = _positive_int_from_env(
        "TRACE_SESSION_SWEEP_INTERVAL_SECONDS",
        DEFAULT_SESSION_SWEEP_INTERVAL_SECONDS,
    )
    return min(interval, _session_ttl_seconds())


def _cleanup_trace_resources(trace: Trace) -> None:
    RepoSourceResolver.remove_managed_cache_path(trace.repo_path)


def _cleanup_expired_sessions(app: FastAPI) -> None:
    now = _current_time()
    ttl = app.state.trace_session_ttl_seconds
    expired: list[Trace] = []

    with _get_session_lock(app):
        traces = _get_session_traces(app)
        for session_id, state in list(traces.items()):
            if now - state.last_accessed_at <= ttl:
                continue
            expired.append(state.trace)
            del traces[session_id]

    for trace in expired:
        _cleanup_trace_resources(trace)


def _cleanup_all_sessions(app: FastAPI) -> None:
    traces: list[Trace] = []
    with _get_session_lock(app):
        session_states = _get_session_traces(app)
        traces = [state.trace for state in session_states.values()]
        session_states.clear()

    for trace in traces:
        _cleanup_trace_resources(trace)


def _evict_session_if_expired(app: FastAPI, session_id: str) -> None:
    expired_trace: Trace | None = None
    with _get_session_lock(app):
        state = _get_session_traces(app).get(session_id)
        if state is None:
            return
        if _current_time() - state.last_accessed_at <= app.state.trace_session_ttl_seconds:
            return
        expired_trace = state.trace
        del _get_session_traces(app)[session_id]

    if expired_trace is not None:
        _cleanup_trace_resources(expired_trace)


def _set_session_trace(app: FastAPI, session_id: str, trace: Trace) -> Trace | None:
    previous: Trace | None = None
    with _get_session_lock(app):
        traces = _get_session_traces(app)
        state = traces.get(session_id)
        if state is not None:
            previous = state.trace
        traces[session_id] = SessionTraceState(
            trace=trace,
            last_accessed_at=_current_time(),
        )
    return previous


def _touch_session(app: FastAPI, session_id: str) -> SessionTraceState | None:
    with _get_session_lock(app):
        state = _get_session_traces(app).get(session_id)
        if state is None:
            return None
        state.last_accessed_at = _current_time()
        return state


def _session_cleanup_worker(app: FastAPI, stop_event: Event) -> None:
    interval = app.state.trace_session_sweep_interval_seconds
    while not stop_event.wait(interval):
        _cleanup_expired_sessions(app)


def _start_session_cleanup_loop(app: FastAPI) -> None:
    thread = app.state.trace_cleanup_thread
    if thread is not None and thread.is_alive():
        return

    stop_event = Event()
    thread = Thread(
        target=_session_cleanup_worker,
        args=(app, stop_event),
        name="trace-session-cleanup",
        daemon=True,
    )
    app.state.trace_cleanup_stop_event = stop_event
    app.state.trace_cleanup_thread = thread
    thread.start()


def _stop_session_cleanup_loop(app: FastAPI) -> None:
    stop_event = app.state.trace_cleanup_stop_event
    thread = app.state.trace_cleanup_thread
    if stop_event is not None:
        stop_event.set()
    if thread is not None:
        thread.join(timeout=2)
    app.state.trace_cleanup_stop_event = None
    app.state.trace_cleanup_thread = None


def _get_trace(request: Request) -> Trace:
    session_id = _get_session_id(request)
    _evict_session_if_expired(request.app, session_id)
    state = _touch_session(request.app, session_id)
    if state is None:
        startup_repo_source = request.app.state.startup_repo_source
        if startup_repo_source:
            return _init_trace(request.app, session_id, startup_repo_source)
        else:
            raise HTTPException(503, "No repository loaded for this session. POST /api/ingest first.")
    return state.trace


def _startup_repo_source(explicit_repo_path: str | None) -> str | None:
    if explicit_repo_path:
        return explicit_repo_path

    env_repo_path = os.environ.get("TRACE_REPO_PATH", "").strip()
    if env_repo_path:
        return env_repo_path

    return DEFAULT_STARTUP_REPO_SOURCE


def create_app(repo_path: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _start_session_cleanup_loop(app)
        try:
            yield
        finally:
            _stop_session_cleanup_loop(app)
            _cleanup_all_sessions(app)

    app = FastAPI(title="Trace", version="0.1.0", lifespan=lifespan)
    app.state.trace_sessions = {}
    app.state.trace_sessions_lock = Lock()
    app.state.trace_session_ttl_seconds = _session_ttl_seconds()
    app.state.trace_session_sweep_interval_seconds = _session_sweep_interval_seconds()
    app.state.trace_cleanup_stop_event = None
    app.state.trace_cleanup_thread = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    startup_repo_path = _startup_repo_source(repo_path)
    app.state.startup_repo_source = startup_repo_path

    # -----------------------------------------------------------------------
    # Routes
    # -----------------------------------------------------------------------

    loader = RepoLoader(parsers=list(DEFAULT_PARSER_REGISTRY.parsers))
    source_resolver = RepoSourceResolver()

    def inspect_repo(
        source: str,
        ref: str | None = None,
        *,
        session_id: str | None = None,
    ) -> tuple[ResolvedRepoSource, RepoSupportResponse]:
        try:
            resolved = source_resolver.resolve(source, ref=ref, session_id=session_id)
            inspection = loader.inspect(resolved.local_path)
        except FileNotFoundError as exc:
            raise HTTPException(400, str(exc)) from exc
        except NotADirectoryError as exc:
            raise HTTPException(400, str(exc)) from exc
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc

        return resolved, RepoSupportResponse(
            source=resolved.source,
            display_source=resolved.display_source,
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
    def status(request: Request):
        try:
            trace = _get_trace(request)
        except HTTPException as exc:
            if exc.status_code == 503:
                return StatusResponse(loaded=False)
            raise

        try:
            g = trace.graph
            return StatusResponse(
                loaded=True,
                repo_path=str(trace.repo_path),
                repo_source=trace.source,
                repo_display_source=source_resolver.display_source_for(trace.source, trace.repo_path),
                repo_source_type="remote" if RepoSourceResolver.is_remote_source(trace.source) else "local",
                repo_ref=trace.source_ref,
                node_count=g.node_count,
                edge_count=g.edge_count,
            )
        except RuntimeError:
            return StatusResponse(
                loaded=False,
                repo_path=str(trace.repo_path),
                repo_source=trace.source,
                repo_display_source=source_resolver.display_source_for(trace.source, trace.repo_path),
                repo_source_type="remote" if RepoSourceResolver.is_remote_source(trace.source) else "local",
                repo_ref=trace.source_ref,
            )

    @app.get("/api/health", response_model=HealthResponse)
    def health():
        return HealthResponse(ok=True)

    @app.post("/api/ingest", response_model=StatusResponse)
    def ingest(request: Request, req: IngestRequest = Body(...)):
        _cleanup_expired_sessions(request.app)
        session_id = _get_session_id(request)
        resolved, inspection = inspect_repo(req.source, ref=req.ref, session_id=session_id)
        if not inspection.supported:
            raise HTTPException(400, inspection.reason)
        t = _init_trace(request.app, session_id, resolved)
        g = t.ingest()
        return StatusResponse(
            loaded=True,
            repo_path=str(t.repo_path),
            repo_source=t.source,
            repo_display_source=source_resolver.display_source_for(t.source, t.repo_path),
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
        request: Request,
        source: str = Query(..., min_length=1),
        ref: str | None = Query(None),
    ):
        _, inspection = inspect_repo(source, ref=ref)
        return inspection

    @app.get("/api/graph/stats")
    def graph_stats(request: Request):
        t = _get_trace(request)
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
    def graph_nodes(request: Request):
        t = _get_trace(request)
        return [n.model_dump() for n in t.graph.nodes.values()]

    @app.get("/api/graph/edges")
    def graph_edges(request: Request):
        t = _get_trace(request)
        return [e.model_dump() for e in t.graph.edges]

    @app.get("/api/impact/{name}", response_model=QueryResult)
    def impact(name: str, request: Request):
        return _get_trace(request).impact(name)

    @app.get("/api/dependents/{name}", response_model=QueryResult)
    def dependents(name: str, request: Request):
        return _get_trace(request).dependents(name)

    @app.get("/api/usages/{name}", response_model=QueryResult)
    def usages(name: str, request: Request):
        return _get_trace(request).usages(name)

    @app.get("/api/dead-code", response_model=QueryResult)
    def dead_code(request: Request):
        return _get_trace(request).dead_code()

    @app.get("/api/endpoints", response_model=QueryResult)
    def endpoints(request: Request):
        return _get_trace(request).endpoints()

    @app.get("/api/cycles", response_model=QueryResult)
    def cycles(request: Request):
        return _get_trace(request).cycles()

    @app.get("/api/hotspots", response_model=QueryResult)
    def hotspots(request: Request, threshold: int = Query(3, ge=1)):
        return _get_trace(request).hotspots(threshold)

    @app.get("/api/coupling", response_model=QueryResult)
    def coupling(request: Request, threshold: int = Query(2, ge=1)):
        return _get_trace(request).coupling(threshold)

    @app.get("/api/search", response_model=QueryResult)
    def search(request: Request, q: str = Query(..., min_length=1)):
        return _get_trace(request).search(q)

    @app.get("/api/path", response_model=QueryResult)
    def find_path(
        request: Request,
        from_name: str = Query(..., alias="from"),
        to_name: str = Query(..., alias="to"),
    ):
        return _get_trace(request).path(from_name, to_name)

    @app.get("/api/stale-modules", response_model=QueryResult)
    def stale_modules(request: Request):
        return _get_trace(request).stale_modules()

    @app.get("/api/entry-flows", response_model=QueryResult)
    def entry_flows(
        request: Request,
        kind: str = Query("all", pattern="^(all|route|job|cli)$"),
        max_depth: int = Query(5, ge=1, le=12),
    ):
        return _get_trace(request).entry_flows(kind=kind, max_depth=max_depth)

    @app.get("/api/criticality", response_model=QueryResult)
    def criticality(request: Request, limit: int = Query(10, ge=1, le=25)):
        return _get_trace(request).criticality(limit=limit)

    @app.get("/api/onboarding", response_model=QueryResult)
    def onboarding(request: Request):
        return _get_trace(request).onboarding()

    @app.get("/api/concept-search", response_model=QueryResult)
    def concept_search(request: Request, q: str = Query(..., min_length=1)):
        return _get_trace(request).concept_search(q)

    @app.get("/api/call-flow", response_model=QueryResult)
    def call_flow(
        request: Request,
        name: str = Query(..., min_length=1),
        max_depth: int = Query(6, ge=1, le=12),
    ):
        return _get_trace(request).call_flow(name, max_depth=max_depth)

    @app.get("/api/history-drift", response_model=QueryResult)
    def history_drift(request: Request, limit: int = Query(10, ge=1, le=25)):
        return _get_trace(request).history_drift(limit=limit)

    @app.get("/api/repo-refs", response_model=RepoRefsResponse)
    def repo_refs(request: Request, commit_limit: int = Query(20, ge=1, le=50)):
        trace = _get_trace(request)
        catalog = source_resolver.list_review_refs(
            trace.repo_path,
            current_ref=trace.source_ref,
            commit_limit=commit_limit,
        )
        return RepoRefsResponse(
            source_type="remote" if RepoSourceResolver.is_remote_source(trace.source) else "local",
            current_ref=trace.source_ref,
            default_branch=catalog.default_branch,
            branches=[
                RepoRefOptionResponse(
                    value=branch.name,
                    label=f"{branch.name}{' (default)' if branch.is_default else ''}",
                    kind="branch",
                    is_default=branch.is_default,
                )
                for branch in catalog.branches
            ],
            commits=[
                RepoRefOptionResponse(
                    value=commit.sha,
                    label=f"{commit.short_sha} {commit.summary}",
                    kind="commit",
                )
                for commit in catalog.commits
            ],
        )

    @app.post("/api/pr-review", response_model=QueryResult)
    def pr_review(request: Request, req: PullRequestReviewRequest = Body(...)):
        return _get_trace(request).pr_review(
            base_ref=req.base_ref,
            head_ref=req.head_ref,
        )

    @app.get("/api/refactor-plan", response_model=QueryResult)
    def refactor_plan(request: Request):
        return _get_trace(request).refactor_plan()

    @app.post("/api/ask", response_model=QueryResult)
    def ask_architecture(request: Request, req: AskRequest = Body(...)):
        return _get_trace(request).ask_architecture(req.question)

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


def _init_trace(app: FastAPI, session_id: str, repo_source: str | ResolvedRepoSource) -> Trace:
    resolved = (
        repo_source
        if isinstance(repo_source, ResolvedRepoSource)
        else RepoSourceResolver().resolve(repo_source, session_id=session_id)
    )
    trace = Trace(
        resolved.local_path,
        source=resolved.source,
        ref=resolved.ref,
        parser_registry=DEFAULT_PARSER_REGISTRY,
    )
    try:
        trace.graph  # load cached graph if available
    except RuntimeError:
        trace.ingest()
    previous = _set_session_trace(app, session_id, trace)
    if previous is not None and previous.repo_path != trace.repo_path:
        _cleanup_trace_resources(previous)
    return trace
