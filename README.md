# RepoLens

RepoLens is a static-analysis platform that parses a repository into a dependency graph
and answers questions from it:

- **Change-impact analysis.** What depends on a symbol, directly and transitively, over
  call and import edges, with direct callers flagged as critical; and for a pull request,
  the blast radius of the files changed between two refs.
- **Hotspot ranking.** Symbols ordered by fan-in and fan-out, a criticality ranking that
  combines betweenness centrality with dependency spread, and files ranked by churn in
  the git history.
- **Architecture Q&A.** An optional LLM layer ("Ask Repo") in which the model answers a
  free-form question by calling graph queries as tools and cites the files it used.
- Also usages, dead code, import cycles, coupled files, paths between two symbols and
  entry flows.

The graph queries involve no model: the same repository gives the same answer, and every
answer carries the files, lines and snippets it rests on. RepoLens runs as a CLI, as a
session-scoped HTTP API that loads a local path or a git URL, and as a React web UI. A
Render blueprint deploys the API and the UI as one service.

In the code the tool is called Trace: the Python package is `trace_engine`, the CLI is
`trace`, and the web UI is titled Trace.

## How it works

```
repo path or git URL
        │
   ingestion        resolve the source (git URLs are shallow-cloned), walk the tree,
        │           detect languages, classify files as source, test, config, ...
        │
    analysis        one parser per language → nodes, edges and unresolved calls;
        │           the graph builder then resolves imports and cross-file calls
        │
 dependency graph   nodes: file, class, function, method
        │           edges: imports, calls, defines, inherits
        │
     query          impact · dependents · usages · dead code · cycles · hotspots ·
        │           coupling · search · paths · entry flows · criticality · PR review
        │
 CLI / API / web    Typer CLI, FastAPI under /api, React + React Flow front end
```

**Graph model** (`models/`). A NetworkX directed multigraph, `CodeGraph` in the code, in
which an edge means "source depends on target", so "what depends on X" is a walk over
incoming edges. Node ids are `path/to/file.py::Class.method`. The graph is saved as JSON
in `.trace/` inside the analysed repository and reused by later queries.

**Parsers** (`analysis/`). Each language implements one small interface and is registered
in a parser registry, which activates parsers from the file extensions and marker files
(`pyproject.toml`, `package.json`, ...) found in the repository.

| Language | Files | Parsed with | Produces |
|---|---|---|---|
| Python | `.py` | standard-library `ast` | classes, functions, methods, decorators; imports, calls, inheritance |
| JavaScript | `.js` `.jsx` `.mjs` `.cjs` | tree-sitter | classes, functions, methods; ES and CommonJS imports and exports, calls |
| TypeScript | `.ts` `.tsx` | tree-sitter (the TSX grammar for `.tsx`) | same as JavaScript |
| HTML | `.html` `.htm` | standard-library `html.parser` | one node per file; linked scripts and stylesheets as imports; ids and classes as metadata |
| CSS | `.css` | regular expressions | one node per file; `@import` as imports; class and id selectors as metadata |

Calls are resolved syntactically: against definitions in the same file, `self.` and
`this.` methods, names bound by an import (followed across files through a module map and
each file's exports), and variables assigned from a constructor (`svc = Service()` then
`svc.run()`). Dynamic dispatch, reflection and anything decided at run time are not seen,
so results such as "dead code" mean "no call edge found" and are reported with a
confidence level.

**Queries** (`query/`). Each analysis is a small class over the graph.

- *Impact* walks incoming call and import edges from a symbol to its transitive
  dependents and labels each one: critical if it calls the symbol directly, high
  otherwise. It reports the counts and the files affected.
- *Hotspots* are symbols whose fan-in or fan-out reaches a threshold, ordered by their
  sum. *Criticality* ranks symbols by a weighted score: betweenness centrality (0.45),
  number of transitive dependents (0.30), fan-in (0.15) and fan-out (0.10), each
  normalised to the largest value in the graph. *History drift* ranks files by the number
  of commits that touched them in the last year and lists the pairs that change together.
- *PR review* takes the files changed between two refs (`git diff --name-only`), expands
  them to the symbols they define and everything that depends on those, and derives the
  entry points affected, the critical symbols in scope, nearby tests and a risk level.
- The rest: dependents and usages, dead code, import cycles, coupled files, name search,
  paths between two symbols, stale modules, entry flows from routes, jobs and CLI
  commands, concept search and an onboarding summary.

