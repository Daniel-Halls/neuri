"""CLI entrypoint and headless execution controller for Neuri.

Provides the primary executable entry point (`neuri`) registered in pyproject.toml.
Typing `neuri` launches the interactive Textual terminal chat interface.
Flags `-p` / `--print` support headless execution for scripting and pipelines.
"""

import asyncio
from pathlib import Path
import sys
from typing import Annotated

from rich.console import Console
import typer

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

    def main(
        self,
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
