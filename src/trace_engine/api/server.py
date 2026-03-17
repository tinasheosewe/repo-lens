from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from trace_engine.core import Trace
from trace_engine.models.evidence import QueryResult

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

_trace: Trace | None = None


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

    class IngestRequest(BaseModel):
        path: str

    class StatusResponse(BaseModel):
        loaded: bool
        repo_path: str | None = None
        node_count: int = 0
        edge_count: int = 0

    @app.get("/api/status", response_model=StatusResponse)
    def status():
        if _trace is None:
            return StatusResponse(loaded=False)
        try:
            g = _trace.graph
            return StatusResponse(
                loaded=True,
                repo_path=str(_trace.repo_path),
                node_count=g.node_count,
                edge_count=g.edge_count,
            )
        except RuntimeError:
            return StatusResponse(loaded=False, repo_path=str(_trace.repo_path))

    @app.post("/api/ingest", response_model=StatusResponse)
    def ingest(req: IngestRequest):
        _init_trace(req.path)
        t = _get_trace()
        g = t.ingest()
        return StatusResponse(
            loaded=True,
            repo_path=str(t.repo_path),
            node_count=g.node_count,
            edge_count=g.edge_count,
        )

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


def _init_trace(repo_path: str) -> None:
    global _trace
    _trace = Trace(repo_path)
    try:
        _trace.graph  # load cached graph if available
    except RuntimeError:
        _trace.ingest()
