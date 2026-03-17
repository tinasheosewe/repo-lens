import { useEffect, useState } from "react";
import { GitPullRequestArrow, Wrench } from "lucide-react";
import { api } from "../api/client";
import type { QueryResult, RepoRefOption, StatusResponse } from "../types";
import ResultPanel from "../components/ResultPanel";

type Tab = "pr-review" | "refactor";

function TabButton({ active, label, onClick, icon: Icon }: { active: boolean; label: string; onClick: () => void; icon: React.ElementType }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-lg transition-all duration-200 ${
        active ? "bg-t-primary/15 text-t-primary border border-t-primary/30" : "text-gray-500 hover:text-gray-300 border border-transparent"
      }`}
    >
      <Icon size={14} />
      {label}
    </button>
  );
}

function getStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function getObjectList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => !!item && typeof item === "object")
    : [];
}

function ReviewSummary({ result }: { result: QueryResult | null }) {
  if (!result) return null;

  const riskLevel = typeof result.metadata?.risk_level === "string" ? result.metadata.risk_level : null;
  const riskReasons = getStringList(result.metadata?.risk_reasons);
  const changedFiles = getStringList(result.metadata?.changed_files);
  const nearbyTests = getStringList(result.metadata?.nearby_tests);
  const hotspotFiles = getStringList(result.metadata?.hotspot_files);
  const testGapFiles = getStringList(result.metadata?.test_gap_files);
  const entryPoints = getObjectList(result.metadata?.impacted_entry_points);
  const criticalSymbols = getObjectList(result.metadata?.critical_symbols);
  const changedSymbolCount = typeof result.metadata?.changed_symbol_count === "number" ? result.metadata.changed_symbol_count : 0;

  const riskTone = riskLevel === "high"
    ? "border-rose-500/25 bg-rose-500/10 text-rose-100"
    : riskLevel === "medium"
      ? "border-amber-500/25 bg-amber-500/10 text-amber-100"
      : "border-emerald-500/25 bg-emerald-500/10 text-emerald-100";

  return (
    <div className="grid gap-4 lg:grid-cols-[1.25fr_1fr]">
      <div className={`rounded-xl border px-5 py-4 ${riskTone}`}>
        <div className="text-xs uppercase tracking-wider opacity-80">Review Summary</div>
        <div className="mt-2 flex items-center gap-3">
          <div className="text-2xl font-semibold">{(riskLevel ?? "unknown").toUpperCase()}</div>
          <div className="text-sm opacity-90">{changedFiles.length} changed file(s), {changedSymbolCount} changed symbol(s)</div>
        </div>
        {!!riskReasons.length && (
          <div className="mt-3 space-y-2 text-sm leading-relaxed">
            {riskReasons.slice(0, 3).map((reason) => (
              <div key={reason}>{reason}</div>
            ))}
          </div>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
        <div className="rounded-xl border border-cyan-500/15 bg-cyan-500/8 px-4 py-4">
          <div className="text-xs uppercase tracking-wider text-cyan-300">Entry Points</div>
          <div className="mt-2 text-2xl font-semibold text-white">{entryPoints.length}</div>
          <div className="mt-1 text-sm text-cyan-100/80">Public or scheduled flows in the review scope</div>
        </div>
        <div className="rounded-xl border border-fuchsia-500/15 bg-fuchsia-500/8 px-4 py-4">
          <div className="text-xs uppercase tracking-wider text-fuchsia-300">Critical Symbols</div>
          <div className="mt-2 text-2xl font-semibold text-white">{criticalSymbols.length}</div>
          <div className="mt-1 text-sm text-fuchsia-100/80">Graph-critical nodes touched or impacted</div>
        </div>
        <div className="rounded-xl border border-amber-500/15 bg-amber-500/8 px-4 py-4">
          <div className="text-xs uppercase tracking-wider text-amber-300">Test Gaps</div>
          <div className="mt-2 text-2xl font-semibold text-white">{testGapFiles.length}</div>
          <div className="mt-1 text-sm text-amber-100/80">Changed files without nearby tests</div>
        </div>
        <div className="rounded-xl border border-emerald-500/15 bg-emerald-500/8 px-4 py-4">
          <div className="text-xs uppercase tracking-wider text-emerald-300">Nearby Tests</div>
          <div className="mt-2 text-2xl font-semibold text-white">{nearbyTests.length}</div>
          <div className="mt-1 text-sm text-emerald-100/80">Candidate tests to run first</div>
        </div>
      </div>

      {(entryPoints.length > 0 || hotspotFiles.length > 0 || criticalSymbols.length > 0) && (
        <div className="glass rounded-xl p-4 space-y-3 lg:col-span-2">
          {entryPoints.length > 0 && (
            <div>
              <div className="text-xs uppercase tracking-wider text-gray-500">Impacted Entry Points</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {entryPoints.slice(0, 6).map((entry, index) => (
                  <span key={`${String(entry.name)}-${index}`} className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-200">
                    {String(entry.kind).toUpperCase()}: {String(entry.name)}
                  </span>
                ))}
              </div>
            </div>
          )}
          {criticalSymbols.length > 0 && (
            <div>
              <div className="text-xs uppercase tracking-wider text-gray-500">Critical Symbols In Scope</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {criticalSymbols.slice(0, 6).map((symbol, index) => (
                  <span key={`${String(symbol.name)}-${index}`} className="rounded-full border border-fuchsia-500/20 bg-fuchsia-500/10 px-3 py-1 text-xs text-fuchsia-200">
                    {String(symbol.name)}
                  </span>
                ))}
              </div>
            </div>
          )}
          {hotspotFiles.length > 0 && (
            <div>
              <div className="text-xs uppercase tracking-wider text-gray-500">Hotspot Files</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {hotspotFiles.slice(0, 6).map((filePath) => (
                  <span key={filePath} className="rounded-full border border-rose-500/20 bg-rose-500/10 px-3 py-1 text-xs text-rose-200">
                    {filePath}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Workflow({ status }: { status: StatusResponse | null }) {
  const [tab, setTab] = useState<Tab>("pr-review");
  const [results, setResults] = useState<Record<Tab, QueryResult | null>>({
    "pr-review": null,
    refactor: null,
  });
  const [loading, setLoading] = useState<Record<Tab, boolean>>({
    "pr-review": false,
    refactor: false,
  });
  const [baseRef, setBaseRef] = useState("");
  const [headRef, setHeadRef] = useState("");
  const [refOptions, setRefOptions] = useState<RepoRefOption[]>([]);
  const [refsLoading, setRefsLoading] = useState(false);
  const [refsError, setRefsError] = useState<string | null>(null);

  useEffect(() => {
    if (tab !== "refactor" || results.refactor) return;
    setLoading((current) => ({ ...current, refactor: true }));
    api.refactorPlan().then((result) => setResults((current) => ({ ...current, refactor: result }))).finally(() => {
      setLoading((current) => ({ ...current, refactor: false }));
    });
  }, [results.refactor, tab]);

  useEffect(() => {
    if (tab !== "pr-review") return;
    setRefsLoading(true);
    setRefsError(null);
    api.repoRefs()
      .then((response) => {
        const options = [...response.branches, ...response.commits];
        setRefOptions(options);

        const defaultBase = response.default_branch || response.branches[0]?.value || "";
        const defaultHead = response.current_ref || response.branches[0]?.value || response.commits[0]?.value || "";
        setBaseRef((current) => current || defaultBase);
        setHeadRef((current) => current || defaultHead);
      })
      .catch((error: Error) => {
        setRefsError(error.message || "Unable to load review refs.");
        setRefOptions([]);
      })
      .finally(() => setRefsLoading(false));
  }, [tab, status?.repo_source, status?.repo_ref]);

  const runReview = async () => {
    if (!baseRef || !headRef) return;
    setLoading((current) => ({ ...current, "pr-review": true }));
    try {
      const payload = {
        base_ref: baseRef.trim() || undefined,
        head_ref: headRef.trim() || undefined,
      };
      const result = await api.prReview(payload);
      setResults((current) => ({ ...current, "pr-review": result }));
    } finally {
      setLoading((current) => ({ ...current, "pr-review": false }));
    }
  };

  const nearbyTests = getStringList(results["pr-review"]?.metadata?.nearby_tests);

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">Workflow</h1>
        <p className="text-sm text-gray-500 mt-1">PR review assistance and refactor planning.</p>
      </div>

      <div className="flex flex-wrap gap-2">
        <TabButton active={tab === "pr-review"} label="PR Review" icon={GitPullRequestArrow} onClick={() => setTab("pr-review")} />
        <TabButton active={tab === "refactor"} label="Refactor Plan" icon={Wrench} onClick={() => setTab("refactor")} />
      </div>

      {tab === "pr-review" && (
        <div className="glass rounded-xl p-4 space-y-3">
          <p className="text-sm text-gray-400 leading-relaxed">
            Review a remote change by comparing two selectable refs. Free-text file and diff entry is disabled.
          </p>
          {refsError && (
            <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
              {refsError}
            </div>
          )}
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1.5 text-sm text-gray-400">
              <span className="text-xs uppercase tracking-wider text-gray-500">Base Ref</span>
              <select
                value={baseRef}
                onChange={(event) => setBaseRef(event.target.value)}
                className="w-full bg-gray-800/50 text-gray-200 px-4 py-3 text-sm rounded-lg border border-t-border focus:border-t-primary/50 focus:outline-none transition-colors"
                disabled={refsLoading || !refOptions.length}
              >
                <option value="">Select base ref</option>
                <optgroup label="Branches">
                  {refOptions.filter((option) => option.kind === "branch").map((option) => (
                    <option key={`base-${option.kind}-${option.value}`} value={option.value}>{option.label}</option>
                  ))}
                </optgroup>
                <optgroup label="Recent Commits">
                  {refOptions.filter((option) => option.kind === "commit").map((option) => (
                    <option key={`base-${option.kind}-${option.value}`} value={option.value}>{option.label}</option>
                  ))}
                </optgroup>
              </select>
            </label>
            <label className="space-y-1.5 text-sm text-gray-400">
              <span className="text-xs uppercase tracking-wider text-gray-500">Head Ref</span>
              <select
                value={headRef}
                onChange={(event) => setHeadRef(event.target.value)}
                className="w-full bg-gray-800/50 text-gray-200 px-4 py-3 text-sm rounded-lg border border-t-border focus:border-t-primary/50 focus:outline-none transition-colors"
                disabled={refsLoading || !refOptions.length}
              >
                <option value="">Select head ref</option>
                <optgroup label="Branches">
                  {refOptions.filter((option) => option.kind === "branch").map((option) => (
                    <option key={`head-${option.kind}-${option.value}`} value={option.value}>{option.label}</option>
                  ))}
                </optgroup>
                <optgroup label="Recent Commits">
                  {refOptions.filter((option) => option.kind === "commit").map((option) => (
                    <option key={`head-${option.kind}-${option.value}`} value={option.value}>{option.label}</option>
                  ))}
                </optgroup>
              </select>
            </label>
          </div>
          <button type="button" onClick={runReview} disabled={loading["pr-review"] || refsLoading || !baseRef || !headRef} className="rounded-lg bg-t-primary px-4 py-2.5 text-sm font-medium text-white hover:bg-t-primary/80 disabled:opacity-40 transition-colors">
            {loading["pr-review"] ? "Reviewing..." : "Run Review"}
          </button>
          {!!nearbyTests.length && (
            <div className="rounded-xl border border-cyan-500/15 bg-cyan-500/8 px-4 py-3 text-sm text-cyan-100">
              Nearby tests: {nearbyTests.join(", ")}
            </div>
          )}
        </div>
      )}

      {tab === "pr-review" && <ReviewSummary result={results["pr-review"]} />}

      <ResultPanel result={results[tab]} loading={loading[tab]} />
    </div>
  );
}