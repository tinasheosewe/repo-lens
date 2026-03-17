import { useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphNode, GraphEdge } from "../types";

/* ------------------------------------------------------------------ */
/* Colour palette per node / edge type                                 */
/* ------------------------------------------------------------------ */
const NODE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  file:     { bg: "#1e293b", border: "#3b82f6", text: "#93c5fd" },
  class:    { bg: "#1e1b33", border: "#8b5cf6", text: "#c4b5fd" },
  function: { bg: "#0d2618", border: "#10b981", text: "#6ee7b7" },
  method:   { bg: "#0d2628", border: "#06b6d4", text: "#67e8f9" },
};

const EDGE_COLORS: Record<string, string> = {
  calls:    "#22d3ee",
  imports:  "#818cf8",
  defines:  "#475569",
  contains: "#374151",
  inherits: "#a78bfa",
};

const LANGUAGE_COLORS: Record<string, { border: string; text: string }> = {
  Python: { border: "#f59e0b", text: "#fde68a" },
  JavaScript: { border: "#eab308", text: "#fef08a" },
  TypeScript: { border: "#38bdf8", text: "#bae6fd" },
  HTML: { border: "#fb7185", text: "#fecdd3" },
  CSS: { border: "#2dd4bf", text: "#99f6e4" },
  Other: { border: "#64748b", text: "#cbd5e1" },
};

const EDGE_TYPE_LABELS: Record<string, string> = {
  calls: "Calls",
  imports: "Imports",
  defines: "Defines",
  contains: "Contains",
  inherits: "Inherits",
};

type NodeMetadata = {
  category?: string;
  html_ids?: string[];
  html_classes?: string[];
  linked_assets?: string[];
  css_classes?: string[];
  css_ids?: string[];
};

function inferLanguage(filePath: string): string {
  const ext = filePath.split(".").pop()?.toLowerCase();
  switch (ext) {
    case "py":
      return "Python";
    case "js":
    case "jsx":
    case "mjs":
    case "cjs":
      return "JavaScript";
    case "ts":
    case "tsx":
      return "TypeScript";
    case "html":
    case "htm":
      return "HTML";
    case "css":
      return "CSS";
    default:
      return "Other";
  }
}

function compactLanguageLabel(language: string): string {
  switch (language) {
    case "JavaScript":
      return "JS";
    case "TypeScript":
      return "TS";
    default:
      return language;
  }
}

/* ------------------------------------------------------------------ */
/* Layout — simple force-directed-like grid                            */
/* ------------------------------------------------------------------ */
function layoutNodes(raw: GraphNode[]): Node[] {
  // Group by file_path to cluster
  const byFile = new Map<string, GraphNode[]>();
  for (const n of raw) {
    const list = byFile.get(n.file_path) || [];
    list.push(n);
    byFile.set(n.file_path, list);
  }

  const nodes: Node[] = [];
  let fileIdx = 0;
  const cols = Math.ceil(Math.sqrt(byFile.size));

  for (const [, group] of byFile) {
    const col = fileIdx % cols;
    const row = Math.floor(fileIdx / cols);
    const baseX = col * 320;
    const baseY = row * 340;

    for (let i = 0; i < group.length; i++) {
      const n = group[i];
      const isFile = n.node_type === "file";
      const language = inferLanguage(n.file_path);
      const languageColors = LANGUAGE_COLORS[language] || LANGUAGE_COLORS.Other;
      const c = isFile
        ? {
            bg: NODE_COLORS.file.bg,
            border: languageColors.border,
            text: languageColors.text,
          }
        : NODE_COLORS[n.node_type] || NODE_COLORS.function;
      const label = isFile
        ? `${n.name} · ${compactLanguageLabel(language)}`
        : n.name;

      nodes.push({
        id: n.id,
        position: {
          x: baseX + (isFile ? 0 : 30 + (i % 3) * 100),
          y: baseY + (isFile ? 0 : 60 + Math.floor(i / 3) * 70),
        },
        data: { label },
        type: "default",
        style: {
          background: c.bg,
          border: `1px solid ${c.border}`,
          borderRadius: isFile ? "8px" : "20px",
          color: c.text,
          fontSize: isFile ? "11px" : "10px",
          fontFamily: '"JetBrains Mono", monospace',
          fontWeight: isFile ? 600 : 400,
          padding: isFile ? "8px 14px" : "4px 12px",
          minWidth: isFile ? "120px" : "auto",
          textAlign: "center" as const,
          boxShadow: `0 0 12px ${c.border}22`,
        },
      });
    }
    fileIdx++;
  }
  return nodes;
}

