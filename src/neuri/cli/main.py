"""CLI entrypoint and headless execution controller for Neuri.

Provides the primary executable entry point (`neuri`) registered in pyproject.toml.
Typing `neuri` launches the interactive Textual terminal chat interface.
Flags `-p` / `--print` support headless execution for scripting and pipelines.
"""

import asyncio
from pathlib import Path
import sys
from typing import Annotated, Any

from rich.console import Console
import typer

from neuri.core.installer import NeuriInstaller
from neuri.core.schemas import ChatTurn
from neuri.core.session import NeuriSessionEngine
from neuri.ui.terminal_chat import NeuriChatApp


class NeuriCLI:
    """Encapsulates Typer CLI setup, option handling, and execution dispatch.

    Parameters
    ------------
    None

    Returns
    --------
        NeuriCLI: NeuriCLI instance
            Constructed CLI runner.
    """

    VERSION: str = "0.1.0"

    def __init__(self) -> None:
        """Initialize Typer application and bind callbacks.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes Typer instance and console.
        """
        self.console: Console = Console()
        self.cli_app: typer.Typer = typer.Typer(
            name="neuri",
            help="Neuri: Vendor-Agnostic Neuroscience Meta-Harness",
            add_completion=False,
        )
        self.cli_app.callback(invoke_without_command=True)(self.main)
        self.cli_app.command(
            name="install",
            help="Install base master prompt, skills, MCP, and rules into ~/.neuri.",
        )(self.install)

    def main(
        self,
        ctx: typer.Context,
        prompt: Annotated[
            str | None,
            typer.Option(
                "--print",
                "-p",
                help="Execute single prompt or slash command headlessly.",
            ),
        ] = None,
        version: Annotated[
            bool,
            typer.Option(
                "--version",
                "-v",
                help="Display Neuri version information.",
            ),
        ] = False,
        workspace: Annotated[
            Path | None,
            typer.Option(
                "--workspace",
                "-w",
                help="Custom workspace directory path.",
            ),
        ] = None,
    ) -> None:
        """Process CLI flags and launch either interactive chat or headless turn.

        Parameters
        ------------
        ctx: typer.Context
            Typer command execution context.
        prompt: str | None
            Prompt or slash command for headless execution. Defaults to None.
        version: bool
            Whether to display version. Defaults to False.
        workspace: Path | None
            Workspace directory. Defaults to None (cwd).

        Returns
        --------
            None: NoneType object
                Dispatches to target execution mode.
        """
        if version:
            self.console.print(f"neuri version {self.VERSION}")
            return

        if ctx.invoked_subcommand is not None:
            return
            self.console.print(f"neuri version {self.VERSION}")
            return

        target_workspace: Path = (
            workspace if workspace is not None else Path.cwd()
        )

        if prompt is not None:
            self._run_headless(prompt=prompt, workspace_dir=target_workspace)
            return

        # Default action: Launch interactive terminal chat interface
        self._run_interactive_tui(workspace_dir=target_workspace)

    def _run_headless(self, prompt: str, workspace_dir: Path) -> None:
        """Execute a prompt headlessly and output formatted result to stdout.

        Parameters
        ------------
        prompt: str
            Input prompt or slash command.
        workspace_dir: Path
            Workspace directory.

        Returns
        --------
            None: NoneType object
                Prints result to stdout.
        """
        engine: NeuriSessionEngine = NeuriSessionEngine(
            workspace_dir=workspace_dir
        )
        turn: ChatTurn = asyncio.run(engine.submit_user_input(prompt))
        self.console.print(turn.content)

    def _run_interactive_tui(self, workspace_dir: Path) -> None:
        """Launch the full Textual interactive chat window in terminal.

        Parameters
        ------------
        workspace_dir: Path
            Workspace directory.

        Returns
        --------
            None: NoneType object
                Runs interactive chat loop.
        """
        app_instance: NeuriChatApp = NeuriChatApp(workspace_dir=workspace_dir)
        app_instance.run()

    def install(
        self,
        force: Annotated[
            bool,
            typer.Option(
                "--force",
                "-f",
                help="Overwrite existing configuration, skills, and prompts.",
            ),
        ] = False,
        target: Annotated[
            Path | None,
            typer.Option(
                "--target",
                "-t",
                help="Custom target directory. Defaults to ~/.neuri.",
            ),
        ] = None,
    ) -> None:
        """Install base Neuri prompts, skills, MCP, and rules into target directory.

        Parameters
        ------------
        force: bool
            Whether to overwrite existing files. Defaults to False.
        target: Path | None
            Custom target directory. Defaults to None (~/.neuri).

        Returns
        --------
            None: NoneType object
                Installs files and prints summary to console.
        """
        installer: NeuriInstaller = NeuriInstaller(target_dir=target)
        summary: dict[str, Any] = installer.install(force=force)
        target_dir: str = summary.get(
            "target_dir", str(Path.home() / ".neuri")
        )
        installed: list[str] = summary.get("installed", [])

        if installed:
            installed_str: str = ", ".join(installed)
            self.console.print(
                "[green]✓ Neuri base environment installed successfully "
                f"into:[/green] {target_dir}"
            )
            self.console.print(
                f"  Installed subfolders: [bold]{installed_str}[/bold]"
            )
            self.console.print(
                "  - global/: Master grounding prompt (master_prompt.md)"
            )
            self.console.print(
                "  - skills/: Neuroscience skills catalog and manuals"
            )
            self.console.print(
                "  - mcp/: MCP server configurations (mcp_servers.json)"
            )
            self.console.print("  - rules/: Operational rules directory")
        else:
            self.console.print(
                "[yellow]Neuri environment is already present at:[/yellow] "
                f"{target_dir}"
            )
            self.console.print(
                "Use [bold]neuri install --force[/bold] to overwrite."
            )

    def run(self) -> None:
        """Invoke the Typer CLI application.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Dispatches arguments to Typer.
        """
        self.cli_app()


def app() -> None:
    """Entrypoint callable for pyproject.toml console_scripts (neuri).

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Executes Neuri CLI.
    """
    runner: NeuriCLI = NeuriCLI()
    runner.run()


__all__: list[str] = [
    "NeuriCLI",
    "app",
]
