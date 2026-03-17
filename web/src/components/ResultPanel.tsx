import type { Evidence, QueryResult, ReasoningStep } from "../types";
import {
  CheckCircle2,
  AlertTriangle,
  Info,
  Sparkles,
  FolderCog,
  BarChart3,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { useState } from "react";

/* ------------------------------------------------------------------ */
/* Confidence badge                                                    */
/* ------------------------------------------------------------------ */
const confidenceConfig: Record<string, { color: string; icon: React.ReactNode }> = {
  high: {
    color: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
    icon: <CheckCircle2 size={14} />,
  },
  medium: {
    color: "text-amber-400 bg-amber-400/10 border-amber-400/20",
    icon: <AlertTriangle size={14} />,
  },
  low: {
    color: "text-gray-400 bg-gray-400/10 border-gray-400/20",
    icon: <Info size={14} />,
  },
};

function ConfidenceBadge({ level }: { level: string }) {
  const cfg = confidenceConfig[level] || confidenceConfig.medium;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 text-xs font-medium rounded-full border ${cfg.color}`}
    >
      {cfg.icon}
      {level}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Evidence row                                                        */
/* ------------------------------------------------------------------ */
function EvidenceRow({ ev }: { ev: Evidence }) {
  const [open, setOpen] = useState(false);
  const expandable = !!ev.code_snippet;

  return (
    <div className="rounded-lg hover:bg-white/[0.03] transition-colors">
      <button
        type="button"
        disabled={!expandable}
        onClick={() => expandable && setOpen((value) => !value)}
        className={`w-full flex items-start gap-3 py-2 px-3 text-left ${
          expandable ? "cursor-pointer" : "cursor-default"
        }`}
      >
        <div className="w-1.5 h-1.5 rounded-full bg-t-primary mt-2 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="text-sm text-gray-300 leading-relaxed">
            {ev.description}
          </p>
          {ev.file_path && (
            <p className="text-xs text-gray-500 font-mono mt-0.5">
              {ev.file_path}
              {ev.function_name ? ` :: ${ev.function_name}` : ""}
              {ev.line_start ? ` L${ev.line_start}` : ""}
            </p>
          )}
        </div>
        {expandable && (
          <span className="text-gray-500 mt-0.5 shrink-0">
            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </span>
        )}
      </button>
      {expandable && open && (
        <div className="mx-3 mb-3 ml-8 rounded-lg border border-t-border/40 bg-gray-950/50 overflow-hidden">
          <div className="px-4 py-2 text-[11px] uppercase tracking-wider text-gray-500 border-b border-t-border/30">
            Source Detail
          </div>
          <pre className="overflow-x-auto px-4 py-3 text-xs leading-6 text-gray-300 font-mono whitespace-pre-wrap">
            {ev.code_snippet}
          </pre>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Reasoning timeline                                                  */
/* ------------------------------------------------------------------ */
function ReasoningTimeline({
  steps,
}: {
  steps: ReasoningStep[];
}) {
  const [open, setOpen] = useState(false);

  if (!steps?.length) return null;

  return (
    <div className="mt-4">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-300 transition-colors"
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        Reasoning Chain ({steps.length} steps)
      </button>

      {open && (
        <div className="mt-3 ml-2 border-l border-t-border pl-4 space-y-4">
          {steps.map((s) => (
            <div key={s.step} className="relative">
              <div className="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full bg-t-primary/60 border-2 border-t-bg" />
              <p className="text-xs font-medium text-t-primary">Step {s.step}</p>
              <p className="text-xs text-gray-500 mt-0.5">{s.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

type UiItem = {
  label: string;
  value: string;
  description: string;
};

type UiBlock = {
  type: "narrative" | "bullets" | "metrics" | "files" | "callout";
  title: string;
  body: string;
  tone: "info" | "success" | "warn";
  items: UiItem[];
};

function isUiItem(value: unknown): value is UiItem {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.label === "string" &&
    typeof candidate.value === "string" &&
    typeof candidate.description === "string"
  );
}

function isUiBlock(value: unknown): value is UiBlock {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.type === "string" &&
    typeof candidate.title === "string" &&
    typeof candidate.body === "string" &&
    typeof candidate.tone === "string" &&
    Array.isArray(candidate.items) &&
    candidate.items.every(isUiItem)
  );
}

function getUiBlocks(result: QueryResult | null): UiBlock[] {
  const raw = result?.metadata?.ui_blocks;
  if (!Array.isArray(raw)) return [];
  return raw.filter(isUiBlock);
}

function blockToneClasses(tone: UiBlock["tone"]) {
  if (tone === "warn") {
    return "border-amber-500/20 bg-amber-500/8";
  }
  if (tone === "success") {
    return "border-emerald-500/20 bg-emerald-500/8";
  }
  return "border-cyan-500/20 bg-cyan-500/8";
}

function BlockHeader({ title, body, icon }: { title: string; body: string; icon: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-start gap-3">
      <div className="mt-0.5 rounded-lg border border-white/10 bg-white/5 p-2 text-gray-300">{icon}</div>
      <div>
        <div className="text-xs uppercase tracking-wider text-gray-500">{title}</div>
        {body && <p className="mt-1 text-sm text-gray-300 leading-relaxed">{body}</p>}
      </div>
    </div>
  );
}

function StructuredBlock({ block }: { block: UiBlock }) {
  const baseClass = `rounded-xl border p-4 ${blockToneClasses(block.tone)}`;

  if (block.type === "metrics") {
    return (
      <div className={baseClass}>
        <BlockHeader title={block.title} body={block.body} icon={<BarChart3 size={16} />} />
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {block.items.map((item) => (
            <div key={`${item.label}-${item.value}`} className="rounded-xl border border-white/10 bg-black/20 p-4">
              <div className="text-[11px] uppercase tracking-wider text-gray-500">{item.label}</div>
              <div className="mt-2 text-lg font-semibold text-white">{item.value}</div>
              <div className="mt-1 text-xs text-gray-400 leading-relaxed">{item.description}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (block.type === "files") {
    return (
      <div className={baseClass}>
      <BlockHeader title={block.title} body={block.body} icon={<FolderCog size={16} />} />
        <div className="space-y-2">
          {block.items.map((item) => (
            <div key={`${item.label}-${item.value}`} className="rounded-lg border border-white/10 bg-black/20 px-3 py-3">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-sm font-medium text-gray-200">{item.label}</div>
                  <div className="mt-1 text-xs font-mono text-gray-500 break-all">{item.value}</div>
                </div>
              </div>
              <div className="mt-2 text-sm text-gray-400 leading-relaxed">{item.description}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (block.type === "bullets") {
    return (
      <div className={baseClass}>
        <BlockHeader title={block.title} body={block.body} icon={<Sparkles size={16} />} />
        <div className="space-y-2">
          {block.items.map((item) => (
            <div key={`${item.label}-${item.value}`} className="flex items-start gap-3 rounded-lg bg-black/15 px-3 py-2.5">
              <div className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-t-primary" />
              <div className="min-w-0 flex-1">
                <div className="text-sm text-gray-200">{item.label}</div>
                <div className="text-xs text-gray-500">{item.value}</div>
                {item.description && <div className="mt-1 text-sm text-gray-400 leading-relaxed">{item.description}</div>}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={baseClass}>
      <BlockHeader title={block.title} body={block.body} icon={block.type === "callout" ? <Info size={16} /> : <Sparkles size={16} />} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main component                                                      */
/* ------------------------------------------------------------------ */
interface Props {
  result: QueryResult | null;
  loading?: boolean;
  className?: string;
}

export default function ResultPanel({ result, loading, className }: Props) {
  if (loading) {
    return (
      <div className={`glass rounded-xl p-6 animate-pulse ${className}`}>
        <div className="h-4 bg-gray-700/40 rounded w-3/4 mb-3" />
        <div className="h-3 bg-gray-700/30 rounded w-1/2 mb-6" />
        <div className="space-y-2">
          <div className="h-3 bg-gray-700/20 rounded" />
          <div className="h-3 bg-gray-700/20 rounded w-5/6" />
          <div className="h-3 bg-gray-700/20 rounded w-2/3" />
        </div>
      </div>
    );
  }

  if (!result) return null;

  const uiBlocks = getUiBlocks(result);

  return (
    <div className={`glass rounded-xl overflow-hidden ${className}`}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-t-border/50">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-sm font-semibold text-gray-200">
            Analysis Result
          </h3>
          <ConfidenceBadge level={result.confidence} />
        </div>
        <p className="text-sm text-gray-400 leading-relaxed">
          {result.conclusion}
        </p>
      </div>

      {uiBlocks.length > 0 && (
        <div className="px-5 py-4 border-b border-t-border/30 space-y-3 bg-white/[0.01]">
          {uiBlocks.map((block, index) => (
            <StructuredBlock key={`${block.title}-${index}`} block={block} />
          ))}
        </div>
      )}

      {/* Evidence */}
      {result.evidence?.length > 0 && (
        <div className="px-5 py-3 border-b border-t-border/30">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
            Evidence
          </p>
          <div className="space-y-0.5">
            {result.evidence.map((ev, i) => (
              <EvidenceRow key={i} ev={ev} />
            ))}
          </div>
        </div>
      )}

      {/* Reasoning */}
      {result.reasoning_chain?.length > 0 && (
        <div className="px-6 py-3">
          <ReasoningTimeline steps={result.reasoning_chain} />
        </div>
      )}
    </div>
  );
}