function buildEdges(raw: GraphEdge[]): Edge[] {
  return raw.map((e, i) => ({
    id: `e-${i}`,
    source: e.source_id,
    target: e.target_id,
    type: "default",
    animated: e.edge_type === "calls",
    style: {
      stroke: EDGE_COLORS[e.edge_type] || "#475569",
      strokeWidth: e.edge_type === "defines" ? 1 : 1.5,
      opacity: e.edge_type === "defines" ? 0.3 : 0.7,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 12,
      height: 12,
      color: EDGE_COLORS[e.edge_type] || "#475569",
    },
  }));
}

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */
interface Props {
  rawNodes: GraphNode[];
  rawEdges: GraphEdge[];
  highlightIds?: Set<string>;
  className?: string;
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-[11px] transition-colors ${
        active
          ? "border-t-primary/40 bg-t-primary/15 text-white"
          : "border-t-border/50 bg-gray-900/40 text-gray-400 hover:bg-white/[0.03]"
      }`}
    >
      {label}
    </button>
  );
}

function MetadataBlock({
  title,
  values,
  tone = "cyan",
}: {
  title: string;
  values: string[];
  tone?: "cyan" | "emerald" | "rose" | "amber";
}) {
  if (!values.length) {
    return null;
  }

  const tones: Record<string, string> = {
    cyan: "border-cyan-500/20 bg-cyan-500/10 text-cyan-200",
    emerald: "border-emerald-500/20 bg-emerald-500/10 text-emerald-200",
    rose: "border-rose-500/20 bg-rose-500/10 text-rose-200",
    amber: "border-amber-500/20 bg-amber-500/10 text-amber-200",
  };

  return (
    <div>
      <div className="mb-2 text-[11px] uppercase tracking-wider text-gray-500">{title}</div>
      <div className="flex flex-wrap gap-2">
        {values.map((value) => (
          <span key={value} className={`rounded-full border px-2 py-0.5 text-[11px] ${tones[tone]}`}>
            {value}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function GraphView({ rawNodes, rawEdges, highlightIds, className }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [activeLanguages, setActiveLanguages] = useState<string[]>([]);
  const [activeEdgeTypes, setActiveEdgeTypes] = useState<string[]>([]);

  const languageOptions = useMemo(() => {
    const unique = new Set(
      rawNodes
        .filter((node) => node.node_type === "file")
        .map((node) => inferLanguage(node.file_path)),
    );
    return Array.from(unique).sort();
  }, [rawNodes]);

  const visibleNodeMap = useMemo(() => {
    const visibleLanguages = activeLanguages.length ? new Set(activeLanguages) : null;
    const entries = rawNodes.filter((node) => {
      const language = inferLanguage(node.file_path);
      return !visibleLanguages || visibleLanguages.has(language);
    });
    return new Map(entries.map((node) => [node.id, node]));
  }, [activeLanguages, rawNodes]);

  const filteredEdges = useMemo(() => {
    const edgeFilter = activeEdgeTypes.length ? new Set(activeEdgeTypes) : null;
    return rawEdges.filter((edge) => {
      if (edgeFilter && !edgeFilter.has(edge.edge_type)) {
        return false;
      }
      return visibleNodeMap.has(edge.source_id) && visibleNodeMap.has(edge.target_id);
    });
  }, [activeEdgeTypes, rawEdges, visibleNodeMap]);

  const filteredNodes = useMemo(
    () => Array.from(visibleNodeMap.values()),
    [visibleNodeMap],
  );

  const nodeLookup = useMemo(
    () => new Map(rawNodes.map((node) => [node.id, node])),
    [rawNodes],
  );

  const selectedNode = selectedNodeId ? nodeLookup.get(selectedNodeId) ?? null : null;
  const selectedMetadata = (selectedNode?.metadata ?? {}) as NodeMetadata;

  const selectedOutgoing = useMemo(() => {
    if (!selectedNodeId) {
      return [] as GraphEdge[];
    }
    return filteredEdges.filter((edge) => edge.source_id === selectedNodeId);
  }, [filteredEdges, selectedNodeId]);

  const selectedIncoming = useMemo(() => {
    if (!selectedNodeId) {
      return [] as GraphEdge[];
    }
    return filteredEdges.filter((edge) => edge.target_id === selectedNodeId);
  }, [filteredEdges, selectedNodeId]);

  useEffect(() => {
    let flowNodes = layoutNodes(filteredNodes);
    const flowEdges = buildEdges(filteredEdges);

    if (highlightIds && highlightIds.size > 0) {
      flowNodes = flowNodes.map((node) => {
        if (highlightIds.has(node.id)) {
          return {
            ...node,
            style: {
              ...node.style,
              boxShadow: "0 0 20px rgba(251,113,133,0.5)",
              border: "2px solid #fb7185",
            },
          };
        }
        return { ...node, style: { ...node.style, opacity: 0.35 } };
      });
    }

    if (selectedNodeId) {
      flowNodes = flowNodes.map((node) => {
        if (node.id === selectedNodeId) {
          return {
            ...node,
            style: {
              ...node.style,
              boxShadow: "0 0 22px rgba(56,189,248,0.35)",
              border: "2px solid #38bdf8",
            },
          };
        }
        return node;
      });
    }

    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [filteredEdges, filteredNodes, highlightIds, selectedNodeId, setEdges, setNodes]);

  useEffect(() => {
    if (selectedNodeId && !visibleNodeMap.has(selectedNodeId)) {
      setSelectedNodeId(null);
    }
  }, [selectedNodeId, visibleNodeMap]);

  if (!rawNodes.length) {
    return (
      <div
        className={`flex items-center justify-center text-gray-500 text-sm ${className}`}
      >
        Loading graph…
      </div>
    );
  }

  const toggleLanguage = (language: string) => {
    setActiveLanguages((current) =>
      current.includes(language)
        ? current.filter((value) => value !== language)
        : [...current, language],
    );
  };

  const toggleEdgeType = (edgeType: string) => {
    setActiveEdgeTypes((current) =>
      current.includes(edgeType)
        ? current.filter((value) => value !== edgeType)
        : [...current, edgeType],
    );
  };

  return (
    <div className="space-y-4">
      <div className="glass rounded-xl p-4 space-y-4">
        <div>
          <div className="mb-2 text-[11px] uppercase tracking-wider text-gray-500">Languages</div>
          <div className="flex flex-wrap gap-2">
            <FilterChip
              label="All"
              active={activeLanguages.length === 0}
              onClick={() => setActiveLanguages([])}
            />
            {languageOptions.map((language) => (
              <FilterChip
                key={language}
                label={language}
                active={activeLanguages.includes(language)}
                onClick={() => toggleLanguage(language)}
              />
            ))}
          </div>
        </div>

        <div>
          <div className="mb-2 text-[11px] uppercase tracking-wider text-gray-500">Relationships</div>
          <div className="flex flex-wrap gap-2">
            <FilterChip
              label="All"
              active={activeEdgeTypes.length === 0}
              onClick={() => setActiveEdgeTypes([])}
            />
            {Object.keys(EDGE_TYPE_LABELS).map((edgeType) => (
              <FilterChip
                key={edgeType}
                label={EDGE_TYPE_LABELS[edgeType]}
                active={activeEdgeTypes.includes(edgeType)}
                onClick={() => toggleEdgeType(edgeType)}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className={`${className} glass rounded-xl overflow-hidden`}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            fitView
            minZoom={0.2}
            maxZoom={2}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={24} size={1} color="#1e1e30" />
            <Controls />
            <MiniMap
              nodeColor={(n) => {
                const s = n.style as Record<string, unknown>;
                return (s?.border as string) || "#475569";
              }}
              maskColor="rgba(7,7,13,0.8)"
              pannable
              zoomable
            />
          </ReactFlow>
        </div>

        <aside className="glass rounded-xl p-4 space-y-4">
          {selectedNode ? (
            <>
              <div>
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className="text-sm font-semibold text-white">{selectedNode.name}</span>
                  <span className="rounded-full border border-t-border/50 bg-gray-900/50 px-2 py-0.5 text-[11px] text-gray-300 capitalize">
                    {selectedNode.node_type}
                  </span>
                  <span className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2 py-0.5 text-[11px] text-cyan-200">
                    {inferLanguage(selectedNode.file_path)}
                  </span>
                </div>
                <div className="text-xs font-mono text-gray-500 break-all">{selectedNode.file_path}</div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-t-border/40 bg-gray-950/35 p-3">
                  <div className="text-[11px] uppercase tracking-wider text-gray-500 mb-1">Outgoing</div>
                  <div className="text-xl font-semibold text-white">{selectedOutgoing.length}</div>
                </div>
                <div className="rounded-xl border border-t-border/40 bg-gray-950/35 p-3">
                  <div className="text-[11px] uppercase tracking-wider text-gray-500 mb-1">Incoming</div>
                  <div className="text-xl font-semibold text-white">{selectedIncoming.length}</div>
                </div>
              </div>

              {selectedMetadata.category && (
                <div>
                  <div className="mb-2 text-[11px] uppercase tracking-wider text-gray-500">Category</div>
                  <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-200 capitalize">
                    {selectedMetadata.category}
                  </span>
                </div>
              )}

              <MetadataBlock title="Linked Assets" values={selectedMetadata.linked_assets ?? []} tone="amber" />
              <MetadataBlock title="HTML IDs" values={selectedMetadata.html_ids ?? []} tone="rose" />
              <MetadataBlock title="HTML Classes" values={selectedMetadata.html_classes ?? []} tone="rose" />
              <MetadataBlock title="CSS Classes" values={selectedMetadata.css_classes ?? []} tone="cyan" />
              <MetadataBlock title="CSS IDs" values={selectedMetadata.css_ids ?? []} tone="emerald" />

              <div>
                <div className="mb-2 text-[11px] uppercase tracking-wider text-gray-500">Connected Relationships</div>
                <div className="space-y-2">
                  {[...selectedOutgoing.slice(0, 4), ...selectedIncoming.slice(0, 4)].map((edge, index) => {
                    const targetId = edge.source_id === selectedNode.id ? edge.target_id : edge.source_id;
                    const relatedNode = nodeLookup.get(targetId);
                    return (
                      <div key={`${edge.edge_type}-${index}-${targetId}`} className="rounded-lg border border-t-border/40 bg-gray-950/35 px-3 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs text-gray-200 truncate">{relatedNode?.name ?? targetId}</span>
                          <span className="text-[11px] text-gray-500 capitalize">{edge.edge_type}</span>
                        </div>
                        <div className="mt-1 text-[11px] font-mono text-gray-500 break-all">{relatedNode?.file_path ?? targetId}</div>
                      </div>
                    );
                  })}
                  {!selectedOutgoing.length && !selectedIncoming.length && (
                    <div className="text-sm text-gray-500">No visible relationships under the current filters.</div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="flex h-full min-h-[220px] items-center justify-center rounded-xl border border-dashed border-t-border/40 bg-gray-950/20 p-6 text-center text-sm text-gray-500">
              Select a node in the graph to inspect its language, file metadata, and connected relationships.
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
