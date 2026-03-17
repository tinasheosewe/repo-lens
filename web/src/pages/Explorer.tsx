import { useRef, useState } from "react";
import { Route, ArrowRight } from "lucide-react";
import { api } from "../api/client";
import type { Evidence, QueryResult } from "../types";
import ResultPanel from "../components/ResultPanel";
import SymbolPicker, { getEvidenceLabel } from "../components/SymbolPicker";

interface PathNodeDetail {
  id: string;
  name: string;
  node_type: string;
  file_path: string;
  line_start: number | null;
  line_end: number | null;
  code_snippet: string | null;
  step: number;
  step_count: number;
}

function isPathNodeDetail(value: unknown): value is PathNodeDetail {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.id === "string" &&
    typeof candidate.name === "string" &&
    typeof candidate.file_path === "string" &&
    typeof candidate.step === "number" &&
    typeof candidate.step_count === "number"
  );
}

function getPathDetails(result: QueryResult | null): PathNodeDetail[][] {
  const raw = result?.metadata?.path_details;
  if (!Array.isArray(raw)) return [];

  return raw
    .map((path) =>
      Array.isArray(path) ? path.filter(isPathNodeDetail) : [],
    )
    .filter((path) => path.length > 0);
}

function PathNodeCard({
  node,
  selected,
  onSelect,
}: {
  node: PathNodeDetail;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-[320px] shrink-0 rounded-xl border overflow-hidden text-left transition-colors md:w-[360px] ${
        selected
          ? "border-cyan-400/40 bg-cyan-500/10"
          : "border-t-border/40 bg-gray-950/35 hover:border-cyan-500/25 hover:bg-gray-950/55"
      }`}
    >
      <div className="px-4 py-3">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-cyan-500/15 text-[11px] font-semibold text-cyan-300">
            {node.step}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-xs uppercase tracking-wider text-gray-500">{node.node_type}</div>
            <div className="text-sm font-medium text-gray-200 break-words">{node.name}</div>
            <div className="mt-1 text-[11px] font-mono text-gray-500 break-all">
              {node.file_path}
              {node.line_start ? `:${node.line_start}` : ""}
            </div>
          </div>
        </div>
      </div>
      <div className="border-t border-t-border/30 px-4 py-2 text-[11px] text-gray-500">
        {node.code_snippet ? "Click to inspect source below" : "No source snippet available"}
      </div>
    </button>
  );
}

function PathResultPanel({ result }: { result: QueryResult }) {
  const pathDetails = getPathDetails(result);
  const [selectedNodes, setSelectedNodes] = useState<Record<number, string>>({});

  if (!pathDetails.length) {
    return <ResultPanel result={result} />;
  }

  return (
    <div className="glass rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-t-border/50">
        <h3 className="text-sm font-semibold text-gray-200">Resolved Paths</h3>
        <p className="mt-1 text-sm text-gray-400 leading-relaxed">{result.conclusion}</p>
        <p className="mt-3 text-xs text-gray-500">
          Read each lane from left to right. Each card is one symbol in the call chain, and the arrows show the order of execution through the path.
        </p>
      </div>

      <div className="px-5 py-5 space-y-4">
        {pathDetails.map((path, pathIndex) => (
          <div key={path[0]?.id ?? pathIndex} className="rounded-xl border border-cyan-500/10 bg-cyan-500/5 p-4">
            {(() => {
              const selectedNode = path.find((node) => node.id === selectedNodes[pathIndex]) ?? path[0];

              return (
                <>
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-wider text-cyan-300">Path {pathIndex + 1}</div>
                <div className="text-sm text-gray-400">
                  {path.length} step{path.length === 1 ? "" : "s"}
                </div>
              </div>
              <div className="text-xs text-gray-500">
                {path.map((node) => node.name).join(" -> ")}
              </div>
            </div>

            <div className="overflow-x-auto pb-3">
              <div className="flex min-w-max items-stretch gap-3">
                {path.map((node, index) => (
                  <div key={node.id} className="flex items-center gap-3">
                    <PathNodeCard
                      node={node}
                      selected={selectedNode.id === node.id}
                      onSelect={() =>
                        setSelectedNodes((current) => ({
                          ...current,
                          [pathIndex]: node.id,
                        }))
                      }
                    />
                  {index < path.length - 1 && (
                      <div className="flex shrink-0 items-center justify-center text-cyan-300/70 px-1">
                        <ArrowRight size={18} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-t-border/40 bg-gray-950/45 overflow-hidden">
              <div className="px-4 py-3 border-b border-t-border/30">
                <div className="text-[11px] uppercase tracking-wider text-gray-500">Selected Step</div>
                <div className="mt-1 flex items-center gap-2 text-sm text-gray-200">
                  <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-cyan-500/15 text-[11px] font-semibold text-cyan-300">
                    {selectedNode.step}
                  </span>
                  <span>{selectedNode.name}</span>
                </div>
                <div className="mt-1 text-[11px] font-mono text-gray-500 break-all">
                  {selectedNode.file_path}
                  {selectedNode.line_start ? `:${selectedNode.line_start}` : ""}
                </div>
              </div>

              {selectedNode.code_snippet ? (
                <pre className="overflow-x-auto px-4 py-4 whitespace-pre-wrap text-xs leading-6 text-gray-300 font-mono">
                  {selectedNode.code_snippet}
                </pre>
              ) : (
                <div className="px-4 py-4 text-sm text-gray-500">
                  No source snippet is available for this node.
                </div>
              )}
            </div>
                </>
              );
            })()}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Explorer() {
  /* ----- path-finding state ----- */
  const [pathFrom, setPathFrom] = useState("");
  const [pathTo, setPathTo] = useState("");
  const [selectedFrom, setSelectedFrom] = useState<Evidence | null>(null);
  const [selectedTo, setSelectedTo] = useState<Evidence | null>(null);
  const [pathResult, setPathResult] = useState<QueryResult | null>(null);
  const [pathLoading, setPathLoading] = useState(false);
  const toInputRef = useRef<HTMLInputElement>(null);

  const matchesSelectedValue = (selected: Evidence | null, value: string) => {
    return !!selected && getEvidenceLabel(selected) === value;
  };

  const runPath = async () => {
    if (!selectedFrom || !selectedTo) return;

    const f = getEvidenceLabel(selectedFrom);
    const t = getEvidenceLabel(selectedTo);
    setPathLoading(true);
    try {
      setPathResult(await api.path(f, t));
    } finally {
      setPathLoading(false);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Explorer</h1>
        <p className="text-sm text-gray-500 mt-1">
          Choose a source and target symbol, then inspect the connection path between them
        </p>
      </div>

      {/* -------- Path finding section -------- */}
      <section className="space-y-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-300">
          <Route size={15} className="text-cyan-400" />
          Path Finder
        </h2>

        <div className="glass rounded-xl p-4">
          <div className="mb-4 rounded-xl border border-cyan-500/15 bg-cyan-500/5 px-4 py-3 text-sm text-gray-300">
            Type in either field to search symbols live. Use arrow keys to move through matches and press Enter to select a symbol for that side of the path.
          </div>

          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_auto] md:items-start">
            <SymbolPicker
              label="From"
              value={pathFrom}
              selected={selectedFrom}
              placeholder="Search source symbol..."
              onValueChange={(value) => {
                setPathFrom(value);
                if (!matchesSelectedValue(selectedFrom, value)) {
                  setSelectedFrom(null);
                }
                setPathResult(null);
              }}
              onSelect={(ev) => {
                const label = getEvidenceLabel(ev);
                setPathFrom(label);
                setSelectedFrom(ev);
                setPathResult(null);
                window.setTimeout(() => toInputRef.current?.focus(), 0);
              }}
            />

            <div className="hidden md:flex h-full items-center justify-center pt-8">
              <ArrowRight size={18} className="text-gray-600 shrink-0" />
            </div>

            <SymbolPicker
              label="To"
              value={pathTo}
              selected={selectedTo}
              inputRef={toInputRef}
              placeholder="Search target symbol..."
              onValueChange={(value) => {
                setPathTo(value);
                if (!matchesSelectedValue(selectedTo, value)) {
                  setSelectedTo(null);
                }
                setPathResult(null);
              }}
              onSelect={(ev) => {
                const label = getEvidenceLabel(ev);
                setPathTo(label);
                setSelectedTo(ev);
                setPathResult(null);
              }}
            />

            <div className="md:pt-8">
              <button
                onClick={runPath}
                disabled={pathLoading || !selectedFrom || !selectedTo}
                className="w-full bg-cyan-500 hover:bg-cyan-500/80 disabled:opacity-40 text-white text-xs font-medium px-4 py-2.5 rounded-lg transition-colors shrink-0 md:w-auto"
              >
                Find Path
              </button>
            </div>
          </div>
        </div>

        {pathLoading ? (
          <ResultPanel result={null} loading />
        ) : pathResult ? (
          <PathResultPanel result={pathResult} />
        ) : null}
      </section>
    </div>
  );
}
