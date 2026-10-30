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
from rich.markdown import Markdown
import typer

from neuri.core.installer import NeuriInstaller
from neuri.core.schemas import ChatTurn, SessionEvent, SessionEventType
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
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run",
                help="Preview planned DAG and role routing without executing.",
            ),
        ] = False,
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
        model: Annotated[
            str | None,
            typer.Option(
                "--model",
                "-m",
                help="Override active AI model across connected harnesses.",
            ),
        ] = None,
        harness: Annotated[
            str | None,
            typer.Option(
                "--harness",
                "-H",
                help="Active AI harness across all roles (agy, ollama, codex).",
            ),
        ] = None,
    ) -> None:
        """Process CLI flags and launch either interactive chat or headless turn.

        Parameters
        ------------
        ctx: typer.Context
            Typer command execution context.
        prompt: str | None
            Prompt or slash command for headless execution via -p.
            Defaults to None.
        dry_run: bool
            Preview planned DAG without executing. Defaults to False.
        version: bool
            Whether to display version. Defaults to False.
        workspace: Path | None
            Workspace directory. Defaults to None (cwd).
        model: str | None
            Active AI model override across harnesses. Defaults to None.
        harness: str | None
            Active AI harness override across roles. Defaults to None.

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

        # Ensure base environment is installed in ~/.neuri if missing
        installer: NeuriInstaller = NeuriInstaller()
        installer.ensure_installed(force=False)

        target_workspace: Path = (
            workspace if workspace is not None else Path.cwd()
        )

        if dry_run:
            target_prompt: str = (
                f"/plan {prompt}" if prompt is not None else "/status"
            )
            self._run_headless(
                prompt=target_prompt,
                workspace_dir=target_workspace,
                model=model,
                harness=harness,
            )
            return

        if prompt is not None:
            self._run_headless(
                prompt=prompt,
                workspace_dir=target_workspace,
                model=model,
                harness=harness,
            )
            return

        # Default action: Launch interactive terminal chat interface
        self._run_interactive_tui(
            workspace_dir=target_workspace,
            model=model,
            harness=harness,
        )

    def _run_headless(
        self,
        prompt: str,
        workspace_dir: Path,
        model: str | None = None,
        harness: str | None = None,
    ) -> None:
        """Execute a prompt headlessly with real-time feedback streamed to terminal.

        Parameters
        ------------
        prompt: str
            Input prompt or slash command.
        workspace_dir: Path
            Workspace directory.
        model: str | None
            Active AI model override across harnesses. Defaults to None.
        harness: str | None
            Active AI harness override across roles. Defaults to None.

        Returns
        --------
            None: NoneType object
                Streams real-time feedback and prints result to stdout.
        """
        engine: NeuriSessionEngine = NeuriSessionEngine(
            workspace_dir=workspace_dir,
            model=model,
            harness=harness,
        )

        has_streamed_content: bool = False
        is_in_thinking: bool = False

        def _on_session_event(ev: SessionEvent) -> None:
            """Process and print live session events to the terminal.

            Parameters
            ------------
            ev: SessionEvent
                Session event containing streaming telemetry, tokens, or tools.

            Returns
            --------
                None: NoneType object
                    Prints live updates to stdout without buffering.
            """
            nonlocal has_streamed_content, is_in_thinking
            if ev.event_type == SessionEventType.STATUS_UPDATE:
                status: Any = ev.payload.get("status")
                action: Any = ev.payload.get("action")
                if status == "workflow_planned":
                    wf_id: str = str(ev.payload.get("workflow_id", ""))
                    self.console.print(
                        f"[dim cyan] Workflow planned: "
                        f"[bold]{wf_id}[/bold][/dim cyan]"
                    )
                elif action == "raw_stream":
                    raw: str = str(ev.payload.get("raw_text", ""))
                    if raw.strip():
                        if is_in_thinking:
                            self.console.print()
                            is_in_thinking = False
                        self.console.print(f"[dim]{raw.rstrip()}[/dim]")

            elif ev.event_type == SessionEventType.TOOL_CALL_UPDATE:
                tool_name: str = str(ev.payload.get("tool_name", "unknown"))
                tool_status: str = str(ev.payload.get("tool_status", ""))
                host: str = str(ev.payload.get("tool_host", "localhost"))
                dur: Any = ev.payload.get("duration_ms")
                if is_in_thinking:
                    self.console.print()
                    is_in_thinking = False
                if tool_status == "started":
                    self.console.print(
                        f"[yellow] Tool started: "
                        f"[bold]{tool_name}[/bold] ({host})[/yellow]"
                    )
                elif tool_status == "completed":
                    dur_str: str = f" in {dur}ms" if dur is not None else ""
                    self.console.print(
                        f"[green]✓ Tool completed: "
                        f"[bold]{tool_name}[/bold]{dur_str}[/green]"
                    )
                elif tool_status == "failed":
                    self.console.print(
                        f"[red]✗ Tool failed: [bold]{tool_name}[/bold][/red]"
                    )

            elif ev.event_type == SessionEventType.THINKING_CHUNK:
                delta: str = str(ev.payload.get("thinking_delta", ""))
                if delta:
                    if not is_in_thinking:
                        self.console.print(
                            "[dim italic]🧠 Reasoning: [/dim italic]",
                            end="",
                        )
                        is_in_thinking = True
                    self.console.print(
                        f"[dim italic]{delta}[/dim italic]",
                        end="",
                    )
                    sys.stdout.flush()

            elif ev.event_type == SessionEventType.ASSISTANT_CHUNK:
                c_delta: str = str(ev.payload.get("content_delta", ""))
                if c_delta:
                    if is_in_thinking:
                        self.console.print("\n")
                        is_in_thinking = False
                    has_streamed_content = True
                    if sys.stdout.isatty():
                        self.console.print(c_delta, end="", highlight=False)
                    else:
                        sys.stdout.write(c_delta)
                    sys.stdout.flush()

            elif ev.event_type == SessionEventType.CIRCUIT_BREAKER_TRIGGERED:
                reason: str = str(ev.payload.get("reason", ""))
                self.console.print(
                    f"\n[bold red]⚠ Circuit Breaker Tripped:[/bold red] "
                    f"{reason}"
                )

        engine.subscribe(_on_session_event)
        turn: ChatTurn = asyncio.run(engine.submit_user_input(prompt))

        if has_streamed_content:
            self.console.print()
        else:
            if sys.stdout.isatty():
                self.console.print(Markdown(turn.content))
            else:
                self.console.print(turn.content)

    def _run_interactive_tui(
        self,
        workspace_dir: Path,
        model: str | None = None,
        harness: str | None = None,
    ) -> None:
        """Launch the full Textual interactive chat window in terminal.

        Parameters
        ------------
        workspace_dir: Path
            Workspace directory.
        model: str | None
            Active AI model override. Defaults to None.
        harness: str | None
            Active AI harness override. Defaults to None.

        Returns
        --------
            None: NoneType object
                Runs interactive chat loop.
        """
        app_instance: NeuriChatApp = NeuriChatApp(
            workspace_dir=workspace_dir,
            initial_model=model,
            initial_harness=harness,
        )
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
        """Install base Neuri prompts, skills, MCP, rules, and brain.

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
            self.console.print(
                "  - themes/: Terminal UI themes (high_contrast, dark, etc.)"
            )
            self.console.print(
                "  - brain/: Cognitive semantic memory vault & MRI pipeline docs"
            )
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
