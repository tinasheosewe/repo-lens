import { useEffect, useState } from "react";
import { BookOpen, FolderSearch, ShieldAlert, CheckCircle2 } from "lucide-react";
import { api } from "../api/client";
import type { AboutResponse, RepoSupportResponse, StatusResponse } from "../types";

const DEFAULT_REMOTE_SOURCE = "https://github.com/tinasheosewe/RepoLens.git";

interface Props {
  status: StatusResponse | null;
  onRepoLoaded: (status: StatusResponse) => void;
}

export default function About({ status, onRepoLoaded }: Props) {
  const [about, setAbout] = useState<AboutResponse | null>(null);
  const [repoPath, setRepoPath] = useState(status?.repo_source ?? DEFAULT_REMOTE_SOURCE);
  const [repoRef, setRepoRef] = useState(status?.repo_ref ?? "");
  const [support, setSupport] = useState<RepoSupportResponse | null>(null);
  const [checking, setChecking] = useState(false);
  const [loadingRepo, setLoadingRepo] = useState(false);
  const [loadingStage, setLoadingStage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.about().then(setAbout).catch(() => setAbout(null));
  }, []);

  useEffect(() => {
    setRepoPath(status?.repo_source ?? DEFAULT_REMOTE_SOURCE);
    setRepoRef(status?.repo_ref ?? "");
  }, [status?.repo_ref, status?.repo_source]);

  const checkSupport = async () => {
    const source = repoPath.trim();
    const ref = repoRef.trim() || undefined;
    if (!source) return;
    setChecking(true);
    setLoadingStage("Inspecting repository support...");
    setError(null);
    try {
      const result = await api.repoSupport(source, ref);
      setSupport(result);
    } catch (err) {
      setSupport(null);
      setError(err instanceof Error ? err.message : "Unable to inspect repository.");
    } finally {
      setChecking(false);
      setLoadingStage(null);
    }
  };

  const loadRepo = async () => {
    const source = repoPath.trim();
    const ref = repoRef.trim() || undefined;
    if (!source) return;
    setLoadingRepo(true);
    setError(null);
    try {
      setLoadingStage("Checking repository support...");
      const checked = support?.source === source && (support.ref ?? "") === (ref ?? "")
        ? support
        : await api.repoSupport(source, ref);
      setSupport(checked);
      if (!checked.supported) {
        setError(checked.reason);
        return;
      }
      setLoadingStage(
        checked.source_type === "remote"
          ? `Cloning ${checked.ref ? `ref ${checked.ref}` : "default branch"} and building graph...`
          : "Loading local repository and building graph...",
      );
      const nextStatus = await api.ingest(source, ref);
      onRepoLoaded(nextStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load repository.");
    } finally {
      setLoadingRepo(false);
      setLoadingStage(null);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">About</h1>
        <p className="text-sm text-gray-500 mt-1">
          What Trace supports today, and which remote repositories you can point it at.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <section className="glass rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-2 text-gray-200">
            <BookOpen size={16} className="text-t-primary" />
            <h2 className="text-sm font-semibold uppercase tracking-wider">Support</h2>
          </div>

          <p className="text-sm text-gray-300 leading-relaxed">
            {about?.summary ?? "Trace inspects supported source files and builds a graph for impact, dependency, navigation, and dead-code analysis."}
          </p>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-t-border/40 bg-gray-950/35 p-4">
              <div className="text-xs uppercase tracking-wider text-gray-500 mb-2">Supported Languages</div>
              <div className="flex flex-wrap gap-2">
                {(about?.supported_languages ?? ["Python"]).map((language) => (
                  <span key={language} className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-300">
                    {language}
                  </span>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-t-border/40 bg-gray-950/35 p-4">
              <div className="text-xs uppercase tracking-wider text-gray-500 mb-2">Supported Files</div>
              <div className="flex flex-wrap gap-2">
                {(about?.supported_extensions ?? [".py"]).map((ext) => (
                  <span key={ext} className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-300 font-mono">
                    {ext}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-amber-500/15 bg-amber-500/5 p-4 text-sm text-gray-300 leading-relaxed">
            <div className="flex items-center gap-2 text-amber-300 mb-2">
              <ShieldAlert size={15} />
              <span className="font-medium">Current boundary</span>
            </div>
            Trace now accepts Git repository URLs and clones them into a managed cache before analysis. It parses Python, JavaScript, TypeScript, HTML, and CSS, and rejects repositories that do not contain supported source files instead of pretending they loaded successfully.
          </div>
        </section>

        <section className="glass rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-2 text-gray-200">
            <FolderSearch size={16} className="text-t-primary" />
            <h2 className="text-sm font-semibold uppercase tracking-wider">Load Repository</h2>
          </div>

          <div className="space-y-3">
            <label className="text-xs uppercase tracking-wider text-gray-500">Git Repository URL</label>
            <input
              type="text"
              value={repoPath}
              onChange={(e) => {
                setRepoPath(e.target.value);
                setSupport(null);
                setError(null);
              }}
              placeholder={DEFAULT_REMOTE_SOURCE}
              className="w-full bg-gray-800/50 text-gray-200 placeholder:text-gray-600 px-4 py-3 text-sm rounded-lg border border-t-border focus:border-t-primary/50 focus:outline-none transition-colors"
            />

            <label className="text-xs uppercase tracking-wider text-gray-500">Branch / Tag / Ref</label>
            <input
              type="text"
              value={repoRef}
              onChange={(e) => {
                setRepoRef(e.target.value);
                setSupport(null);
                setError(null);
              }}
              placeholder="main"
              className="w-full bg-gray-800/50 text-gray-200 placeholder:text-gray-600 px-4 py-3 text-sm rounded-lg border border-t-border focus:border-t-primary/50 focus:outline-none transition-colors"
            />
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={checkSupport}
              disabled={checking || !repoPath.trim()}
              className="flex-1 rounded-lg border border-t-border bg-gray-900/50 px-4 py-2.5 text-sm text-gray-200 hover:bg-white/[0.03] disabled:opacity-40 transition-colors"
            >
              {checking ? "Checking..." : "Check Support"}
            </button>
            <button
              type="button"
              onClick={loadRepo}
              disabled={loadingRepo || !repoPath.trim()}
              className="flex-1 rounded-lg bg-t-primary px-4 py-2.5 text-sm font-medium text-white hover:bg-t-primary/80 disabled:opacity-40 transition-colors"
            >
              {loadingRepo ? "Loading..." : "Load Repo"}
            </button>
          </div>

          {loadingStage && (
            <div className="rounded-xl border border-cyan-500/15 bg-cyan-500/8 px-4 py-3 text-sm text-cyan-100">
              {loadingStage}
            </div>
          )}

          {error && (
            <div className="rounded-xl border border-rose-500/15 bg-rose-500/8 px-4 py-3 text-sm text-rose-200">
              {error}
            </div>
          )}

          {support && (
            <div className={`rounded-xl border px-4 py-4 text-sm ${support.supported ? "border-emerald-500/15 bg-emerald-500/8 text-emerald-200" : "border-amber-500/15 bg-amber-500/8 text-amber-200"}`}>
              <div className="flex items-center gap-2 mb-2">
                {support.supported ? <CheckCircle2 size={15} /> : <ShieldAlert size={15} />}
                <span className="font-medium">{support.supported ? "Supported" : "Unsupported"}</span>
              </div>
              <p className="leading-relaxed">{support.reason}</p>
              <div className="mt-3 text-xs text-current/80">
                Source type: {support.source_type}
              </div>
              {support.ref && (
                <div className="mt-2 text-xs text-current/80">
                  Ref: {support.ref}
                </div>
              )}
              <div className="mt-3 text-xs text-current/80">
                {support.supported_file_count} supported file(s) found
              </div>
              {!!support.detected_languages.length && (
                <div className="mt-3">
                  <div className="text-[11px] uppercase tracking-wider text-current/70 mb-2">
                    Detected Languages
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {support.detected_languages.map((language) => (
                      <span key={language} className="rounded-full border border-current/15 px-2 py-0.5 text-[11px]">
                        {language}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {!!support.active_extensions.length && (
                <div className="mt-3">
                  <div className="text-[11px] uppercase tracking-wider text-current/70 mb-2">
                    Active Parser Extensions
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {support.active_extensions.map((ext) => (
                      <span key={ext} className="rounded-full border border-current/15 px-2 py-0.5 text-[11px] font-mono">
                        {ext}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <div className="mt-2 text-[11px] text-current/80 break-all">
                Cached checkout: {support.resolved_path}
              </div>
              {!!support.detected_extensions.length && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {support.detected_extensions.map((ext) => (
                    <span key={ext} className="rounded-full border border-current/15 px-2 py-0.5 text-[11px] font-mono">
                      {ext}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {status?.loaded && (
            <div className="rounded-xl border border-t-border/40 bg-gray-950/35 px-4 py-3 text-sm text-gray-300">
              Current source: <span className="font-mono text-gray-400 break-all">{status.repo_source}</span>
              {status.repo_ref && (
                <div className="mt-2 text-xs text-gray-500">
                  Ref: <span className="font-mono">{status.repo_ref}</span>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}