from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from trace_engine.core import Trace
from trace_engine.output.formatter import Formatter

app = typer.Typer(
    name="trace",
    help="Deterministic codebase understanding with AI-assisted reasoning.",
    no_args_is_help=True,
)
console = Console()
fmt = Formatter(console)


def _trace(repo: str) -> Trace:
    return Trace(repo)


# ------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------


@app.command()
def ingest(
    path: str = typer.Argument(".", help="Path to the repository"),
) -> None:
    """Ingest a codebase and build the code graph."""
    t = _trace(path)
    graph = t.ingest()
    console.print(
        f"[green]✓[/green] Ingested {graph.node_count} nodes, "
        f"{graph.edge_count} edges."
    )


@app.command()
def impact(
    name: str = typer.Argument(..., help="Function or class name"),
    repo: str = typer.Option(".", help="Repository path"),
) -> None:
    """Analyse what breaks if you change or remove a component."""
    fmt.render(_trace(repo).impact(name), title=f"Impact Analysis: {name}")


@app.command()
def deps(
    name: str = typer.Argument(..., help="Component name"),
    repo: str = typer.Option(".", help="Repository path"),
) -> None:
    """Show what depends on a component."""
    fmt.render(_trace(repo).dependents(name), title=f"Dependents: {name}")


@app.command()
def usages(
    name: str = typer.Argument(..., help="Component name"),
    repo: str = typer.Option(".", help="Repository path"),
) -> None:
    """Find where a component is used."""
    fmt.render(_trace(repo).usages(name), title=f"Usages: {name}")


@app.command()
def dead_code(
    repo: str = typer.Option(".", help="Repository path"),
) -> None:
    """Detect dead code (functions with no callers)."""
    fmt.render(_trace(repo).dead_code(), title="Dead Code Detection")


@app.command()
def endpoints(
    repo: str = typer.Option(".", help="Repository path"),
) -> None:
    """List all detected API endpoints."""
    fmt.render(_trace(repo).endpoints(), title="API Endpoints")


@app.command()
def cycles(
    repo: str = typer.Option(".", help="Repository path"),
) -> None:
    """Find circular dependencies between files."""
    fmt.render(_trace(repo).cycles(), title="Circular Dependencies")


@app.command()
def hotspots(
    repo: str = typer.Option(".", help="Repository path"),
    threshold: int = typer.Option(3, help="Minimum fan-in/out"),
) -> None:
    """Find dependency hotspots (high fan-in / fan-out)."""
    fmt.render(
        _trace(repo).hotspots(threshold), title="Dependency Hotspots"
    )


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    repo: str = typer.Option(".", help="Repository path"),
) -> None:
    """Search for code elements by name."""
    fmt.render(_trace(repo).search(query), title=f"Search: {query}")


@app.command()
def navigate(
    from_name: str = typer.Argument(..., help="Source component"),
    to_name: str = typer.Argument(..., help="Target component"),
    repo: str = typer.Option(".", help="Repository path"),
) -> None:
    """Show code paths between two components."""
    fmt.render(
        _trace(repo).path(from_name, to_name),
        title=f"Navigate: {from_name} → {to_name}",
    )
