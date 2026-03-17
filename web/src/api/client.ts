import type {
  AboutResponse,
  GraphEdge,
  GraphNode,
  GraphStats,
  QueryResult,
  RepoSupportResponse,
  StatusResponse,
} from "../types";

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || res.statusText);
  }
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || res.statusText);
  }
  return res.json();
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
};
