import { useCallback, useEffect, useMemo, useState } from "react";
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
import { api } from "../api/client";

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
      const c = NODE_COLORS[n.node_type] || NODE_COLORS.function;

      nodes.push({
        id: n.id,
        position: {
          x: baseX + (isFile ? 0 : 30 + (i % 3) * 100),
          y: baseY + (isFile ? 0 : 60 + Math.floor(i / 3) * 70),
        },
        data: { label: n.name },
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
  highlightIds?: Set<string>;
  className?: string;
}

export default function GraphView({ highlightIds, className }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    Promise.all([api.graphNodes(), api.graphEdges()]).then(([rawN, rawE]) => {
      let flowNodes = layoutNodes(rawN);
      const flowEdges = buildEdges(rawE);

      // Highlight affected nodes if provided
      if (highlightIds && highlightIds.size > 0) {
        flowNodes = flowNodes.map((n) => {
          if (highlightIds.has(n.id)) {
            return {
              ...n,
              style: {
                ...n.style,
                boxShadow: "0 0 20px rgba(251,113,133,0.5)",
                border: "2px solid #fb7185",
              },
            };
          }
          return { ...n, style: { ...n.style, opacity: 0.35 } };
        });
      }

      setNodes(flowNodes);
      setEdges(flowEdges);
      setLoaded(true);
    });
  }, [highlightIds]);

  if (!loaded) {
    return (
      <div
        className={`flex items-center justify-center text-gray-500 text-sm ${className}`}
      >
        Loading graph…
      </div>
    );
  }

  return (
    <div className={`${className}`}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
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
  );
}
