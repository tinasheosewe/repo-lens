import { useEffect, useState } from "react";
import { GitPullRequestArrow, Wrench } from "lucide-react";
import { api } from "../api/client";
import type { QueryResult } from "../types";
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

export default function Workflow() {
  const [tab, setTab] = useState<Tab>("pr-review");
  const [results, setResults] = useState<Record<Tab, QueryResult | null>>({
    "pr-review": null,
    refactor: null,
  });
  const [loading, setLoading] = useState<Record<Tab, boolean>>({
    "pr-review": false,
    refactor: false,
  });
  const [changedFiles, setChangedFiles] = useState("");
  const [baseRef, setBaseRef] = useState("");
  const [headRef, setHeadRef] = useState("");
  const [diffText, setDiffText] = useState("");

  useEffect(() => {
    if (tab !== "refactor" || results.refactor) return;
    setLoading((current) => ({ ...current, refactor: true }));
    api.refactorPlan().then((result) => setResults((current) => ({ ...current, refactor: result }))).finally(() => {
      setLoading((current) => ({ ...current, refactor: false }));
    });
  }, [results.refactor, tab]);

  const runReview = async () => {
    setLoading((current) => ({ ...current, "pr-review": true }));
    try {
      const payload = {
        changed_files: changedFiles.split(/\r?\n/).map((value) => value.trim()).filter(Boolean),
        diff_text: diffText.trim() || undefined,
        base_ref: baseRef.trim() || undefined,
        head_ref: headRef.trim() || undefined,
      };
      const result = await api.prReview(payload);
      setResults((current) => ({ ...current, "pr-review": result }));
    } finally {
      setLoading((current) => ({ ...current, "pr-review": false }));
    }
  };

  const nearbyTests = Array.isArray(results["pr-review"]?.metadata?.nearby_tests)
    ? (results["pr-review"]?.metadata?.nearby_tests as string[])
    : [];

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
          <textarea
            value={changedFiles}
            onChange={(event) => setChangedFiles(event.target.value)}
            placeholder="Paste changed files, one path per line. Leave blank to let Trace inspect the latest diff."
            className="w-full min-h-[120px] bg-gray-800/50 text-gray-200 placeholder:text-gray-600 px-4 py-3 text-sm rounded-lg border border-t-border focus:border-t-primary/50 focus:outline-none transition-colors"
          />
          <textarea
            value={diffText}
            onChange={(event) => setDiffText(event.target.value)}
            placeholder="Optional unified diff text if you want Trace to parse files from a pasted patch."
            className="w-full min-h-[120px] bg-gray-800/50 text-gray-200 placeholder:text-gray-600 px-4 py-3 text-sm rounded-lg border border-t-border focus:border-t-primary/50 focus:outline-none transition-colors"
          />
          <div className="grid gap-3 md:grid-cols-2">
            <input value={baseRef} onChange={(event) => setBaseRef(event.target.value)} placeholder="Base ref (optional)" className="w-full bg-gray-800/50 text-gray-200 placeholder:text-gray-600 px-4 py-3 text-sm rounded-lg border border-t-border focus:border-t-primary/50 focus:outline-none transition-colors" />
            <input value={headRef} onChange={(event) => setHeadRef(event.target.value)} placeholder="Head ref (optional)" className="w-full bg-gray-800/50 text-gray-200 placeholder:text-gray-600 px-4 py-3 text-sm rounded-lg border border-t-border focus:border-t-primary/50 focus:outline-none transition-colors" />
          </div>
          <button type="button" onClick={runReview} disabled={loading["pr-review"]} className="rounded-lg bg-t-primary px-4 py-2.5 text-sm font-medium text-white hover:bg-t-primary/80 disabled:opacity-40 transition-colors">
            {loading["pr-review"] ? "Reviewing..." : "Run Review"}
          </button>
          {!!nearbyTests.length && (
            <div className="rounded-xl border border-cyan-500/15 bg-cyan-500/8 px-4 py-3 text-sm text-cyan-100">
              Nearby tests: {nearbyTests.join(", ")}
            </div>
          )}
        </div>
      )}

      <ResultPanel result={results[tab]} loading={loading[tab]} />
    </div>
  );
}