**Evidence** (`models/evidence.py`). Every query returns the same `QueryResult`: a
conclusion, a list of evidence items (file, symbol, line range, code snippet,
description), the reasoning steps, a confidence level and the ids of the affected nodes.
The CLI renders it as tables; the API returns it as JSON.

**API sessions** (`api/server.py`, `ingestion/source_resolver.py`). The server keeps one
analysed repository per client session, identified by an `X-Trace-Session` header, so
several people can look at different repositories at once. A session can load a local
path or a git URL with an optional branch or tag. Remote repositories are
shallow-cloned into a cache under `~/.trace/remote_repos`, rejected above a size limit
(250 MB by default) and deleted when the session expires (one hour without requests by
default).

## Ask Repo: the question-answering layer

`POST /api/ask` and the Discovery page take a free-form architecture question.

With `OPENAI_API_KEY` (or `TRACE_LLM_API_KEY`) set, the question goes to a chat-completions
model together with seven tool definitions, and the model decides which of them to call.
Each call runs a query on the graph and returns a compact JSON result:

| Tool | What it runs |
|---|---|
| `get_repo_overview` | onboarding summary: subsystems and hotspot count |
| `get_critical_symbols` | the criticality ranking |
| `find_concept_matches` | concept search over symbol names, paths and decorators |
| `trace_entry_points` | entry flows from routes, jobs or CLI commands |
| `get_history_drift` | churn and co-change from git history |
| `inspect_file` | one file: its symbols, import fan-in and fan-out, first lines |
| `search_symbols` | substring search over symbol names and paths |

The exchange is capped at six model calls, tool rounds included, and the final answer has
to match a fixed JSON schema: a summary, a confidence level, reasoning steps, UI blocks
for the front end, and citations. Each cited file is matched to an evidence item that a
tool returned, or else attached with the first lines of that file. The response also
lists the tool calls that were made (`metadata.tool_trace`).

What this does not do: the model is instructed, not forced, to call tools before it
answers; the impact, dead-code, cycle and path queries are not among the tools; and the
text of the answer is not checked against the tool results. The confidence level is the
model's own.

Without a key, or if the call fails, the endpoint returns an answer assembled from three
deterministic queries (onboarding summary, concept search, criticality) and says so.

`TRACE_LLM_MODEL` selects the model (default `gpt-4.1-mini`) and `TRACE_LLM_BASE_URL`
points the client at another OpenAI-compatible endpoint; it has to support tool calls and
`json_schema` response formats. Everything else in RepoLens runs without an API key.

## Install

Python 3.11+ and git. Node.js 18+ for the web UI.

```bash
python3 -m venv .venv                # with a Python 3.11+ interpreter
source .venv/bin/activate
pip install -e ".[web,dev]"
```

## CLI

Run `trace` from the activated virtualenv (macOS ships an unrelated `/usr/bin/trace`).
`ingest` builds the graph; the query commands read it, so run `ingest` again after the
code changes. The query commands take a local path; `serve` also accepts a git URL.

```bash
trace ingest path/to/repo            # build the dependency graph
trace impact some_function --repo path/to/repo
trace deps SomeClass --repo path/to/repo
trace usages SomeClass --repo path/to/repo
trace dead-code --repo path/to/repo
trace endpoints --repo path/to/repo
trace cycles --repo path/to/repo
trace hotspots --repo path/to/repo --threshold 3
trace search "auth" --repo path/to/repo
trace navigate login_view save_user --repo path/to/repo
trace serve path/to/repo             # API on http://127.0.0.1:8000
```

To try it without a project of your own, use the small fixture the tests run on:

```bash
trace ingest tests/fixtures/sample_project
trace impact authenticate --repo tests/fixtures/sample_project
trace hotspots --repo tests/fixtures/sample_project --threshold 2
trace dead-code --repo tests/fixtures/sample_project
```

The criticality ranking, history drift, PR review, entry flows and Ask Repo are available
through the API and the web UI, not the CLI.

## Web UI

```bash
cd web && npm install && cd ..
./start.sh [repo-path-or-git-url]
```

`start.sh` starts the FastAPI backend on port 8000 and the Vite dev server on
http://127.0.0.1:5173. It expects the virtualenv from the install step, and it first kills
whatever is listening on those two ports. With no argument, sessions start on a small
public Flask application (`miguelgrinberg/flasky`), which is cloned on first use, so there
is something to look at immediately.

Pages: About (load a repository, see what is supported), Discovery (onboarding summary,
concept search, Ask Repo, history drift), Dashboard (graph overview), Audit (stale modules,
criticality), Flows (entry points and call paths), Workflow (PR review, refactor
candidates), Impact Analysis, Dead Code, Dependencies (cycles, hotspots, coupling) and
Explorer (paths between two symbols).

