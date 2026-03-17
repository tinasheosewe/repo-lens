from __future__ import annotations

import math
import re
import subprocess
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import networkx as nx

from trace_engine.ingestion.loader import RepoLoader
from trace_engine.models.code_graph import CodeGraph
from trace_engine.models.evidence import Confidence, Evidence, QueryResult, ReasoningStep
from trace_engine.models.graph import EdgeType, GraphNode, NodeType

from .dependencies import DependencyAnalyzer
from .llm import LLMConfigurationError, TraceLLMClient
from .snippets import QuerySnippetResolver


class AdvancedAnalyzer:
    """Higher-level repo exploration, auditing, and workflow analyses."""

    _FLOW_EDGES = {EdgeType.CALLS}
    _PUBLIC_ENDPOINT_DECORATORS = {
        "app.route", "app.get", "app.post", "app.put", "app.delete", "app.patch",
        "router.get", "router.post", "router.put", "router.delete", "router.patch",
    }
    _JOB_DECORATOR_MARKERS = ("task", "shared_task", "celery", "job")
    _JOB_NAME_MARKERS = ("job", "task", "worker", "cron", "schedule")
    _CLI_DECORATOR_MARKERS = ("app.command", "typer.command", "click.command")
    _CLI_NAME_MARKERS = {"main", "cli", "run"}
    _ROUTE_NAME_MARKERS = ("get_", "create_", "update_", "delete_", "list_", "post_")
    _SOURCE_CATEGORIES = {"source"}
    _LEGACY_CONCEPTS: dict[str, tuple[str, ...]] = {
        "validator": ("validate", "validator", "schema", "clean"),
        "service": ("service", "manager"),
        "model": ("model", "entity", "dto"),
        "controller": ("controller", "route", "handler", "endpoint", "view"),
        "client": ("client", "gateway", "adapter", "connector"),
        "repository": ("repository", "repo", "store", "dao"),
        "config": ("config", "settings", "conf"),
        "test": ("test", "pytest", "fixture"),
    }

    def __init__(
        self,
        graph: CodeGraph,
        repo_root: str | Path | None = None,
    ) -> None:
        self._graph = graph
        self._repo_root = Path(repo_root).resolve() if repo_root else None
        self._snippets = QuerySnippetResolver(graph, repo_root=repo_root)

    def find_stale_modules(self) -> QueryResult:
        stale: list[Evidence] = []
        affected: list[str] = []

        for node in self._source_files():
            imports_in = self._graph.get_edges_to(node.id, {EdgeType.IMPORTS})
            external_callers = [
                edge
                for member in self._graph.get_nodes_by_file(node.file_path)
                if member.id != node.id
                for edge in self._graph.get_edges_to(member.id, {EdgeType.CALLS})
                if self._graph.get_node(edge.source_id) is not None
                and self._graph.get_node(edge.source_id).file_path != node.file_path
            ]
            has_entry = self._file_contains_entry_surface(node.file_path)
            only_test_imports = imports_in and all(
                self._is_test_node(self._graph.get_node(edge.source_id))
                for edge in imports_in
            )

            if has_entry:
                continue
            if imports_in or external_callers:
                if not only_test_imports:
                    continue
                descriptor = "Only test files depend on this module"
            else:
                descriptor = "No incoming imports or cross-file calls"

            stale.append(
                Evidence(
                    file_path=node.file_path,
                    line_start=node.line_start,
                    line_end=node.line_end,
                    code_snippet=self._snippets.for_node(node),
                    description=(
                        f"{descriptor}; imports_in={len(imports_in)} cross_file_callers={len(external_callers)}"
                    ),
                )
            )
            affected.append(node.id)

        stale.sort(key=lambda ev: ev.file_path)
        return QueryResult(
            conclusion=f"Found {len(stale)} potentially stale module(s).",
            evidence=stale,
            reasoning_chain=[
                ReasoningStep(
                    step=1,
                    description="Checked source files for incoming IMPORTS edges, cross-file CALLS edges, and entry-point exemptions.",
                ),
                ReasoningStep(
                    step=2,
                    description=f"Flagged {len(stale)} file(s) with no non-test dependents.",
                ),
            ],
            confidence=Confidence.MEDIUM if stale else Confidence.HIGH,
            affected_nodes=affected,
        )

    def trace_entry_flows(self, *, kind: str = "all", max_depth: int = 5) -> QueryResult:
        entries = self._entry_points(kind=kind)
        if not entries:
            return QueryResult(
                conclusion=f"No {kind if kind != 'all' else ''} entry flows found.".replace("  ", " ").strip(),
                confidence=Confidence.MEDIUM,
            )

        path_details: list[list[dict[str, object]]] = []
        evidence: list[Evidence] = []
        reasoning: list[ReasoningStep] = []

        for index, (node, entry_kind, reason) in enumerate(entries, start=1):
            paths = self._walk_paths(node.id, max_depth=max_depth, limit_paths=3)
            for path in paths:
                path_details.append(self._path_to_details(path, label=entry_kind))
            summary = paths[0] if paths else [node.id]
            evidence.append(
                Evidence(
                    file_path=node.file_path,
                    function_name=node.name,
                    line_start=node.line_start,
                    line_end=node.line_end,
                    code_snippet=self._snippets.for_node(node),
                    description=f"{entry_kind.upper()} entry via {reason}: {' -> '.join(self._short_name(nid) for nid in summary)}",
                )
            )
            reasoning.append(
                ReasoningStep(
                    step=index,
                    description=f"Traced {len(paths)} path(s) from {node.name} ({entry_kind}).",
                )
            )

        return QueryResult(
            conclusion=f"Traced {len(path_details)} execution path(s) from {len(entries)} entry point(s).",
            evidence=evidence,
            reasoning_chain=reasoning,
            confidence=Confidence.HIGH,
            affected_nodes=[node.id for node, _, _ in entries],
            metadata={"path_details": path_details, "entry_count": len(entries)},
        )

    def rank_criticality(self, *, limit: int = 10) -> QueryResult:
        di_graph = self._graph.to_simple_digraph()
        if not di_graph.nodes:
            return QueryResult(conclusion="No graph loaded.", confidence=Confidence.HIGH)

        betweenness = self._normalize_scores(nx.betweenness_centrality(di_graph))
        dependents = self._normalize_scores(
            {node_id: len(self._graph.get_transitive_dependents(node_id, {EdgeType.CALLS, EdgeType.IMPORTS})) for node_id in di_graph.nodes}
        )
        fan_in = self._normalize_scores({node_id: self._graph.fan_in(node_id) for node_id in di_graph.nodes})
        fan_out = self._normalize_scores({node_id: self._graph.fan_out(node_id) for node_id in di_graph.nodes})

        rankings: list[tuple[float, GraphNode]] = []
        for node_id in di_graph.nodes:
            node = self._graph.get_node(node_id)
            if node is None or node.node_type == NodeType.FILE:
                continue
            score = (
                betweenness.get(node_id, 0.0) * 0.45
                + dependents.get(node_id, 0.0) * 0.3
                + fan_in.get(node_id, 0.0) * 0.15
                + fan_out.get(node_id, 0.0) * 0.1
            )
            rankings.append((score, node))

        rankings.sort(key=lambda item: item[0], reverse=True)
        top = rankings[:limit]
        evidence = [
            Evidence(
                file_path=node.file_path,
                function_name=node.name,
                line_start=node.line_start,
                line_end=node.line_end,
                code_snippet=self._snippets.for_node(node),
                description=f"criticality={score:.3f} fan-in={self._graph.fan_in(node.id)} fan-out={self._graph.fan_out(node.id)} transitive_dependents={len(self._graph.get_transitive_dependents(node.id, {EdgeType.CALLS, EdgeType.IMPORTS}))}",
            )
            for score, node in top
        ]

        return QueryResult(
            conclusion=f"Ranked the top {len(top)} critical symbol(s) by graph centrality and dependency spread.",
            evidence=evidence,
            confidence=Confidence.HIGH,
            affected_nodes=[node.id for _, node in top],
        )

    def onboarding_summary(self) -> QueryResult:
        file_nodes = self._source_files()
        subsystem_counts = Counter(self._top_level_segment(node.file_path) for node in file_nodes)
        critical = self.rank_criticality(limit=5)
        entries = self.trace_entry_flows(kind="all", max_depth=4)
        hotspots = DependencyAnalyzer(self._graph, repo_root=self._repo_root).find_hotspots(threshold=2)

        reasoning = [
            ReasoningStep(step=1, description=f"Detected {len(file_nodes)} source file(s) across {len(subsystem_counts)} top-level subsystem(s)."),
            ReasoningStep(step=2, description=f"Found {len(entries.metadata.get('path_details', []))} entry flow(s) to start exploring execution paths."),
            ReasoningStep(step=3, description=f"Ranked the most central symbols and highlighted {len(hotspots.evidence)} hotspot(s)."),
        ]
        subsystem_text = ", ".join(
            f"{name} ({count})" for name, count in subsystem_counts.most_common(5)
        ) or "single-module repo"
        conclusion = (
            f"This repo is organized around {subsystem_text}. Start with the traced entry flows, then inspect the critical symbols and hotspots to understand change risk."
        )

        return QueryResult(
            conclusion=conclusion,
            evidence=critical.evidence[:3] + entries.evidence[:3],
            reasoning_chain=reasoning,
            confidence=Confidence.HIGH,
            metadata={
                "subsystems": subsystem_counts.most_common(),
                "entry_flows": entries.metadata.get("path_details", []),
                "hotspot_count": len(hotspots.evidence),
            },
        )

    def concept_search(self, concept: str) -> QueryResult:
        normalized = concept.strip().lower()
        patterns = self._LEGACY_CONCEPTS.get(normalized, tuple(filter(None, re.split(r"\s+", normalized))))
        evidence: list[Evidence] = []
        affected: list[str] = []

        for node in self._graph.nodes.values():
            haystacks = [node.name.lower(), node.file_path.lower()]
            decorators = [str(value).lower() for value in node.metadata.get("decorators", [])]
            haystacks.extend(decorators)
            matched = [pattern for pattern in patterns if any(pattern in haystack for haystack in haystacks)]
            if not matched:
                continue
            evidence.append(
                Evidence(
                    file_path=node.file_path,
                    function_name=None if node.node_type == NodeType.FILE else node.name,
                    line_start=node.line_start,
                    line_end=node.line_end,
                    code_snippet=self._snippets.for_node(node),
                    description=f"Matched concept '{concept}' via: {', '.join(sorted(set(matched)))}",
                )
            )
            affected.append(node.id)

        return QueryResult(
            conclusion=f"Found {len(evidence)} concept match(es) for '{concept}'.",
            evidence=evidence,
            confidence=Confidence.HIGH,
            affected_nodes=affected,
        )

    def call_flow(self, name: str, *, max_depth: int = 6) -> QueryResult:
        nodes = self._graph.find_nodes(name)
        if not nodes:
            return QueryResult(conclusion=f"No node named '{name}' found.", confidence=Confidence.HIGH)
        node = nodes[0]
        paths = self._walk_paths(node.id, max_depth=max_depth, limit_paths=8)
        if not paths:
            paths = [[node.id]]

        return QueryResult(
            conclusion=f"Found {len(paths)} call flow path(s) starting from '{node.name}'.",
            evidence=[
                Evidence(
                    file_path=node.file_path,
                    function_name=node.name,
                    line_start=node.line_start,
                    line_end=node.line_end,
                    code_snippet=self._snippets.for_node(node),
                    description=f"Entry node for call flow exploration: {node.name}",
                )
            ],
            confidence=Confidence.HIGH,
            affected_nodes=[item for path in paths for item in path],
            metadata={"path_details": [self._path_to_details(path, label="call") for path in paths]},
        )

    def history_drift(self, *, limit: int = 10) -> QueryResult:
        if self._repo_root is None or not (self._repo_root / ".git").exists():
            return QueryResult(
                conclusion="Historical drift analysis requires a Git repository checkout.",
                confidence=Confidence.MEDIUM,
            )

        try:
            history_output = subprocess.run(
                ["git", "-C", str(self._repo_root), "log", "--name-only", "--pretty=format:__COMMIT__", "--since=365.days"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        except subprocess.CalledProcessError as exc:
            return QueryResult(
                conclusion=f"Unable to read Git history: {exc.stderr.strip() or exc}",
                confidence=Confidence.MEDIUM,
            )

        churn_counter: Counter[str] = Counter()
        cochange_counter: Counter[tuple[str, str]] = Counter()
        current_commit_files: list[str] = []
        for line in history_output.splitlines():
            line = line.strip()
            if not line:
                continue
            if line == "__COMMIT__":
                if len(current_commit_files) > 1:
                    for pair in combinations(sorted(set(current_commit_files)), 2):
                        cochange_counter[pair] += 1
                current_commit_files = []
                continue
            churn_counter[line] += 1
            current_commit_files.append(line)

        top_files = churn_counter.most_common(limit)
        evidence = [
            Evidence(
                file_path=file_path,
                description=f"{count} change commit(s) in the last 365 days",
                code_snippet=self._snippets.for_location(file_path, 1, min(12, len((self._repo_root / file_path).read_text(encoding='utf-8', errors='ignore').splitlines()) if (self._repo_root / file_path).is_file() else 12)),
            )
            for file_path, count in top_files
        ]

        return QueryResult(
            conclusion=f"Ranked the top {len(top_files)} churn-heavy file(s) from Git history.",
            evidence=evidence,
            confidence=Confidence.MEDIUM,
            metadata={
                "cochange_pairs": [
                    {"pair": list(pair), "count": count}
                    for pair, count in cochange_counter.most_common(10)
                ],
                "churn_files": [{"file_path": file_path, "count": count} for file_path, count in top_files],
            },
        )

    def pr_review(
        self,
        *,
        changed_files: list[str] | None = None,
        diff_text: str | None = None,
        base_ref: str | None = None,
        head_ref: str | None = None,
    ) -> QueryResult:
        files = self._resolve_changed_files(
            changed_files=changed_files,
            diff_text=diff_text,
            base_ref=base_ref,
            head_ref=head_ref,
        )
        if not files:
            return QueryResult(
                conclusion="No changed files were provided or detected for PR review.",
                confidence=Confidence.MEDIUM,
            )

        impacted_nodes: set[str] = set()
        evidence: list[Evidence] = []
        nearby_tests: list[str] = []
        for file_path in files:
            file_node = self._graph.get_node(file_path)
            if file_node:
                impacted_nodes.add(file_node.id)
                impacted_nodes.update(
                    node.id
                    for node in self._graph.get_transitive_dependents(file_node.id, {EdgeType.IMPORTS, EdgeType.CALLS})
                )
            members = [node for node in self._graph.get_nodes_by_file(file_path) if node.node_type != NodeType.FILE]
            for member in members:
                impacted_nodes.update(
                    node.id
                    for node in self._graph.get_transitive_dependents(member.id, {EdgeType.CALLS, EdgeType.IMPORTS})
                )
            nearby_tests.extend(self._find_nearby_tests(file_path))
            evidence.append(
                Evidence(
                    file_path=file_path,
                    description=f"Changed file with {len(members)} symbol(s) and {len(self._find_nearby_tests(file_path))} nearby test candidate(s)",
                    code_snippet=self._snippets.for_location(file_path, 1, 20),
                )
            )

        return QueryResult(
            conclusion=(
                f"Reviewed {len(files)} changed file(s); estimated impact reaches {len(impacted_nodes)} node(s), with {len(set(nearby_tests))} nearby test candidate(s)."
            ),
            evidence=evidence,
            confidence=Confidence.MEDIUM,
            affected_nodes=sorted(impacted_nodes),
            metadata={
                "changed_files": files,
                "nearby_tests": sorted(set(nearby_tests)),
            },
        )

    def refactor_plan(self) -> QueryResult:
        stale = self.find_stale_modules()
        critical = self.rank_criticality(limit=8)
        cycles = DependencyAnalyzer(self._graph, repo_root=self._repo_root).find_circular_dependencies()
        candidates: dict[str, list[str]] = defaultdict(list)

        for evidence in stale.evidence:
            candidates[evidence.file_path].append("stale module")
        for evidence in critical.evidence[:5]:
            candidates[evidence.file_path].append("critical dependency hub")
        for evidence in cycles.evidence:
            candidates[evidence.file_path].append("cycle participant")
        for file_path, node_count in self._file_symbol_counts().items():
            if node_count >= 4:
                candidates[file_path].append(f"dense file ({node_count} symbols)")

        ranked = sorted(candidates.items(), key=lambda item: (len(item[1]), item[0]), reverse=True)
        evidence = [
            Evidence(
                file_path=file_path,
                description=f"Refactor candidate due to: {', '.join(reasons)}",
                code_snippet=self._snippets.for_location(file_path, 1, 20),
            )
            for file_path, reasons in ranked[:10]
        ]

        return QueryResult(
            conclusion=f"Identified {len(evidence)} refactor candidate(s) by combining stale modules, criticality, cycles, and file density.",
            evidence=evidence,
            confidence=Confidence.MEDIUM,
            metadata={"candidates": [{"file_path": file_path, "reasons": reasons} for file_path, reasons in ranked[:10]]},
        )

    def ask_architecture(self, question: str) -> QueryResult:
        query = question.strip()
        if not query:
            return QueryResult(conclusion="Ask a non-empty architecture question.", confidence=Confidence.HIGH)

        concept = self.concept_search(query)
        onboarding = self.onboarding_summary()
        critical = self.rank_criticality(limit=5)
        context_blocks = [
            f"Onboarding summary: {onboarding.conclusion}",
            "Top critical symbols:\n" + "\n".join(f"- {ev.file_path}: {ev.description}" for ev in critical.evidence[:5]),
            "Concept matches:\n" + "\n".join(f"- {ev.file_path}: {ev.description}" for ev in concept.evidence[:8]),
        ]

        try:
            client = TraceLLMClient.from_environment()
        except LLMConfigurationError as exc:
            return QueryResult(
                conclusion=(
                    f"LLM repo Q&A is available but not configured: {exc}. "
                    "Set TRACE_LLM_API_KEY and optionally TRACE_LLM_MODEL / TRACE_LLM_BASE_URL to enable it."
                ),
                evidence=concept.evidence[:5] + critical.evidence[:3],
                confidence=Confidence.MEDIUM,
            )

        answer = client.complete(
            system_prompt=(
                "You answer repository architecture questions using provided repo context. "
                "Be concise, factual, and explicit about uncertainty."
            ),
            user_prompt=f"Question: {query}\n\nContext:\n{chr(10).join(context_blocks)}",
        )
        return QueryResult(
            conclusion=answer,
            evidence=concept.evidence[:5] + critical.evidence[:3],
            confidence=Confidence.MEDIUM,
            metadata={"question": query},
        )

    def _source_files(self) -> list[GraphNode]:
        return [
            node
            for node in self._graph.get_nodes_by_type(NodeType.FILE)
            if node.metadata.get("category") in self._SOURCE_CATEGORIES
        ]

    def _entry_points(self, *, kind: str) -> list[tuple[GraphNode, str, str]]:
        entries: list[tuple[GraphNode, str, str]] = []
        for node in self._graph.nodes.values():
            if node.node_type not in {NodeType.FUNCTION, NodeType.METHOD}:
                continue
            decorators = [str(value).lower() for value in node.metadata.get("decorators", [])]
            name_lower = node.name.lower()
            if self._looks_like_route(node, decorators):
                entries.append((node, "route", "web decorator"))
                continue
            if any(marker in decorator for decorator in decorators for marker in self._JOB_DECORATOR_MARKERS) or any(marker in name_lower for marker in self._JOB_NAME_MARKERS):
                entries.append((node, "job", "task naming/decorator"))
                continue
            if any(marker in decorator for decorator in decorators for marker in self._CLI_DECORATOR_MARKERS) or name_lower in self._CLI_NAME_MARKERS or Path(node.file_path).name == "main.py":
                entries.append((node, "cli", "CLI naming/decorator"))
        if kind == "all":
            return entries
        return [entry for entry in entries if entry[1] == kind]

    def _walk_paths(
        self,
        start_id: str,
        *,
        max_depth: int,
        limit_paths: int,
    ) -> list[list[str]]:
        paths: list[list[str]] = []

        def dfs(current_id: str, path: list[str], depth: int) -> None:
            if len(paths) >= limit_paths:
                return
            outgoing = []
            for edge in self._graph.get_edges_from(current_id, self._FLOW_EDGES):
                if edge.target_id in path:
                    continue
                outgoing.append(edge.target_id)
            outgoing = list(dict.fromkeys(outgoing))
            if depth >= max_depth or not outgoing:
                paths.append(path)
                return
            for target_id in outgoing:
                dfs(target_id, [*path, target_id], depth + 1)

        dfs(start_id, [start_id], 1)
        return paths or [[start_id]]

    def _path_to_details(self, path: list[str], *, label: str) -> list[dict[str, object]]:
        details: list[dict[str, object]] = []
        for index, node_id in enumerate(path, start=1):
            node = self._graph.get_node(node_id)
            if node is None:
                continue
            details.append(
                {
                    "id": node.id,
                    "name": node.name,
                    "node_type": f"{label}:{node.node_type.value}" if index == 1 else node.node_type.value,
                    "file_path": node.file_path,
                    "line_start": node.line_start,
                    "line_end": node.line_end,
                    "code_snippet": self._snippets.for_node(node),
                    "step": index,
                    "step_count": len(path),
                }
            )
        return details

    def _file_contains_entry_surface(self, file_path: str) -> bool:
        nodes = self._graph.get_nodes_by_file(file_path)
        for node in nodes:
            if node.node_type not in {NodeType.FUNCTION, NodeType.METHOD}:
                continue
            decorators = [str(value).lower() for value in node.metadata.get("decorators", [])]
            if self._looks_like_route(node, decorators):
                return True
            if node.name.lower() in self._CLI_NAME_MARKERS:
                return True
        return Path(file_path).name in {"main.py", "__init__.py"}

    def _looks_like_route(self, node: GraphNode, decorators: list[str]) -> bool:
        if any(any(decorator.startswith(item) for item in self._PUBLIC_ENDPOINT_DECORATORS) for decorator in decorators):
            return True
        file_path_lower = node.file_path.lower()
        name_lower = node.name.lower()
        return (
            "/api/" in f"/{file_path_lower}"
            or file_path_lower.endswith("routes.py")
            or any(name_lower.startswith(marker) for marker in self._ROUTE_NAME_MARKERS)
        )

    def _is_test_node(self, node: GraphNode | None) -> bool:
        return bool(
            node
            and self._graph.get_node(node.file_path)
            and self._graph.get_node(node.file_path).metadata.get("category") == "test"
        )

    def _top_level_segment(self, file_path: str) -> str:
        parts = Path(file_path).parts
        if len(parts) <= 1:
            return "root"
        return parts[0]

    def _file_symbol_counts(self) -> dict[str, int]:
        counts: dict[str, int] = Counter()
        for node in self._graph.nodes.values():
            if node.node_type != NodeType.FILE:
                counts[node.file_path] += 1
        return counts

    def _resolve_changed_files(
        self,
        *,
        changed_files: list[str] | None,
        diff_text: str | None,
        base_ref: str | None,
        head_ref: str | None,
    ) -> list[str]:
        if changed_files:
            return sorted(set(path.strip() for path in changed_files if path.strip()))
        if diff_text:
            matches = re.findall(r"\+\+\+\s+b/(.+)", diff_text)
            if matches:
                return sorted(set(matches))
        if self._repo_root is None or not (self._repo_root / ".git").exists():
            return []
        args = ["git", "-C", str(self._repo_root), "diff", "--name-only"]
        if base_ref and head_ref:
            args.extend([base_ref, head_ref])
        else:
            args.extend(["HEAD~1", "HEAD"])
        try:
            output = subprocess.run(args, check=True, capture_output=True, text=True).stdout
        except subprocess.CalledProcessError:
            return []
        return sorted(set(line.strip() for line in output.splitlines() if line.strip()))

    def _find_nearby_tests(self, file_path: str) -> list[str]:
        if self._repo_root is None:
            return []
        stem = Path(file_path).stem
        matches: list[str] = []
        for candidate in self._repo_root.rglob("*.py"):
            rel = str(candidate.relative_to(self._repo_root)).replace("\\", "/")
            if "/tests/" not in f"/{rel}" and not rel.startswith("tests/"):
                continue
            candidate_stem = candidate.stem
            if stem in candidate_stem or candidate_stem in {f"test_{stem}", stem}:
                matches.append(rel)
        return matches

    @staticmethod
    def _normalize_scores(values: dict[str, float | int]) -> dict[str, float]:
        if not values:
            return {}
        max_value = max(float(value) for value in values.values())
        if math.isclose(max_value, 0.0):
            return {key: 0.0 for key in values}
        return {key: float(value) / max_value for key, value in values.items()}

    @staticmethod
    def _short_name(node_id: str) -> str:
        return node_id.split("::")[-1] if "::" in node_id else node_id