from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from trace_engine.models.evidence import Confidence, QueryResult


_CONFIDENCE_COLOURS = {
    Confidence.HIGH: "green",
    Confidence.MEDIUM: "yellow",
    Confidence.LOW: "red",
}


class Formatter:
    """Render :class:`QueryResult` objects with Rich."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def render(self, result: QueryResult, *, title: str = "Trace") -> None:
        colour = _CONFIDENCE_COLOURS.get(result.confidence, "white")

        # Header
        header = Text(title, style="bold")
        header.append("  ")
        header.append(
            f"[{result.confidence.value.upper()}]",
            style=f"bold {colour}",
        )
        self.console.print(Panel(header, expand=False))

        # Conclusion
        self.console.print(f"\n[bold]Conclusion:[/bold] {result.conclusion}\n")

        # Evidence table
        if result.evidence:
            table = Table(
                title="Evidence", show_lines=True, title_style="bold cyan"
            )
            table.add_column("File", style="cyan", no_wrap=True)
            table.add_column("Component")
            table.add_column("Line", justify="right")
            table.add_column("Description")

            for ev in result.evidence:
                table.add_row(
                    ev.file_path,
                    ev.function_name or "—",
                    str(ev.line_start) if ev.line_start else "—",
                    ev.description,
                )
            self.console.print(table)

        # Reasoning chain
        if result.reasoning_chain:
            tree = Tree("[bold]Reasoning Chain[/bold]")
            for step in result.reasoning_chain:
                tree.add(f"[dim]{step.step}.[/dim] {step.description}")
            self.console.print()
            self.console.print(tree)

        self.console.print()
