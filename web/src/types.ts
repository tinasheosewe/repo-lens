/* ------------------------------------------------------------------ */
/* Shared types mirroring the Trace backend models                     */
/* ------------------------------------------------------------------ */

export interface Evidence {
  file_path: string;
  function_name: string | null;
  line_start: number | null;
  line_end: number | null;
  code_snippet: string | null;
  description: string;
}

export interface ReasoningStep {
  step: number;
  description: string;
  evidence: Evidence | null;
}

export type Confidence = "high" | "medium" | "low";

export interface QueryResult {
  conclusion: string;
  evidence: Evidence[];
  reasoning_chain: ReasoningStep[];
  confidence: Confidence;
  affected_nodes: string[];
  metadata: Record<string, unknown>;
}

export interface GraphNode {
  id: string;
  name: string;
  node_type: "file" | "class" | "function" | "method";
  file_path: string;
  line_start: number;
  line_end: number;
  metadata: Record<string, unknown>;
}

export interface GraphEdge {
  source_id: string;
  target_id: string;
  edge_type: "imports" | "calls" | "defines" | "contains" | "inherits";
  metadata: Record<string, unknown>;
}

export interface GraphStats {
  total_nodes: number;
  total_edges: number;
  nodes_by_type: Record<string, number>;
  edges_by_type: Record<string, number>;
}

export interface StatusResponse {
  loaded: boolean;
  repo_path: string | null;
  node_count: number;
  edge_count: number;
}

export type Page =
  | "dashboard"
  | "impact"
  | "dead-code"
  | "dependencies"
  | "explorer";
