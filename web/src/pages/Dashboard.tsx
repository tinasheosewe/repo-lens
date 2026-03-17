import { useEffect, useState } from "react";
import {
  Box,
  GitBranch,
  FileCode2,
  FunctionSquare,
  Activity,
  Layers,
} from "lucide-react";
import { api } from "../api/client";
import type { GraphStats } from "../types";
import GraphView from "../components/GraphView";

/* ------------------------------------------------------------------ */
/* Stat card                                                           */
/* ------------------------------------------------------------------ */
function StatCard({
  label,
  value,
  icon: Icon,
  accent,
}: {
  label: string;
  value: number;
  icon: React.ElementType;
  accent: string;
}) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    let frame: number;
    const start = performance.now();
    const duration = 900;
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - t, 3);
      setDisplay(Math.round(ease * value));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value]);

  return (
    <div className="glass rounded-xl p-5 group hover:border-t-primary/30 transition-all duration-300">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
          {label}
        </span>
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors duration-300"
          style={{ backgroundColor: `${accent}15`, color: accent }}
        >
          <Icon size={16} />
        </div>
      </div>
      <p className="text-3xl font-bold text-white tabular-nums">{display}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Type-breakdown bar                                                  */
/* ------------------------------------------------------------------ */
function TypeBar({
  data,
}: {
  data: Record<string, number>;
}) {
  const total = Object.values(data).reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  const colors: Record<string, string> = {
    file: "#3b82f6",
    class: "#8b5cf6",
    function: "#10b981",
    method: "#06b6d4",
    calls: "#22d3ee",
    imports: "#818cf8",
    defines: "#475569",
    contains: "#334155",
    inherits: "#a78bfa",
  };

  return (
    <div className="glass rounded-xl p-5">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
        Breakdown
      </p>
      <div className="flex rounded-full overflow-hidden h-2 bg-gray-800 mb-4">
        {Object.entries(data).map(([key, count]) => (
          <div
            key={key}
            className="h-full transition-all duration-700"
            style={{
              width: `${(count / total) * 100}%`,
              backgroundColor: colors[key] || "#475569",
            }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {Object.entries(data).map(([key, count]) => (
          <div key={key} className="flex items-center gap-1.5 text-xs">
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: colors[key] || "#475569" }}
            />
            <span className="text-gray-400">
              {key}{" "}
              <span className="text-gray-500">({count})</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Dashboard page                                                      */
/* ------------------------------------------------------------------ */
export default function Dashboard() {
  const [stats, setStats] = useState<GraphStats | null>(null);

  useEffect(() => {
    api.graphStats().then(setStats);
  }, []);

  if (!stats) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 animate-pulse">
        Loading dashboard…
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">
          Codebase overview at a glance
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Nodes"
          value={stats.total_nodes}
          icon={Box}
          accent="#6366f1"
        />
        <StatCard
          label="Total Edges"
          value={stats.total_edges}
          icon={GitBranch}
          accent="#22d3ee"
        />
        <StatCard
          label="Files"
          value={stats.nodes_by_type.file || 0}
          icon={FileCode2}
          accent="#3b82f6"
        />
        <StatCard
          label="Functions"
          value={
            (stats.nodes_by_type.function || 0) +
            (stats.nodes_by_type.method || 0)
          }
          icon={FunctionSquare}
          accent="#10b981"
        />
      </div>

      {/* Breakdowns */}
      <div className="grid md:grid-cols-2 gap-4">
        <TypeBar data={stats.nodes_by_type} />
        <TypeBar data={stats.edges_by_type} />
      </div>

      {/* Graph */}
      <div className="glass rounded-xl overflow-hidden">
        <div className="flex items-center gap-2 px-5 py-3 border-b border-t-border/50">
          <Layers size={14} className="text-t-primary" />
          <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
            Code Graph
          </span>
        </div>
        <GraphView className="h-[500px]" />
      </div>
    </div>
  );
}
