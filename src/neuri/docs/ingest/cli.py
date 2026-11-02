"""Command-line interface for indexing and querying Neuri documentation.

Provides Typer CLI commands to build the SQLite documentation database,
perform test searches, and inspect supported pipelines.
"""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from neuri.docs.db.repository import DocsRepository
from neuri.docs.ingest.indexer import DocsIndexer
from neuri.docs.models import DocSearchResult, DocType, PipelineMetadata


class DocsCLI:
    """Command-line interface manager for neuroimaging docs indexer and query tool.

    Encapsulates Rich Console and Typer command bindings to maintain zero
    module-level global state.
    """

    def __init__(self) -> None:
        """Initialize DocsCLI with console and Typer app instance.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes CLI application and binds commands.
        """
        self.console: Console = Console()
        self.app: typer.Typer = typer.Typer(
            name="neuri-docs",
            help="Neuroimaging documentation indexer and query manager.",
        )
        self.app.command("index")(self.index_docs)
        self.app.command("search")(self.search_docs)
        self.app.command("list")(self.list_supported)

    def index_docs(
        self,
        docs_dir: Annotated[
            Path | None,
            typer.Option(
                "--docs-dir",
                "-d",
                help="Path to documentation root folder.",
            ),
        ] = None,
        db_path: Annotated[
            Path | None,
            typer.Option(
                "--db-path",
                "-b",
                help="Target SQLite database destination path.",
            ),
        ] = None,
    ) -> None:
        """Index all markdown documentation files into SQLite FTS5 database.

        Parameters
        ------------
        docs_dir: Path | None
            Optional explicit documentation source directory. Defaults to None.
        db_path: Path | None
            Optional explicit SQLite target database path. Defaults to None.

        Returns
        --------
            None: NoneType object
                Prints indexing summary table to console.
        """
        repo: DocsRepository = DocsRepository(db_path=db_path)
        indexer: DocsIndexer = DocsIndexer(repository=repo, docs_dir=docs_dir)

        self.console.print(
            f"[bold blue]Indexing documentation from:[/bold blue] "
            f"{indexer.docs_dir}"
        )
        res = indexer.index_all()

        if res.get("status") == "error":
            self.console.print(
                f"[bold red]Error:[/bold red] {res.get('message')}"
            )
            raise typer.Exit(code=1)

        table: Table = Table(title="Indexed Pipelines Summary")
        table.add_column("Pipeline", style="cyan")
        table.add_column("Commands", justify="center")
        table.add_column("Functions", justify="center")
        table.add_column("Docs", justify="center")
        table.add_column("Chunks", justify="right", style="green")

        for item in res.get("details", []):
            table.add_row(
                item["display_name"],
                "[green]Yes[/green]" if item["has_commands"] else "[dim]No[/dim]",
                "[green]Yes[/green]" if item["has_functions"] else "[dim]No[/dim]",
                "[green]Yes[/green]" if item["has_documentation"] else "[dim]No[/dim]",
                str(item["chunks"]),
            )

        self.console.print(table)
        total_pipes = res.get("pipelines_indexed")
        total_ch = res.get("total_chunks")
        out_db = res.get("db_path")
        self.console.print(
            f"[bold green]Successfully indexed {total_pipes} pipelines "
            f"({total_ch} total chunks) into {out_db}[/bold green]"
        )

    def search_docs(
        self,
        pipeline: Annotated[
            str,
            typer.Argument(
                help="Pipeline or package name (e.g. 'fmriprep', 'nilearn')."
            ),
        ],
        query: Annotated[
            str,
            typer.Argument(
                help="Search query text or flag (e.g. '--output-spaces')."
            ),
        ],
        doc_type: Annotated[
            str | None,
            typer.Option(
                "--type",
                "-t",
                help="Filter: 'commands', 'functions', or 'documentation'.",
            ),
        ] = None,
        limit: Annotated[
            int,
            typer.Option(
                "--limit",
                "-l",
                help="Maximum results to return.",
            ),
        ] = 5,
        db_path: Annotated[
            Path | None,
            typer.Option(
                "--db-path",
                "-b",
                help="Path to SQLite database.",
            ),
        ] = None,
    ) -> None:
        """Search indexed documentation chunks by pipeline and keyword.

        Parameters
        ------------
        pipeline: str
            Pipeline name or alias to query.
        query: str
            Search terms or flag name.
        doc_type: str | None
            Optional documentation category filter. Defaults to None.
        limit: int
            Max results. Defaults to 5.
        db_path: Path | None
            Optional database path. Defaults to None.

        Returns
        --------
            None: NoneType object
                Renders matching items to console.
        """
        repo: DocsRepository = DocsRepository(db_path=db_path)
        clean_type: DocType | None = (
            doc_type.lower().strip()  # type: ignore[assignment]
            if doc_type in ("commands", "functions", "documentation")
            else None
        )

        results: list[DocSearchResult] = repo.search(
            pipeline=pipeline,
            query=query,
            doc_type=clean_type,
            limit=limit,
        )

        if not results:
            msg: str = (
                f"[yellow]No matching documentation found for '{query}' "
                f"in {pipeline}.[/yellow]"
            )
            self.console.print(msg)
            return

        summary_msg: str = (
            f"[bold green]Found {len(results)} matches for '{query}' "
            f"in {pipeline}:[/bold green]\n"
        )
        self.console.print(summary_msg)
        for idx, r in enumerate(results, 1):
            self.console.print(
                f"[bold cyan]#{idx} [{r.doc_type.upper()}] {r.item_name}"
                f"[/bold cyan] ([dim]{r.section_title}[/dim])"
            )
            self.console.print(f"{r.content.strip()}\n")

    def list_supported(
        self,
        db_path: Annotated[
            Path | None,
            typer.Option(
                "--db-path",
                "-b",
                help="Path to SQLite database.",
            ),
        ] = None,
    ) -> None:
        """List all supported pipelines and their indexed documentation categories.

        Parameters
        ------------
        db_path: Path | None
            Optional explicit database path. Defaults to None.

        Returns
        --------
            None: NoneType object
                Displays pipeline table.
        """
        repo: DocsRepository = DocsRepository(db_path=db_path)
        pipelines: list[PipelineMetadata] = repo.list_pipelines()

        table: Table = Table(
            title="Supported Pipelines & Available Documentation"
        )
        table.add_column("Pipeline", style="cyan")
        table.add_column("Commands", justify="center")
        table.add_column("Functions", justify="center")
        table.add_column("Docs", justify="center")
        table.add_column("Description", style="dim")

        for p in pipelines:
            table.add_row(
                p.display_name,
                "[green]Yes[/green]" if p.has_commands else "[dim]No[/dim]",
                "[green]Yes[/green]" if p.has_functions else "[dim]No[/dim]",
                "[green]Yes[/green]" if p.has_documentation else "[dim]No[/dim]",
                p.description[:80] + ("..." if len(p.description) > 80 else ""),
            )

        self.console.print(table)


def get_docs_cli_app() -> typer.Typer:
    """Construct and return the Typer CLI application for documentation operations.

    Parameters
    ------------
    None

    Returns
    --------
        typer.Typer: Typer object
            Configured Typer CLI instance.
    """
    cli: DocsCLI = DocsCLI()
    target_app: typer.Typer = cli.app
    return target_app


def main() -> None:
    """Execute Docs CLI application.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Executes CLI.
    """
    cli_app: typer.Typer = get_docs_cli_app()
    cli_app()


__all__: list[str] = [
    "DocsCLI",
    "get_docs_cli_app",
    "main",
]

if __name__ == "__main__":
    main()
