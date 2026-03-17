import type {
  AboutResponse,
  GraphEdge,
  GraphNode,
  GraphStats,
  QueryResult,
  RepoRefsResponse,
  RepoSupportResponse,
  StatusResponse,
} from "../types";

function resolveApiBase(): string {
  const explicitBase = import.meta.env.VITE_API_BASE;
  if (explicitBase) {
    return explicitBase.replace(/\/$/, "");
  }

  if (typeof window !== "undefined") {
    const { hostname, port, protocol } = window.location;
    if ((hostname === "127.0.0.1" || hostname === "localhost") && port === "5173") {
      return `${protocol}//127.0.0.1:8000/api`;
    }
  }

  return "/api";
}

const BASE = resolveApiBase();
const SESSION_STORAGE_KEY = "trace.session.id";

function getSessionId(): string {
  if (typeof window === "undefined") {
    return "trace-server";
  }

  const existing = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) {
    return existing;
  }

  const next = window.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  window.sessionStorage.setItem(SESSION_STORAGE_KEY, next);
  return next;
}

function requestHeaders(headers?: HeadersInit): Headers {
  const nextHeaders = new Headers(headers);
  nextHeaders.set("X-Trace-Session", getSessionId());
  return nextHeaders;
}

async function parseResponse<T>(res: Response): Promise<T> {
  const contentType = res.headers.get("content-type") || "";

  if (!contentType.includes("application/json")) {
    const bodyText = await res.text();
    throw new Error(
      `Expected JSON from API but received ${contentType || "unknown content type"}: ${bodyText.slice(0, 120)}`,
    );
  }

  return res.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: requestHeaders(),
  });
  if (!res.ok) {
    const body = await parseResponse<{ detail?: string } | { detail?: Array<{ msg?: string }> }>(res).catch(() => ({}));
    const detail = Array.isArray((body as { detail?: Array<{ msg?: string }> }).detail)
      ? (body as { detail?: Array<{ msg?: string }> }).detail?.map((item) => item.msg).filter(Boolean).join("; ")
      : (body as { detail?: string }).detail;
    throw new Error(detail || res.statusText);
  }
  return parseResponse<T>(res);
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: requestHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await parseResponse<{ detail?: string } | { detail?: Array<{ msg?: string }> }>(res).catch(() => ({}));
    const detail = Array.isArray((data as { detail?: Array<{ msg?: string }> }).detail)
      ? (data as { detail?: Array<{ msg?: string }> }).detail?.map((item) => item.msg).filter(Boolean).join("; ")
      : (data as { detail?: string }).detail;
    throw new Error(detail || res.statusText);
  }
  return parseResponse<T>(res);
}

export const api = {
  about: () => get<AboutResponse>("/about"),
  status: () => get<StatusResponse>("/status"),
  repoSupport: (source: string, ref?: string) =>
    get<RepoSupportResponse>(
      `/repo-support?source=${encodeURIComponent(source)}${
        ref ? `&ref=${encodeURIComponent(ref)}` : ""
      }`,
    ),
  repoRefs: (commitLimit = 20) => get<RepoRefsResponse>(`/repo-refs?commit_limit=${commitLimit}`),
  ingest: (source: string, ref?: string) => post<StatusResponse>("/ingest", { source, ref }),
  graphStats: () => get<GraphStats>("/graph/stats"),
  graphNodes: () => get<GraphNode[]>("/graph/nodes"),
  graphEdges: () => get<GraphEdge[]>("/graph/edges"),
  impact: (name: string) => get<QueryResult>(`/impact/${encodeURIComponent(name)}`),
  dependents: (name: string) => get<QueryResult>(`/dependents/${encodeURIComponent(name)}`),
  usages: (name: string) => get<QueryResult>(`/usages/${encodeURIComponent(name)}`),
  deadCode: () => get<QueryResult>("/dead-code"),
  endpoints: () => get<QueryResult>("/endpoints"),
  cycles: () => get<QueryResult>("/cycles"),
  hotspots: (threshold = 3) => get<QueryResult>(`/hotspots?threshold=${threshold}`),
  coupling: () => get<QueryResult>("/coupling"),
  search: (q: string) => get<QueryResult>(`/search?q=${encodeURIComponent(q)}`),
  path: (from: string, to: string) =>
    get<QueryResult>(`/path?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`),
  staleModules: () => get<QueryResult>("/stale-modules"),
  entryFlows: (kind = "all", maxDepth = 5) =>
    get<QueryResult>(`/entry-flows?kind=${encodeURIComponent(kind)}&max_depth=${maxDepth}`),
  criticality: (limit = 10) => get<QueryResult>(`/criticality?limit=${limit}`),
  onboarding: () => get<QueryResult>("/onboarding"),
  conceptSearch: (q: string) => get<QueryResult>(`/concept-search?q=${encodeURIComponent(q)}`),
  callFlow: (name: string, maxDepth = 6) =>
    get<QueryResult>(`/call-flow?name=${encodeURIComponent(name)}&max_depth=${maxDepth}`),
  historyDrift: (limit = 10) => get<QueryResult>(`/history-drift?limit=${limit}`),
  prReview: (payload: {
    base_ref?: string;
    head_ref?: string;
  }) => post<QueryResult>("/pr-review", payload),
  refactorPlan: () => get<QueryResult>("/refactor-plan"),
  askArchitecture: (question: string) => post<QueryResult>("/ask", { question }),
};
