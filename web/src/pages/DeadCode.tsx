import { Fragment, useEffect, useState } from "react";
import { Trash2, AlertTriangle, ChevronDown, ChevronRight, Info } from "lucide-react";
import { api } from "../api/client";
import type { Evidence, QueryResult } from "../types";

/* ------------------------------------------------------------------ */
/* Severity badge                                                      */
/* ------------------------------------------------------------------ */
function Severity({ level }: { level: string }) {
  const map: Record<string, { cls: string; icon: React.ReactNode }> = {
    high: {
      cls: "text-rose-400 bg-rose-400/10",
      icon: <AlertTriangle size={12} />,
    },
    medium: {
      cls: "text-amber-400 bg-amber-400/10",
      icon: <AlertTriangle size={12} />,
    },
    low: {
      cls: "text-gray-400 bg-gray-400/10",
      icon: <Info size={12} />,
    },
  };
  const cfg = map[level] || map.low;
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${cfg.cls}`}
    >
      {cfg.icon}
      {level}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */
export default function DeadCode() {
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  useEffect(() => {
    api.deadCode().then((r) => {
      setResult(r);
      setLoading(false);
    });
  }, []);

  const items = result?.evidence ?? [];

  const toggleExpanded = (ev: Evidence, index: number) => {
    const key = `${ev.file_path}:${ev.function_name ?? index}`;
    setExpanded((current) => ({
      ...current,
      [key]: !current[key],
    }));
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dead Code</h1>
          <p className="text-sm text-gray-500 mt-1">
            Unreachable functions and methods detected in the codebase
          </p>
        </div>
        {items.length > 0 && (
          <div className="flex items-center gap-2 glass px-4 py-2 rounded-lg">
            <Trash2 size={14} className="text-rose-400" />
            <span className="text-sm font-medium text-gray-300">
              {items.length} issue{items.length !== 1 ? "s" : ""}
            </span>
          </div>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="glass rounded-xl p-8 animate-pulse">
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className="h-10 bg-gray-700/20 rounded-lg"
                style={{ width: `${90 - i * 8}%` }}
              />
            ))}
          </div>
        </div>
      )}

      {/* Result */}
      {result && (
        <>
          {/* Conclusion */}
          <div className="glass rounded-xl p-5">
            <p className="text-sm text-gray-300 leading-relaxed">
              {result.conclusion}
            </p>
          </div>

          {/* Table */}
          <div className="glass rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-t-border/50 text-left">
                  <th className="px-5 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-5 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Location
                  </th>
                  <th className="px-5 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Type
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((ev, i) => {
                  const rowKey = `${ev.file_path}:${ev.function_name ?? i}`;
                  const isExpanded = !!expanded[rowKey];

                  return (
                    <Fragment key={rowKey}>
                      <tr
                        className="border-b border-t-border/20 hover:bg-white/[0.02] transition-colors cursor-pointer"
                        style={{
                          animationDelay: `${i * 30}ms`,
                        }}
                        onClick={() => toggleExpanded(ev, i)}
                      >
                        <td className="px-5 py-3">
                          <div className="flex items-start gap-2">
                            <span className="mt-0.5 text-gray-500">
                              {isExpanded ? (
                                <ChevronDown size={14} />
                              ) : (
                                <ChevronRight size={14} />
                              )}
                            </span>
                            <div>
                              <span className="text-gray-200 font-mono text-xs">
                                {ev.function_name || ev.description}
                              </span>
                              {ev.function_name && (
                                <p className="mt-1 text-[11px] text-gray-500">
                                  {ev.description}
                                </p>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-5 py-3 text-xs text-gray-500 font-mono">
                          {ev.file_path || "—"}
                          {ev.line_start ? `:${ev.line_start}` : ""}
                        </td>
                        <td className="px-5 py-3">
                          <Severity level={ev.function_name ? "medium" : "low"} />
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="border-b border-t-border/20 bg-black/10">
                          <td colSpan={3} className="px-5 pb-4 pt-0">
                            <div className="ml-6 rounded-lg border border-t-border/40 bg-gray-950/50 overflow-hidden">
                              <div className="px-4 py-2 text-[11px] uppercase tracking-wider text-gray-500 border-b border-t-border/30">
                                Function Body
                              </div>
                              <pre className="overflow-x-auto px-4 py-3 text-xs leading-6 text-gray-300 font-mono whitespace-pre-wrap">
                                {ev.code_snippet || "Source snippet unavailable for this function."}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
                {items.length === 0 && (
                  <tr>
                    <td
                      colSpan={3}
                      className="px-5 py-12 text-center text-gray-600"
                    >
                      No dead code detected — nice!
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