## Deployment

`trace serve`, or `uvicorn trace_engine.api.server:create_app --factory`, serves the API
under `/api` and, once the front end has been built (`cd web && npm run build`), the
files in `web/dist` from the same process. The server looks for `web/dist` next to the
source tree, which is where an editable install (`pip install -e`) leaves it. That is the
whole deployment unit.

`render.yaml` is a Render blueprint for it: one Python web service whose build step
installs the package and builds the front end, started with uvicorn on `$PORT`, health
checked on `/api/health`, with `TRACE_REPO_PATH` set to the public demo repository so that
every new session has something loaded, and `OPENAI_API_KEY` declared as an optional
secret for Ask Repo. [RENDER_DEPLOY.md](RENDER_DEPLOY.md) has the steps.

The API has no authentication and no user accounts: a session is whatever sends a session
header, and it can load any git URL the server can reach or any directory on the server.
Treat a deployment as a public demo on a host that holds nothing else. Symlinks inside a
repository are skipped, code snippets are read only from inside the repository being
analysed, and browsers are allowed to call the API only from the local Vite dev server
unless `TRACE_CORS_ORIGINS` says otherwise.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `TRACE_REPO_PATH` | `https://github.com/miguelgrinberg/flasky.git` | Path or git URL that new server sessions start on |
| `TRACE_SESSION_TTL_SECONDS` | `3600` | Idle time after which a session and its clone are dropped |
| `TRACE_SESSION_SWEEP_INTERVAL_SECONDS` | `60` | How often expired sessions are swept |
| `TRACE_MAX_CLONE_BYTES` | `262144000` | Size limit for a cloned repository |
| `TRACE_CORS_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` | Comma-separated origins allowed to call the API from a browser |
| `OPENAI_API_KEY` / `TRACE_LLM_API_KEY` | unset | Enables the LLM path of Ask Repo |
| `TRACE_LLM_MODEL`, `TRACE_LLM_BASE_URL` | `gpt-4.1-mini`, `https://api.openai.com/v1` | Model and endpoint for Ask Repo |

`start.sh` also reads `.env` and `.env.local`, and accepts `BACKEND_HOST`, `BACKEND_PORT`,
`FRONTEND_HOST` and `FRONTEND_PORT`. The dev front end looks for the API on
`127.0.0.1:8000`, and the API accepts browser calls from port 5173 only, so moving either
port needs two more settings: `VITE_API_BASE` (for example `http://127.0.0.1:9000/api`)
and `TRACE_CORS_ORIGINS` (the front end's new origin). `VITE_API_BASE` is also read by
`npm run build`, for a front end served from a different origin than the API.

## Limits

- Resolution is syntactic, as described above, and symbols are looked up by name: when
  several share a name, a query uses the first match.
- Python gets the fullest treatment. JavaScript and TypeScript have no inheritance edges,
  and HTML and CSS contribute file-level nodes only.
- Remote repositories are shallow clones, so the history-based results (history drift,
  PR review) see only the commits that have been fetched: one at first, more once the
  refs under review are fetched.
- Endpoint and entry-point detection is by decorator and naming convention
  (`@app.route`, `@router.get`, task and CLI decorators, `main`).

## Tests

```bash
pytest
```

The suite covers the parsers, the classifier, the graph and graph builder, the query
engines, storage and output, the source resolver and the API. It needs git on the `PATH`
but no network: remote sources are stood in for by local bare repositories, and the LLM
client is replaced by a fake.

The GitHub Actions workflow in `.github/workflows/ci.yml` runs on pushes to `main` and on
pull requests: `pip install -e ".[web,dev]"` and `pytest -q` on Python 3.12, and `npm ci` and
`npm run build` in `web/` on Node 20.

## Layout

```
src/trace_engine/
├── core.py           # Trace: the facade used by the CLI and the API
├── ingestion/        # source resolver (clone, cache), loader, file classifier
├── analysis/         # parser interface and registry, one parser per language, graph builder
├── models/           # graph nodes and edges, CodeGraph, QueryResult and Evidence
├── query/            # the analyses, snippet resolver, LLM client
├── storage/          # JSON graph repository
├── output/           # Rich formatter for the CLI
├── cli/              # Typer commands
└── api/              # FastAPI application
tests/                # pytest suite and a sample project fixture
web/                  # React front end (Vite, TypeScript, Tailwind, React Flow)
render.yaml           # Render blueprint (see RENDER_DEPLOY.md)
```
