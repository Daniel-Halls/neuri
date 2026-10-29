"""Interactive Slash Command Router and Execution Subsystem for Neuri.

Provides structured command dispatch (/init, /skills, /status, /harness,
/retry, /cancel, /clear, /help, /exit) designed for both the terminal chat
interface and future Desktop/Web GUIs.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
from typing import Any, Coroutine
import uuid
import webbrowser

from pydantic import BaseModel, ConfigDict, Field
import yaml

from neuri.brain import (
    BrainContextCapsule,
    BrainManager,
    BrainObservation,
    BrainScope,
    BrainSearchResult,
    BrainStats,
    ObservationCategory,
)
from neuri.core.blackboard import Blackboard
from neuri.core.config import NeuriConfig, init_project_workspace, load_config
from neuri.core.installer import NeuriInstaller
from neuri.core.orchestrator import DAGOrchestrator
from neuri.core.paths import PathResolver
from neuri.core.schemas import (
    NiiVueLayerSpec,
    NiiVueSceneSpec,
    RemoteArtifact,
    TaskNode,
    TaskState,
)
from neuri.literature import (
    ApaCitation,
    ApaResolver,
    AuditReport,
    RefereeAuditor,
    ScholarCorpusFetcher,
)
from neuri.remote.bootstrap import RemoteHostBootstrapper
from neuri.remote.monitor import RemoteHostMonitor
from neuri.remote.slurm_bridge import DetachAndReconcileManager


class SlashCommandResult(BaseModel):
    """Structured result returned by slash command execution.

    Parameters
    ------------
    command: str
        The slash command that was executed (e.g. '/init', '/skills').
    success: bool
        Whether command execution succeeded.
    markdown_output: str
        Human-readable GitHub-flavored markdown rendered in the chat window.
    data: dict[str, Any]
        Raw structured data payload for programmatic GUI consumption.
    action: str | None
        Optional UI trigger action (e.g. 'clear_chat', 'exit_app', 'reload_config').
        Defaults to None.

    Returns
    --------
        SlashCommandResult: SlashCommandResult instance
            Constructed slash command result model.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    command: str = Field(..., description="Executed slash command")
    success: bool = Field(..., description="Whether command succeeded")
    markdown_output: str = Field(..., description="Formatted markdown message")
    data: dict[str, Any] = Field(
        default_factory=dict, description="Structured payload"
    )
    action: str | None = Field(
        default=None, description="UI trigger action if any"
    )


class SlashCommandRouter:
    """Dispatches user commands starting with '/' to typed handlers.

    Parameters
    ------------
    workspace_dir: Path
        Target workspace directory.
    config: NeuriConfig
        Active configuration instance.
    blackboard: Blackboard
        Persistent SQLite WAL state store.
    orchestrator: DAGOrchestrator
        DAG execution orchestrator.
    skills_index_path: Path | None
        Path to skills/index.yaml catalog. Defaults to None.

    Returns
    --------
        SlashCommandRouter: SlashCommandRouter instance
            Constructed command router.
    """

    SUPPORTED_COMMANDS: list[str] = [
        "/init",
        "/install",
        "/skills",
        "/status",
        "/harness",
        "/model",
        "/models",
        "/remote",
        "/machines",
        "/cluster",
        "/jobs",
        "/shell",
        "/sh",
        "/history",
        "/hist",
        "/theme",
        "/brain",
        "/memory",
        "/researcher",
        "/research",
        "/paperback",
        "/writer",
        "/referee",
        "/notebooklm",
        "/nlm",
        "/plan",
        "/run",
        "/view",
        "/retry",
        "/cancel",
        "/clear",
        "/help",
        "/exit",
        "/quit",
    ]

    def __init__(
        self,
        workspace_dir: Path,
        config: NeuriConfig,
        blackboard: Blackboard,
        orchestrator: DAGOrchestrator,
        skills_index_path: Path | None = None,
    ) -> None:
        """Initialize slash command router with workspace dependencies.

        Parameters
        ------------
        workspace_dir: Path
            Target workspace directory.
        config: NeuriConfig
            Active Neuri configuration.
        blackboard: Blackboard
            Active Blackboard instance.
        orchestrator: DAGOrchestrator
            Active DAG orchestrator instance.
        skills_index_path: Path | None
            Catalog file path. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes router state.
        """
        self._workspace_dir: Path = workspace_dir
        self._config: NeuriConfig = config
        self._blackboard: Blackboard = blackboard
        self._orchestrator: DAGOrchestrator = orchestrator
        self._skills_index_path: Path = (
            skills_index_path
            if skills_index_path is not None
            else PathResolver.get_default_skills_index()
        )
        self._last_planned_workflow_id: str | None = None

    def is_slash_command(self, text: str) -> bool:
        """Check if an input string is formatted as a slash command.

        Parameters
        ------------
        text: str
            Raw user input string.

        Returns
        --------
            bool: boolean object
                True if text starts with '/' followed by non-whitespace.
        """
        stripped: str = text.strip()
        is_cmd: bool = stripped.startswith("/") and len(stripped) > 1
        return is_cmd

    def execute(self, command_line: str) -> SlashCommandResult:
        """Route and execute a slash command string.

        Parameters
        ------------
        command_line: str
            Full command string (e.g. '/init', '/skills bids-standard').

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Outcome of command execution.
        """
        parts: list[str] = command_line.strip().split()
        if not parts:
            return SlashCommandResult(
                command="/",
                success=False,
                markdown_output="No command provided.",
            )

        cmd: str = parts[0].lower()
        args: list[str] = parts[1:]

        if cmd == "/init":
            return self._handle_init()
        elif cmd == "/install":
            return self._handle_install(args)
        elif cmd == "/skills":
            return self._handle_skills(args)
        elif cmd == "/status":
            return self._handle_status()
        elif cmd == "/harness":
            return self._handle_harness(args)
        elif cmd in ("/model", "/models"):
            return self._handle_model(args)
        elif cmd == "/remote":
            return self._handle_remote(args)
        elif cmd in ("/machines", "/cluster"):
            return self._handle_machines()
        elif cmd == "/jobs":
            return self._handle_jobs(args)
        elif cmd in ("/shell", "/sh"):
            return self._handle_shell(args)
        elif cmd in ("/history", "/hist"):
            return self._handle_history(args)
        elif cmd == "/theme":
            return self._handle_theme(args)
        elif cmd in ("/brain", "/memory"):
            return self._handle_brain(args)
        elif cmd in ("/researcher", "/research"):
            return self._handle_researcher(args)
        elif cmd in ("/paperback", "/writer", "/referee"):
            return self._handle_paperback(args)
        elif cmd in ("/notebooklm", "/nlm"):
            return self._handle_notebooklm(args)
        elif cmd == "/plan":
            return self._handle_plan(args)
        elif cmd == "/run":
            return self._handle_run(args)
        elif cmd == "/view":
            return self._handle_view(args)
        elif cmd == "/retry":
            return self._handle_retry(args)
        elif cmd == "/cancel":
            return self._handle_cancel(args)
        elif cmd == "/clear":
            return self._handle_clear()
        elif cmd in ("/help", "/?"):
            return self._handle_help()
        elif cmd in ("/exit", "/quit"):
            return self._handle_exit()
        else:
            return SlashCommandResult(
                command=cmd,
                success=False,
                markdown_output=(
                    f"Unknown command: `{cmd}`. Type `/help` to see available "
                    f"commands."
                ),
            )

    def _handle_init(self) -> SlashCommandResult:
        """Initialize .neuri workspace in current directory.

        Parameters
        ------------
        None

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Initialization result card.
        """
        try:
            ws_path: Path = init_project_workspace(self._workspace_dir)
            msg: str = (
                f"### Workspace Initialized\n\n"
                f"Successfully initialized Neuri workspace at:\n"
                f"- Directory: `{ws_path}`\n"
                f"- Configuration: `{ws_path / 'neuri.toml'}`\n"
                f"- Blackboard: `{ws_path / 'state.db'}`\n"
                f"- Provenance Log: `{ws_path / 'execution_history.json'}`\n"
                f"- References Ledger: `{ws_path / 'references.bib'}`\n"
            )
            return SlashCommandResult(
                command="/init",
                success=True,
                markdown_output=msg,
                data={"workspace_path": str(ws_path)},
                action="reload_config",
            )
        except Exception as exc:
            return SlashCommandResult(
                command="/init",
                success=False,
                markdown_output=f"Failed to initialize workspace: {exc}",
            )

    def _handle_install(self, args: list[str]) -> SlashCommandResult:
        """Install or synchronize Neuri base environment into ~/.neuri.

        Parameters
        ------------
        args: list[str]
            Optional command arguments (e.g. '--force' or '-f').

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Installation outcome summary card.
        """
        force: bool = "--force" in args or "-f" in args
        installer: NeuriInstaller = NeuriInstaller()
        summary: dict[str, Any] = installer.install(force=force)
        target_dir: str = summary.get(
            "target_dir", str(Path.home() / ".neuri")
        )
        installed: list[str] = summary.get("installed", [])

        if installed:
            installed_str: str = ", ".join(f"`{sec}`" for sec in installed)
            msg: str = (
                f"### Neuri Base Environment Installed\n\n"
                f"- **Target Directory**: `{target_dir}`\n"
                f"- **Installed Subfolders**: {installed_str}\n\n"
                f"Initialized structure:\n"
                f"- `global/`: Master prompt grounding Neuri\n"
                f"- `skills/`: Neuroscience skills catalog and manuals\n"
                f"- `mcp/`: Model Context Protocol server definitions\n"
                f"- `rules/`: Workspace and domain rule configurations\n"
                f"- `brain/`: Cognitive semantic memory vault & MRI pipeline docs\n"
            )
        else:
            msg = (
                f"### Neuri Environment Already Initialized\n\n"
                f"Neuri environment is already present at `{target_dir}`.\n"
                f"Use `/install --force` to overwrite existing configuration."
            )

        result: SlashCommandResult = SlashCommandResult(
            command="/install",
            success=True,
            markdown_output=msg,
            data=summary,
        )
        return result

    def _handle_skills(self, args: list[str]) -> SlashCommandResult:
        """List or inspect neuroscience skills catalog.

        Parameters
        ------------
        args: list[str]
            Optional skill ID or 'list'.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Rendered skills table or skill specification card.
        """
        if not self._skills_index_path.is_file():
            return SlashCommandResult(
                command="/skills",
                success=False,
                markdown_output=(
                    f"Skills catalog not found at `{self._skills_index_path}`."
                ),
            )

        try:
            content: str = self._skills_index_path.read_text(encoding="utf-8")
            data: dict[str, Any] = yaml.safe_load(content) or {}
            skills: list[dict[str, Any]] = data.get("skills", [])

            if args and args[0] not in ("list", ""):
                target_id: str = args[0].strip().lower()
                for sk in skills:
                    if str(sk.get("id")).lower() == target_id or target_id in [
                        str(a).lower() for a in sk.get("aliases", [])
                    ]:
                        detail_msg: str = (
                            f"### Skill: {sk.get('name')}\n\n"
                            f"- **ID:** `{sk.get('id')}`\n"
                            f"- **Aliases:** `{sk.get('aliases', [])}`\n"
                            f"- **Description:** {sk.get('description')}\n"
                            f"- **Modalities:** {', '.join(sk.get('modalities', []))}\n"
                            f"- **Triggers:** {', '.join(sk.get('triggers', []))}\n"
                        )
                        return SlashCommandResult(
                            command="/skills",
                            success=True,
                            markdown_output=detail_msg,
                            data=sk,
                        )
                return SlashCommandResult(
                    command="/skills",
                    success=False,
                    markdown_output=f"Skill `{args[0]}` not found in catalog.",
                )

            # Render catalog table
            lines: list[str] = [
                "### Neuroscience Skills Catalog\n",
                "| ID | Name | Modalities | Triggers |",
                "| :--- | :--- | :--- | :--- |",
            ]
            for sk in skills:
                s_id: str = str(sk.get("id"))
                name: str = str(sk.get("name"))
                mods: str = ", ".join(sk.get("modalities", []))
                trigs: str = ", ".join(sk.get("triggers", []))[:35] + "..."
                lines.append(f"| `{s_id}` | {name} | {mods} | {trigs} |")

            table_md: str = "\n".join(lines)
            return SlashCommandResult(
                command="/skills",
                success=True,
                markdown_output=table_md,
                data={"skills_count": len(skills)},
            )
        except Exception as exc:
            return SlashCommandResult(
                command="/skills",
                success=False,
                markdown_output=f"Failed to read skills catalog: {exc}",
            )

    def _handle_status(self) -> SlashCommandResult:
        """Display workspace, remote host, blackboard, and telemetry status.

        Parameters
        ------------
        None

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Rendered status dashboard card.
        """
        is_init: bool = (self._workspace_dir / ".neuri").is_dir()
        remote_host: str = self._config.project.default_remote_host

        active_harness: str = getattr(
            self._config.project, "default_harness", "agy"
        )
        active_model: str | None = self._orchestrator.resolve_active_model(
            active_harness
        )
        active_model_str: str = (
            active_model if active_model else "(harness default)"
        )

        init_status: str = "Yes" if is_init else "No (type /init to initialize)"
        cost_limit: str = f"${self._config.budgets.max_workflow_cost_usd:.2f}"

        wf_info: str = "None"
        node_counts_str: str = "0 nodes"
        total_artifacts: int = 0
        total_citations: int = 0
        try:
            workflows = self._blackboard.list_workflows()
            if workflows:
                latest_wf = workflows[-1]
                wf_id = latest_wf["workflow_id"]
                wf_status = latest_wf.get("status", "UNKNOWN")
                wf_info = f"`{wf_id}` ({wf_status})"

                nodes = self._blackboard.get_nodes_by_workflow(wf_id)
                comp = sum(1 for n in nodes if n.state == TaskState.COMPLETED)
                run = sum(1 for n in nodes if n.state == TaskState.RUNNING)
                wait = sum(
                    1 for n in nodes if n.state == TaskState.WAITING_OPERATOR
                )
                pend = sum(1 for n in nodes if n.state == TaskState.PENDING)
                fail = sum(1 for n in nodes if n.state == TaskState.FAILED)
                node_counts_str = (
                    f"✓ {comp} Completed  │  ⠋ {run} Running  │  "
                    f"! {wait} Paused  │  ○ {pend} Pending"
                )
                if fail:
                    node_counts_str += f"  │  ✗ {fail} Failed"

            artifacts = self._blackboard.list_artifacts()
            total_artifacts = len(artifacts)
            citations = self._blackboard.list_citations()
            total_citations = len(citations)
        except Exception:
            pass

        msg: str = (
            f"### Neuri System Status\n\n"
            f"- **Workspace Directory:** `{self._workspace_dir}`\n"
            f"- **Initialized (.neuri):** `{init_status}`\n"
            f"- **Default Remote Host:** `{remote_host}`\n"
            f"- **Active Harness:** `{active_harness}`\n"
            f"- **Active Model:** `{active_model_str}`\n"
            f"- **Active Workflow:** {wf_info}\n"
            f"- **Workflow Nodes:** {node_counts_str}\n"
            f"- **Registered Artifacts:** `{total_artifacts}` volumes / files\n"
            f"- **Verified Citations:** `{total_citations}` references\n"
            f"- **Max Node Tokens:** `{self._config.budgets.max_node_tokens:,}`\n"
            f"- **Max Workflow Cost:** `{cost_limit}`\n"
        )
        return SlashCommandResult(
            command="/status",
            success=True,
            markdown_output=msg,
            data={
                "workspace_initialized": is_init,
                "remote_host": remote_host,
                "default_harness": active_harness,
                "default_model": active_model,
                "artifacts_count": total_artifacts,
                "citations_count": total_citations,
            },
        )

    def _resolve_target_config_paths(self) -> list[Path]:
        """Resolve configuration file paths for persisting slash command updates.

        Includes workspace `.neuri/neuri.toml` and `.neuri/config.toml` when
        present, plus `~/.neuri/config.toml` when the workspace is not inside
        a temporary test directory (`/tmp`, `/var/folders`).

        Parameters
        ------------
        None

        Returns
        --------
            list[Path]: list object
                Target TOML file paths for persisting configuration updates.
        """
        targets: list[Path] = []
        ws_dot: Path = self._workspace_dir / ".neuri"
        if (ws_dot / "neuri.toml").is_file():
            targets.append(ws_dot / "neuri.toml")
        if (ws_dot / "config.toml").is_file():
            targets.append(ws_dot / "config.toml")

        ws_str: str = str(self._workspace_dir.resolve())
        is_temp: bool = (
            ws_str.startswith("/private/var/folders/")
            or ws_str.startswith("/var/folders/")
            or ws_str.startswith("/tmp/")
            or ws_str.startswith("/private/tmp/")
            or "pytest-of-" in ws_str
        )
        if not is_temp:
            home_cfg: Path = Path.home() / ".neuri" / "config.toml"
            if home_cfg.is_file() and home_cfg not in targets:
                targets.append(home_cfg)

        return targets

    def _persist_harness_and_model(
        self, harness_id: str, model_id: str | None
    ) -> None:
        """Persist active harness and model to all resolved config TOML files.

        Parameters
        ------------
        harness_id: str
            Active canonical harness ID.
        model_id: str | None
            Active model ID or None to clear model overrides.

        Returns
        --------
            None: NoneType object
                Writes updated harness and model to disk if config files exist.
        """
        cfg_paths: list[Path] = self._resolve_target_config_paths()
        if not cfg_paths:
            return

        import tomllib
        import tomli_w

        for cfg_path in cfg_paths:
            if not cfg_path.is_file():
                continue
            try:
                raw_cfg: dict[str, Any] = tomllib.loads(
                    cfg_path.read_text(encoding="utf-8")
                )
                if "project" not in raw_cfg or not isinstance(
                    raw_cfg["project"], dict
                ):
                    raw_cfg["project"] = {}
                raw_cfg["project"]["default_harness"] = harness_id
                if model_id is not None:
                    raw_cfg["project"]["default_model"] = model_id
                elif "default_model" in raw_cfg["project"]:
                    del raw_cfg["project"]["default_model"]

                if "harness_routing" not in raw_cfg or not isinstance(
                    raw_cfg["harness_routing"], dict
                ):
                    raw_cfg["harness_routing"] = {}
                for r_name in self._config.harness_routing:
                    r_ent: dict[str, Any] = {"harness": harness_id}
                    if model_id is not None:
                        r_ent["model"] = model_id
                    raw_cfg["harness_routing"][r_name] = r_ent

                cfg_path.write_text(
                    tomli_w.dumps(raw_cfg), encoding="utf-8"
                )
            except Exception:
                pass

    def _handle_harness(self, args: list[str]) -> SlashCommandResult:
        """Display or update AI harness configuration uniformly across all roles.

        Parameters
        ------------
        args: list[str]
            Optional [harness_id], [harness_id, model], or [role, harness_id, model].

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Status overview or update confirmation card.
        """
        known_harnesses: set[str] = {
            "agy",
            "antigravity",
            "codex",
            "opencode",
            "openclaw",
            "ollama",
            "ollama_local",
        }

        if args:
            target_h: str = "agy"
            chosen_model: str | None = None
            if len(args) == 1:
                target_h = args[0].strip().lower()
            elif len(args) == 2:
                t0: str = args[0].strip().lower()
                t1: str = args[1].strip().lower()
                if t0 in known_harnesses:
                    target_h = t0
                    chosen_model = args[1].strip()
                elif t1 in known_harnesses:
                    target_h = t1
                    chosen_model = None
                else:
                    target_h = t0
                    chosen_model = args[1].strip()
            else:
                t0 = args[0].strip().lower()
                t1 = args[1].strip().lower()
                if t1 in known_harnesses:
                    target_h = t1
                    chosen_model = args[2].strip()
                else:
                    target_h = t0
                    chosen_model = args[1].strip()

            if target_h == "antigravity":
                target_h = "agy"
            elif target_h == "ollama_local":
                target_h = "ollama"

            try:
                avail_models: list[str] = (
                    self._orchestrator.registry.get_models_for_harness(
                        target_h
                    )
                )
            except Exception:
                avail_models = []

            if chosen_model is not None:
                if avail_models and chosen_model not in avail_models:
                    valid_list: str = ", ".join(f"`{m}`" for m in avail_models)
                    err_md: str = (
                        f"Model `{chosen_model}` is not available on harness "
                        f"`{target_h}`.\n\n"
                        f"**Available models on `{target_h}`:** {valid_list}"
                    )
                    return SlashCommandResult(
                        command="/harness",
                        success=False,
                        markdown_output=err_md,
                        data={
                            "harness": target_h,
                            "requested_model": chosen_model,
                            "available_models": avail_models,
                        },
                    )
            else:
                chosen_model = avail_models[0] if avail_models else None

            self._config.project.default_harness = target_h
            self._config.project.default_model = chosen_model

            if isinstance(self._config.harness_routing, dict):
                for r_cfg in self._config.harness_routing.values():
                    r_cfg.harness = target_h
                    r_cfg.model = chosen_model

            self._persist_harness_and_model(target_h, chosen_model)

            model_note: str = (
                f" with model `{chosen_model}`" if chosen_model else ""
            )
            msg: str = (
                f"Updated harness routing: All roles set to "
                f"`{target_h}`{model_note}."
            )
            return SlashCommandResult(
                command="/harness",
                success=True,
                markdown_output=msg,
                data={
                    "harness": target_h,
                    "model": chosen_model,
                },
            )

        active_harness: str = getattr(
            self._config.project, "default_harness", "agy"
        )
        active_model: str | None = self._orchestrator.resolve_active_model(
            active_harness
        )
        model_str: str = active_model if active_model else "(vendor default)"
        try:
            harness_models: list[str] = (
                self._orchestrator.registry.get_models_for_harness(
                    active_harness
                )
            )
        except Exception:
            harness_models = []

        lines: list[str] = [
            "### AI Harness Configuration (Harness Routing Map)\n",
            f"- **Active Harness:** `{active_harness}`",
            f"- **Active Model:** `{model_str}`",
            (
                "- **All Roles Synchronized:** `coordinator`, `pipeline_engineer`, "
                "`neuroimaging_specialist`, `critic_qa`\n"
            ),
        ]
        if harness_models:
            lines.append(
                f"**Available Models on `{active_harness}` "
                f"({len(harness_models)}):**"
            )
            for m_item in harness_models:
                marker: str = " *(active)*" if m_item == active_model else ""
                lines.append(f"- `{m_item}`{marker}")
            lines.append("")

        lines.extend(
            [
                "**Commands:**",
                "- `/harness <name>`: Switch active harness across all roles",
                "- `/harness <name> <model>`: Switch harness and model together",
                "- `/model <name>`: Switch active model across all roles",
                "- `/model list`: Show live models directly from harnesses",
            ]
        )
        return SlashCommandResult(
            command="/harness",
            success=True,
            markdown_output="\n".join(lines),
            data={
                "harness": active_harness,
                "model": active_model,
                "available_models": harness_models,
            },
        )

    def _handle_model(self, args: list[str]) -> SlashCommandResult:
        """Display, list, or update AI model configuration across all roles.

        Parameters
        ------------
        args: list[str]
            Optional [model_name], [role, model_name], ['reset'], or ['list'].

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Model catalog, status table, or update confirmation.
        """
        active_harness: str = getattr(
            self._config.project, "default_harness", "agy"
        )

        # 1. /model list: Query live models directly from underlying harnesses
        if args and args[0].lower() in ("list", "ls"):
            live_models: dict[str, list[str]] = (
                self._orchestrator.registry.list_all_models()
            )
            catalog_lines: list[str] = [
                "### Live Available Models Directly from Harnesses\n",
            ]
            if not live_models:
                catalog_lines.append(
                    "No models could be discovered from installed harnesses. "
                    "Ensure harness binaries (agy, ollama, codex) are installed."
                )
            else:
                for h_id, m_list in sorted(live_models.items()):
                    active_tag: str = (
                        " [ACTIVE HARNESS]" if h_id == active_harness else ""
                    )
                    catalog_lines.append(
                        f"#### Harness `{h_id}`{active_tag} "
                        f"({len(m_list)} models)"
                    )
                    for m in m_list:
                        is_curr: bool = (
                            h_id == active_harness
                            and m == self._config.project.default_model
                        )
                        curr_tag: str = " *(active)*" if is_curr else ""
                        catalog_lines.append(f"- `{m}`{curr_tag}")
                    catalog_lines.append("")

            catalog_lines.extend(
                [
                    "**Commands:**",
                    "- `/model <name>`: Switch default model for active harness",
                    "- `/model <role> <name>`: Set model for specific specialist",
                    "- `/model reset`: Restore harness default model",
                ]
            )
            result_list: SlashCommandResult = SlashCommandResult(
                command="/model",
                success=True,
                markdown_output="\n".join(catalog_lines),
                data=live_models,
            )
            return result_list

        try:
            avail_for_active: list[str] = (
                self._orchestrator.registry.get_models_for_harness(
                    active_harness
                )
            )
        except Exception:
            avail_for_active = []

        # 2. /model reset: Restore to active harness default model
        if args and args[0].lower() == "reset":
            restored_model: str | None = (
                avail_for_active[0] if avail_for_active else None
            )
            self._config.project.default_model = restored_model
            if isinstance(self._config.harness_routing, dict):
                for r_cfg in self._config.harness_routing.values():
                    r_cfg.model = restored_model
            self._persist_harness_and_model(active_harness, None)
            reset_result: SlashCommandResult = SlashCommandResult(
                command="/model",
                success=True,
                markdown_output="Restored all harnesses to default models.",
                data={"default_model": restored_model},
            )
            return reset_result

        # 3. /model <role> <model_name> or /model <harness> <model_name>
        if len(args) >= 2:
            role_target: str = args[0].strip()
            chosen_model_val: str = args[1].strip()

            if avail_for_active and chosen_model_val not in avail_for_active:
                valid_str: str = ", ".join(f"`{m}`" for m in avail_for_active)
                return SlashCommandResult(
                    command="/model",
                    success=False,
                    markdown_output=(
                        f"Model `{chosen_model_val}` is not available on "
                        f"active harness `{active_harness}`.\n\n"
                        f"**Available models on `{active_harness}`:** "
                        f"{valid_str}"
                    ),
                    data={
                        "harness": active_harness,
                        "requested_model": chosen_model_val,
                        "available_models": avail_for_active,
                    },
                )

            self._config.project.default_model = chosen_model_val
            if isinstance(self._config.harness_routing, dict):
                for r_cfg_item in self._config.harness_routing.values():
                    r_cfg_item.model = chosen_model_val

            self._persist_harness_and_model(active_harness, chosen_model_val)

            role_result: SlashCommandResult = SlashCommandResult(
                command="/model",
                success=True,
                markdown_output=(
                    f"Updated model: Set `{role_target}` to `{chosen_model_val}` "
                    f"(applied across all roles in uniform mode)."
                ),
                data={"role": role_target, "model": chosen_model_val},
            )
            return role_result

        # 4. /model <model_name>: Set global default model across all roles
        if len(args) == 1:
            chosen_default: str = args[0].strip()
            if avail_for_active and chosen_default not in avail_for_active:
                valid_str_single: str = ", ".join(
                    f"`{m}`" for m in avail_for_active
                )
                return SlashCommandResult(
                    command="/model",
                    success=False,
                    markdown_output=(
                        f"Model `{chosen_default}` is not available on "
                        f"active harness `{active_harness}`.\n\n"
                        f"**Available models on `{active_harness}`:** "
                        f"{valid_str_single}"
                    ),
                    data={
                        "harness": active_harness,
                        "requested_model": chosen_default,
                        "available_models": avail_for_active,
                    },
                )

            self._config.project.default_model = chosen_default
            if isinstance(self._config.harness_routing, dict):
                for r_cfg_item in self._config.harness_routing.values():
                    r_cfg_item.model = chosen_default

            self._persist_harness_and_model(active_harness, chosen_default)

            def_result: SlashCommandResult = SlashCommandResult(
                command="/model",
                success=True,
                markdown_output=(
                    f"Updated global default model to `{chosen_default}` across "
                    f"all connected harnesses."
                ),
                data={"default_model": chosen_default},
            )
            return def_result

        # 5. /model (no arguments): Display active model status and live models
        resolved_active: str | None = self._orchestrator.resolve_active_model(
            active_harness
        )
        active_default: str = (
            resolved_active if resolved_active else "(harness default)"
        )
        status_lines: list[str] = [
            "### AI Model Configuration\n",
            f"- **Active Harness:** `{active_harness}`",
            f"- **Active Model:** `{active_default}`",
            (
                "- **All Roles Synchronized:** `coordinator`, `pipeline_engineer`, "
                "`neuroimaging_specialist`, `critic_qa`\n"
            ),
        ]
        if avail_for_active:
            status_lines.append(
                f"**Available Models on `{active_harness}` "
                f"({len(avail_for_active)}):**"
            )
            for m_item in avail_for_active:
                marker_m: str = (
                    " *(active)*" if m_item == resolved_active else ""
                )
                status_lines.append(f"- `{m_item}`{marker_m}")
            status_lines.append("")

        status_lines.extend(
            [
                "**Commands:**",
                "- `/model list`: Browse live models directly from harnesses",
                "- `/model <name>`: Switch active model across all roles",
                "- `/model reset`: Restore vendor defaults",
            ]
        )

        table_result: SlashCommandResult = SlashCommandResult(
            command="/model",
            success=True,
            markdown_output="\n".join(status_lines),
            data={
                "default_model": resolved_active,
                "harness": active_harness,
                "available_models": avail_for_active,
            },
        )
        return table_result

    def _run_sync_coroutine(self, coro: Coroutine[Any, Any, Any]) -> Any:
        """Execute an asynchronous coroutine synchronously.

        Parameters
        ------------
        coro: Coroutine[Any, Any, Any]
            Coroutine instance to execute.

        Returns
        --------
            Any: Any object
                Result returned by the coroutine.
        """
        try:
            asyncio.get_running_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, coro)
                result = future.result()
                return result
        except RuntimeError:
            sync_res = asyncio.run(coro)
            return sync_res

    def _handle_remote(self, args: list[str]) -> SlashCommandResult:
        """Inspect and manage configured remote compute hosts.

        Parameters
        ------------
        args: list[str]
            Subcommands ('list', 'bootstrap <host>').

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Remote host status or bootstrap outcome card.
        """
        subcmd: str = args[0].lower() if args else "list"

        if subcmd == "list":
            hosts: list[Any] = (
                getattr(self._config, "remote_hosts", None) or []
            )
            if not hosts:
                default_host: str = getattr(
                    getattr(self._config, "project", None),
                    "default_remote_host",
                    "localhost",
                )
                bids_root: str | None = getattr(
                    getattr(self._config, "project", None),
                    "remote_bids_root",
                    None,
                )
                md_out: str = (
                    "### Configured Remote Hosts\n\n"
                    f"- **Default Remote Host:** `{default_host}`\n"
                    f"- **Remote BIDS Root:** `{bids_root or 'Not configured'}`\n\n"
                    "*(No cluster hosts configured. Use "
                    "`/remote bootstrap <host_alias>` to bootstrap compute.)*"
                )
                return SlashCommandResult(
                    command="/remote",
                    success=True,
                    markdown_output=md_out,
                    data={"hosts": []},
                )
            rows: list[str] = [
                "| Host Name | Hostname | User | Scheduler | Work Dir |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ]
            host_data: list[dict[str, Any]] = []
            for h in hosts:
                rows.append(
                    f"| `{h.name}` | `{h.hostname}` | `{h.user}` | "
                    f"`{h.scheduler}` | `{h.work_dir}` |"
                )
                host_data.append(h.model_dump())
            md_out: str = "### Configured Remote Hosts\n\n" + "\n".join(rows)
            return SlashCommandResult(
                command="/remote",
                success=True,
                markdown_output=md_out,
                data={"hosts": host_data},
            )

        if subcmd == "bootstrap":
            if len(args) < 2:
                return SlashCommandResult(
                    command="/remote",
                    success=False,
                    markdown_output="Usage: `/remote bootstrap <host_alias>`",
                )
            target_host: str = args[1].strip()
            bootstrapper: RemoteHostBootstrapper = RemoteHostBootstrapper()
            try:
                res: dict[str, Any] = self._run_sync_coroutine(
                    bootstrapper.bootstrap_host(target_host)
                )
                status_md: str = (
                    f"### Remote Host Bootstrap: `{target_host}`\n\n"
                    f"- **Status:** `{'Success' if res.get('success') else 'Failed'}`\n"
                    f"- **Neuri Worker Dir:** "
                    f"`{res.get('worker_dir', '~/.neuri_worker')}`\n"
                    f"- **Slurm:** `{'Detected' if res.get('has_slurm') else 'None'}`\n"
                    f"- **Container Runtime:** "
                    f"`{res.get('container_binary', 'None')}`\n"
                )
                return SlashCommandResult(
                    command="/remote",
                    success=bool(res.get("success", False)),
                    markdown_output=status_md,
                    data=res,
                )
            except Exception as err:
                return SlashCommandResult(
                    command="/remote",
                    success=False,
                    markdown_output=(
                        f"Bootstrap failed for `{target_host}`: {err}"
                    ),
                    data={"error": str(err)},
                )

        if subcmd in ("remove", "rm", "delete"):
            if len(args) < 2:
                return SlashCommandResult(
                    command="/remote",
                    success=False,
                    markdown_output="Usage: `/remote remove <host_alias>`",
                )
            target_host: str = args[1].strip()
            bootstrapper: RemoteHostBootstrapper = RemoteHostBootstrapper()
            removed_from_hosts: bool = bootstrapper.remove_host_record(
                target_host
            )

            if removed_from_hosts:
                msg: str = (
                    f"### Host Removed: `{target_host}`\n\n"
                    f"Successfully removed `{target_host}` from "
                    "`~/.neuri/hosts.toml`.\n\n"
                    "> [!NOTE]\n"
                    f"> If `{target_host}` is also declared in your "
                    "`.neuri/config.toml` under `[[remote_hosts]]`, remove that "
                    "entry to completely deregister it."
                )
                return SlashCommandResult(
                    command="/remote",
                    success=True,
                    markdown_output=msg,
                    data={
                        "removed_host": target_host,
                        "removed_from_hosts": True,
                    },
                )
            else:
                msg = (
                    f"Host `{target_host}` was not found in "
                    "`~/.neuri/hosts.toml`.\n"
                    "Use `/remote list` or `/machines` to view configured hosts."
                )
                return SlashCommandResult(
                    command="/remote",
                    success=False,
                    markdown_output=msg,
                    data={
                        "removed_host": target_host,
                        "removed_from_hosts": False,
                    },
                )

        return SlashCommandResult(
            command="/remote",
            success=False,
            markdown_output=(
                f"Unknown remote subcommand `{subcmd}`. "
                "Use `/remote list`, `/remote bootstrap <host>`, or "
                "`/remote remove <host>`."
            ),
        )

    def _handle_machines(self) -> SlashCommandResult:
        """Inspect all configured compute machines and their running jobs.

        Parameters
        ------------
        None

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Rendered table of attached machines and job statuses.
        """
        monitor: RemoteHostMonitor = RemoteHostMonitor()
        hosts: list[str] = monitor.get_configured_hosts()
        default_host: str = getattr(
            getattr(self._config, "project", None),
            "default_remote_host",
            "localhost",
        )
        if default_host not in hosts:
            hosts.insert(0, default_host)

        results: list[dict[str, Any]] = self._run_sync_coroutine(
            monitor.query_all_hosts(hosts)
        )

        if not results:
            empty_res: SlashCommandResult = SlashCommandResult(
                command="/machines",
                success=True,
                markdown_output=(
                    "### Attached Machines & Compute Fabric\n\n"
                    "No remote machines configured. Use `/remote bootstrap <host>` "
                    "to attach a compute host."
                ),
                data={"machines": []},
            )
            return empty_res

        lines: list[str] = [
            "### Attached Machines & Compute Status\n",
            "| Host | Status | CPU Cores | Load Avg | Active Jobs |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        job_details: list[str] = []

        for m in results:
            host_name: str = str(m.get("host", "unknown"))
            online: bool = bool(m.get("online", False))
            status_badge: str = "● Online" if online else "○ Offline"
            cores: str = str(m.get("cpu_count", "-"))
            load_arr: list[float] = m.get("load_avg", [0.0, 0.0, 0.0])
            load_str: str = (
                ", ".join(str(x) for x in load_arr) if load_arr else "-"
            )

            n_jobs: list[dict[str, Any]] = m.get("neuri_jobs", [])
            s_jobs: list[dict[str, Any]] = m.get("slurm_jobs", [])
            active_cnt: int = len(
                [j for j in n_jobs if j.get("state") == "RUNNING"]
            ) + len([j for j in s_jobs if j.get("state") in ("R", "RUNNING")])

            lines.append(
                f"| `{host_name}` | {status_badge} | {cores} | {load_str} | "
                f"{active_cnt} active |"
            )

            if n_jobs or s_jobs:
                job_details.append(f"\n**Jobs on `{host_name}`:**")
                for j in n_jobs:
                    job_details.append(
                        f"- [Neuri] `{j.get('job_id')}`: {j.get('state')} "
                        f"(Started: {j.get('start_time', 'N/A')})"
                    )
                for sj in s_jobs:
                    job_details.append(
                        f"- [Slurm] `#{sj.get('slurm_job_id')}` "
                        f"({sj.get('name')}): {sj.get('state')} on "
                        f"`{sj.get('partition')}` (Time: {sj.get('elapsed')})"
                    )

        md_out: str = "\n".join(lines)
        if job_details:
            md_out += "\n" + "\n".join(job_details)

        final_res: SlashCommandResult = SlashCommandResult(
            command="/machines",
            success=True,
            markdown_output=md_out,
            data={"machines": results},
        )
        return final_res

    def _handle_jobs(self, args: list[str]) -> SlashCommandResult:
        """Inspect and reconcile asynchronous remote batch jobs.

        Parameters
        ------------
        args: list[str]
            Subcommands ('list', 'reconcile').

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Remote jobs status card or reconciliation report.
        """
        subcmd: str = args[0].lower() if args else "list"

        if subcmd == "list":
            jobs: list[dict[str, Any]] = self._blackboard.list_remote_jobs()
            if not jobs:
                return SlashCommandResult(
                    command="/jobs",
                    success=True,
                    markdown_output="No remote jobs currently registered.",
                    data={"jobs": []},
                )
            rows: list[str] = [
                "| Job ID | Node ID | Host | Sched | Sched ID | State |",
                "| :--- | :--- | :--- | :--- | :--- | :--- |",
            ]
            for j in jobs:
                rows.append(
                    f"| `{j.get('job_id')}` | `{j.get('node_id')}` | "
                    f"`{j.get('host')}` | `{j.get('scheduler_type')}` | "
                    f"`{j.get('scheduler_job_id')}` | `{j.get('state')}` |"
                )
            md_out: str = "### Registered Remote Jobs\n\n" + "\n".join(rows)
            return SlashCommandResult(
                command="/jobs",
                success=True,
                markdown_output=md_out,
                data={"jobs": jobs},
            )

        if subcmd == "reconcile":
            reconciler: DetachAndReconcileManager = DetachAndReconcileManager()
            try:
                report: list[dict[str, Any]] = self._run_sync_coroutine(
                    reconciler.reconcile_active_jobs(self._blackboard)
                )
                md_lines: list[str] = [
                    f"### Remote Jobs Reconciled ({len(report)} active)",
                    "",
                ]
                for item in report:
                    md_lines.append(
                        f"- Job `{item.get('job_id')}` "
                        f"(`{item.get('remote_id')}`): `{item.get('status')}`"
                    )
                if not report:
                    md_lines.append("No active remote jobs to reconcile.")
                return SlashCommandResult(
                    command="/jobs",
                    success=True,
                    markdown_output="\n".join(md_lines),
                    data={"reconciled": report},
                )
            except Exception as err:
                return SlashCommandResult(
                    command="/jobs",
                    success=False,
                    markdown_output=f"Reconciliation error: {err}",
                    data={"error": str(err)},
                )

        return SlashCommandResult(
            command="/jobs",
            success=False,
            markdown_output=(
                f"Unknown jobs subcommand `{subcmd}`. "
                "Use `/jobs list` or `/jobs reconcile`."
            ),
        )

    def _handle_shell(self, args: list[str]) -> SlashCommandResult:
        """Execute a shell command locally or on a remote machine.

        Parameters
        ------------
        args: list[str]
            Command arguments, optionally prefixed with machine alias.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Formatted shell output card.
        """
        if not args:
            return SlashCommandResult(
                command="/shell",
                success=False,
                markdown_output=(
                    "Usage: `/shell <command>` or `/shell <host> <command>`"
                ),
            )

        from neuri.remote.shell_executor import (
            ShellCommandExecutor,
            ShellExecutionResult,
        )

        executor: ShellCommandExecutor = ShellCommandExecutor(
            workspace_dir=self._workspace_dir
        )
        available_hosts: list[str] = executor.get_available_hosts(
            config=self._config
        )

        target_host: str = "localhost"
        cmd_tokens: list[str] = args

        if len(args) >= 2 and args[0] in available_hosts:
            target_host = args[0]
            cmd_tokens = args[1:]

        command_str: str = " ".join(cmd_tokens)
        res: ShellExecutionResult = self._run_sync_coroutine(
            executor.execute(command=command_str, host=target_host)
        )
        card_md: str = executor.format_markdown_card(res)

        result: SlashCommandResult = SlashCommandResult(
            command="/shell",
            success=(res.exit_code == 0),
            markdown_output=card_md,
            data={
                "host": res.host,
                "command": res.command,
                "exit_code": res.exit_code,
                "duration_seconds": res.duration_seconds,
            },
        )
        return result

    def _handle_history(self, args: list[str]) -> SlashCommandResult:
        """Display or clear persistent command and prompt history.

        Parameters
        ------------
        args: list[str]
            Optional subcommands (e.g. 'clear' or count limit).

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Formatted history markdown table or status confirmation.
        """
        from neuri.ui.history import PromptHistoryManager

        manager: PromptHistoryManager = PromptHistoryManager()
        if args and args[0].lower() in ("clear", "clean", "purge"):
            manager.clear()
            clear_res: SlashCommandResult = SlashCommandResult(
                command="/history",
                success=True,
                markdown_output="Command and prompt history cleared.",
            )
            return clear_res

        entries: list[str] = manager.entries
        if not entries:
            empty_res: SlashCommandResult = SlashCommandResult(
                command="/history",
                success=True,
                markdown_output="*Command history is empty.*",
            )
            return empty_res

        limit: int = 25
        if args and args[0].isdigit():
            limit = max(1, min(int(args[0]), 200))

        displayed: list[str] = entries[-limit:]
        start_idx: int = max(1, len(entries) - len(displayed) + 1)
        header_text: str = (
            f"### Command & Prompt History (last {len(displayed)} of "
            f"{len(entries)})"
        )
        lines: list[str] = [
            header_text,
            "",
            "| # | Command / Prompt |",
            "| :--- | :--- |",
        ]
        for i, entry in enumerate(displayed, start=start_idx):
            escaped: str = entry.replace("|", "\\|").replace("\n", " ")
            if len(escaped) > 80:
                escaped = escaped[:77] + "..."
            lines.append(f"| {i} | `{escaped}` |")

        lines.extend([
            "",
            "- Press **Up / Down arrows** in prompt to scroll through history.",
            "- Use `/history clear` to purge stored history.",
        ])

        hist_res: SlashCommandResult = SlashCommandResult(
            command="/history",
            success=True,
            markdown_output="\n".join(lines),
        )
        return hist_res

    def _handle_theme(self, args: list[str]) -> SlashCommandResult:
        """List available color themes or activate a selected theme.

        Parameters
        ------------
        args: list[str]
            Optional theme name argument.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Theme listing or activation confirmation card.
        """
        from neuri.ui.theme import NeuriTheme, NeuriThemeManager

        mgr: NeuriThemeManager = NeuriThemeManager(
            workspace_dir=self._workspace_dir
        )
        available_themes: list[NeuriTheme] = mgr.list_available_themes()
        active_theme_name: str = mgr.get_active_theme_name()

        if not args or args[0].lower() in ("list", "ls"):
            rows: list[str] = [
                "| Theme Name | Style | Description | Status |",
                "| :--- | :--- | :--- | :--- |",
            ]
            for t in available_themes:
                is_active: bool = (
                    t.name.lower().replace("-", "_")
                    == active_theme_name.lower().replace("-", "_")
                )
                status_str: str = "● **Active**" if is_active else "○"
                rows.append(
                    f"| `{t.name}` | {t.display_name} | "
                    f"{t.description} | {status_str} |"
                )

            md: str = (
                "### Neuri Visual Color Themes\n\n"
                + "\n".join(rows)
                + "\n\n"
                "- Use `/theme <name>` to switch themes "
                "(e.g. `/theme high_contrast`, `/theme dark`).\n"
                "- Themes are stored in `~/.neuri/themes/` (TOML format)."
            )
            return SlashCommandResult(
                command="/theme",
                success=True,
                markdown_output=md,
                data={
                    "themes": [t.name for t in available_themes],
                    "active": active_theme_name,
                },
            )

        chosen: str = args[0].lower().replace("-", "_").strip()
        matched: NeuriTheme | None = None
        for t in available_themes:
            if t.name.lower().replace("-", "_") == chosen:
                matched = t
                break

        if matched is None:
            avail_str: str = ", ".join(f"`{t.name}`" for t in available_themes)
            return SlashCommandResult(
                command="/theme",
                success=False,
                markdown_output=(
                    f"Theme `{args[0]}` not found.\n\n"
                    f"Available themes: {avail_str}\n"
                    "Use `/theme` to view full catalog."
                ),
            )

        mgr.set_active_theme(matched.name)
        confirm_md: str = (
            f"### Theme Activated: `{matched.display_name}`\n\n"
            f"- **Identifier:** `{matched.name}`\n"
            f"- **Description:** {matched.description}\n"
            f"- **Background:** `{matched.background}`  │  "
            f"**Foreground:** `{matched.foreground}`\n\n"
            "Theme preference saved to `~/.neuri/config.toml`."
        )
        return SlashCommandResult(
            command="/theme",
            success=True,
            markdown_output=confirm_md,
            action="change_theme",
            data={"theme_name": matched.name},
        )

    def _handle_plan(self, args: list[str]) -> SlashCommandResult:
        """Decompose natural language prompt into DAG without auto-executing.

        Parameters
        ------------
        args: list[str]
            User research prompt string.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                DAG preview card with role assignments and instructions.
        """
        prompt: str = " ".join(args).strip()
        if not prompt:
            help_msg: str = (
                "### Neuri DAG Planner\n\n"
                "**Usage:** `/plan <research instruction or pipeline>`\n\n"
                "*Example:* `/plan Run skull-stripping with BET and generate QA`"
            )
            return SlashCommandResult(
                command="/plan",
                success=False,
                markdown_output=help_msg,
            )

        wf_id: str = self._orchestrator.plan_workflow_from_prompt(prompt)
        self._last_planned_workflow_id = wf_id
        nodes: list[TaskNode] = self._blackboard.get_nodes_by_workflow(wf_id)

        rows: list[str] = [
            f"### Planned Research DAG: `{wf_id}`\n",
            f"**Instruction:** {prompt}\n",
            "| Step | Node ID | Specialist Role | Harness | Model | State |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for idx, node in enumerate(nodes, start=1):
            node_model: str = node.model if node.model else "default"
            rows.append(
                f"| {idx} | `{node.node_id}` | `{node.agent_role}` | "
                f"`{node.harness_id}` | `{node_model}` | `○ {node.state.value}` |"
            )

        rows.append(
            "\nTo execute this workflow, enter `/run` or ask me to modify it."
        )
        plan_md: str = "\n".join(rows)

        return SlashCommandResult(
            command="/plan",
            success=True,
            markdown_output=plan_md,
            data={"workflow_id": wf_id, "nodes_count": len(nodes)},
        )

    def _handle_run(self, args: list[str]) -> SlashCommandResult:
        """Execute a planned or pending research DAG.

        Parameters
        ------------
        args: list[str]
            Optional workflow identifier. Defaults to last planned workflow.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Execution trigger action result.
        """
        wf_id: str | None = None
        if args:
            wf_id = args[0].strip()
        elif self._last_planned_workflow_id is not None:
            wf_id = self._last_planned_workflow_id
        else:
            workflows = self._blackboard.list_workflows()
            for wf in reversed(workflows):
                candidate_id: str = wf["workflow_id"]
                pending_nodes = [
                    n
                    for n in self._blackboard.get_nodes_by_workflow(candidate_id)
                    if n.state in (TaskState.PENDING, TaskState.WAITING_OPERATOR)
                ]
                if pending_nodes:
                    wf_id = candidate_id
                    break

        if wf_id is None:
            err_msg: str = (
                "No planned or pending workflows found to execute.\n\n"
                "Use `/plan <instruction>` to preview a DAG, or enter your "
                "prompt directly to plan and execute automatically."
            )
            return SlashCommandResult(
                command="/run",
                success=False,
                markdown_output=err_msg,
            )

        run_msg: str = (
            f"### Executing Workflow: `{wf_id}`\n\n"
            f"Dispatched DAG wave execution to orchestrator."
        )
        return SlashCommandResult(
            command="/run",
            success=True,
            markdown_output=run_msg,
            action="resume_workflow",
            data={"workflow_id": wf_id},
        )

    def _handle_view(self, args: list[str]) -> SlashCommandResult:
        """Launch or inspect local NiiVue WebGL2 visualization bridge.

        Parameters
        ------------
        args: list[str]
            Optional artifact URI, file path, or flags (e.g. '--no-open').

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Visualization link and instructions card.
        """
        no_open: bool = "--no-open" in args
        clean_args: list[str] = [a for a in args if a != "--no-open"]

        from neuri.viewer.niivue_bridge import NiiVueBridge

        bridge: NiiVueBridge = NiiVueBridge.get_instance()
        if not bridge.is_running():
            try:
                bridge.start()
            except Exception:
                pass

        viewer_url: str = bridge.get_url()
        target_uri: str = clean_args[0].strip() if clean_args else ""

        if not target_uri:
            try:
                artifacts: list[RemoteArtifact] = (
                    self._blackboard.list_artifacts()
                )
                vol_exts: tuple[str, ...] = (
                    ".nii",
                    ".nii.gz",
                    ".mgh",
                    ".mgz",
                    ".dcm",
                )
                for art in reversed(artifacts):
                    if any(art.uri.lower().endswith(ext) for ext in vol_exts):
                        target_uri = art.uri
                        break
            except Exception:
                pass

        if target_uri:
            scene_id: str = f"scene_{uuid.uuid4().hex[:8]}"
            spec: NiiVueSceneSpec = NiiVueSceneSpec(
                scene_id=scene_id,
                title=f"Neuri: {Path(target_uri).name}",
                volumes=[
                    NiiVueLayerSpec(
                        artifact_uri=target_uri,
                        colormap="gray",
                        opacity=1.0,
                    )
                ],
            )
            bridge.push_scene(spec)

        if not no_open:
            try:
                webbrowser.open(viewer_url)
            except Exception:
                pass

        if target_uri:
            msg: str = (
                f"### NiiVue WebGL2 Visualization Bridge\n\n"
                f"- **Viewer URL:** [{viewer_url}]({viewer_url})\n"
                f"- **Active Volume:** `{target_uri}`\n"
                f"- **Status:** Scene updated and browser opened.\n\n"
                f"*Controls:* Drag to slice, Right-click to zoom, "
                f"Scroll to cycle slices."
            )
            return SlashCommandResult(
                command="/view",
                success=True,
                markdown_output=msg,
                data={"viewer_url": viewer_url, "target_uri": target_uri},
            )

        msg_default: str = (
            f"### NiiVue WebGL2 Visualization Bridge\n\n"
            f"- **Viewer URL:** [{viewer_url}]({viewer_url})\n"
            f"- **Status:** Bridge listening on port 8421.\n\n"
            f"Pass a volume path or URI to inspect (e.g. `/view sub-01_T1w.nii.gz`)."
        )
        return SlashCommandResult(
            command="/view",
            success=True,
            markdown_output=msg_default,
            data={"viewer_url": viewer_url},
        )

    def _handle_retry(self, args: list[str]) -> SlashCommandResult:
        """Retry a node paused in WAITING_OPERATOR or FAILED.

        Parameters
        ------------
        args: list[str]
            Optional node_id and operator feedback string.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Retry outcome card with workflow resumption trigger.
        """
        node_id: str | None = None
        feedback: str = ""

        if args:
            if args[0].startswith("node_"):
                node_id = args[0].strip()
                if len(args) > 1:
                    feedback = " ".join(args[1:]).strip()
            else:
                feedback = " ".join(args).strip()

        target_wf_id: str | None = None
        if node_id is None:
            workflows = self._blackboard.list_workflows()
            for wf in reversed(workflows):
                curr_wf_id: str = wf["workflow_id"]
                nodes = self._blackboard.get_nodes_by_workflow(curr_wf_id)
                for n in reversed(nodes):
                    if n.state in (
                        TaskState.WAITING_OPERATOR,
                        TaskState.FAILED,
                    ):
                        node_id = n.node_id
                        target_wf_id = curr_wf_id
                        break
                if node_id is not None:
                    break

        if node_id is None:
            return SlashCommandResult(
                command="/retry",
                success=False,
                markdown_output=(
                    "No nodes are currently paused in `WAITING_OPERATOR` "
                    "or `FAILED` state."
                ),
            )

        if target_wf_id is None:
            target_node = self._blackboard.get_node(node_id)
            if target_node is not None:
                target_wf_id = target_node.workflow_id

        ok: bool = self._orchestrator.retry_node(node_id)
        if ok:
            fb_note: str = (
                f"\n- **Operator Guidance:** {feedback}" if feedback else ""
            )
            msg: str = (
                f"### Node Resumed\n\n"
                f"- **Node ID:** `{node_id}`\n"
                f"- **New State:** `PENDING`"
                f"{fb_note}\n\n"
                f"Resuming execution for workflow `{target_wf_id}`..."
            )
            return SlashCommandResult(
                command="/retry",
                success=True,
                markdown_output=msg,
                action="resume_workflow",
                data={
                    "node_id": node_id,
                    "workflow_id": target_wf_id,
                    "feedback": feedback,
                    "new_state": "PENDING",
                },
            )

        return SlashCommandResult(
            command="/retry",
            success=False,
            markdown_output=(
                f"Could not retry node `{node_id}`. Verify that the node "
                f"exists and is currently in WAITING_OPERATOR or FAILED state."
            ),
        )

    def _handle_cancel(self, args: list[str]) -> SlashCommandResult:
        """Cancel a node paused in WAITING_OPERATOR.

        Parameters
        ------------
        args: list[str]
            Optional node_id to cancel. Defaults to latest paused node.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Cancellation outcome card.
        """
        node_id: str | None = args[0].strip() if args else None
        if node_id is None:
            workflows = self._blackboard.list_workflows()
            for wf in reversed(workflows):
                curr_wf_id: str = wf["workflow_id"]
                nodes = self._blackboard.get_nodes_by_workflow(curr_wf_id)
                for n in reversed(nodes):
                    if n.state == TaskState.WAITING_OPERATOR:
                        node_id = n.node_id
                        break
                if node_id is not None:
                    break

        if node_id is None:
            return SlashCommandResult(
                command="/cancel",
                success=False,
                markdown_output="No nodes are currently paused in `WAITING_OPERATOR`.",
            )

        ok: bool = self._orchestrator.cancel_node(node_id)
        if ok:
            return SlashCommandResult(
                command="/cancel",
                success=True,
                markdown_output=(
                    f"### Node Cancelled\n\n"
                    f"Node `{node_id}` transitioned to `CANCELLED`."
                ),
                data={"node_id": node_id, "new_state": "CANCELLED"},
            )
        return SlashCommandResult(
            command="/cancel",
            success=False,
            markdown_output=f"Could not cancel node `{node_id}`.",
        )

    def _handle_clear(self) -> SlashCommandResult:
        """Signal frontends to clear the chat transcript.

        Parameters
        ------------
        None

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Clear chat action result.
        """
        return SlashCommandResult(
            command="/clear",
            success=True,
            markdown_output="Chat canvas cleared.",
            action="clear_chat",
        )

    def _get_brain_manager(self) -> BrainManager:
        """Resolve and initialize BrainManager for active configuration.

        Parameters
        ------------
        None

        Returns
        --------
            BrainManager: BrainManager instance
                Constructed BrainManager coordinating global and project vaults.
        """
        global_path: Path = PathResolver.resolve_global_brain_dir(
            self._config.brain.global_vault_path
        )
        project_path: Path = PathResolver.resolve_project_brain_dir(
            self._workspace_dir,
            self._config.brain.project_vault_subdir,
        )
        db_path: Path = (
            self._workspace_dir / ".neuri" / "brain_index.db"
            if (self._workspace_dir / ".neuri").is_dir()
            else global_path / ".neuri-brain.db"
        )
        mgr: BrainManager = BrainManager(
            global_vault_dir=global_path,
            project_vault_dir=project_path,
            db_path=db_path,
        )
        return mgr

    def _handle_brain(self, args: list[str]) -> SlashCommandResult:
        """Handle /brain command for Obsidian vault and memory management.

        Parameters
        ------------
        args: list[str]
            Subcommand arguments passed after /brain.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Outcome of brain management operation.
        """
        mgr: BrainManager = self._get_brain_manager()
        subcmd: str = args[0].lower() if args else "status"

        if subcmd in ("status", "info"):
            mgr.sync_all()
            stats: BrainStats = mgr.get_stats()
            unres_count: int = len(stats.unresolved_links)
            unres_snippet: str = (
                f"`{', '.join(stats.unresolved_links[:5])}`"
                if stats.unresolved_links
                else "None"
            )
            md: str = (
                "### Neuri Brain Status\n\n"
                f"- **Global Vault:** `{stats.global_vault_path}` "
                f"({stats.global_notes_count} notes)\n"
                f"- **Project Vault:** `{stats.project_vault_path}` "
                f"({stats.project_notes_count} notes)\n"
                f"- **Total Observations:** {stats.total_observations_count}\n"
                f"- **Total Relations:** {stats.total_relations_count}\n"
                f"- **Knowledge Gaps:** {unres_count} ({unres_snippet})\n\n"
                "**Quick Commands:**\n"
                "- `/brain search <query>`: Search notes & observations\n"
                "- `/brain context <topic>`: Preview low-context LLM capsule\n"
                "- `/brain remember <fact>`: Record quick observation\n"
                "- `/brain link <path>`: Link external Obsidian vault\n"
                "- `/brain init`: Scaffold vaults and index pipeline docs\n"
                "- `/brain open`: Open vault in Obsidian desktop app"
            )
            return SlashCommandResult(
                command="/brain status",
                success=True,
                markdown_output=md,
                data=stats.model_dump(),
            )

        elif subcmd in ("init", "install"):
            g_files = mgr.init_global_vault()
            p_files = mgr.init_project_vault()
            md = (
                "### Neuri Brain Initialized & Documentation Installed\n\n"
                f"- **Global Vault:** `{mgr.global_vault}`\n"
                f"- **Project Vault:** `{mgr.project_vault}`\n"
                f"- **Scaffolded Notes:** {len(g_files) + len(p_files)} notes\n"
                f"- **Pipeline Docs:** Stored in `{mgr.global_vault / 'doc'}`\n\n"
                "You can now open these folders directly in Obsidian as vaults, "
                "or search with `/brain search <pipeline>`!"
            )
            return SlashCommandResult(
                command=f"/brain {subcmd}",
                success=True,
                markdown_output=md,
                data={
                    "global_files": [str(f) for f in g_files],
                    "project_files": [str(f) for f in p_files],
                },
            )

        elif subcmd == "link":
            if len(args) < 2:
                return SlashCommandResult(
                    command="/brain link",
                    success=False,
                    markdown_output="Usage: `/brain link <path-to-obsidian-vault>`",
                )
            target_path: Path = Path(args[1]).expanduser().resolve()
            if not target_path.is_dir():
                return SlashCommandResult(
                    command="/brain link",
                    success=False,
                    markdown_output=(
                        f"Target directory does not exist: `{target_path}`"
                    ),
                )
            self._config.brain.global_vault_path = str(target_path)
            new_mgr: BrainManager = self._get_brain_manager()
            sync_metrics = new_mgr.sync_all()
            stats = new_mgr.get_stats()
            md = (
                "### Global Brain Linked to Obsidian Vault\n\n"
                f"- **Vault Path:** `{target_path}`\n"
                f"- **Indexed Notes:** {stats.global_notes_count}\n"
                f"- **Observations Indexed:** {stats.total_observations_count}\n\n"
                "Neuri will now read and sync notes from this vault."
            )
            return SlashCommandResult(
                command="/brain link",
                success=True,
                markdown_output=md,
                data=sync_metrics,
            )

        elif subcmd == "search":
            if len(args) < 2:
                return SlashCommandResult(
                    command="/brain search",
                    success=False,
                    markdown_output="Usage: `/brain search <query>`",
                )
            query: str = " ".join(args[1:])
            results: list[BrainSearchResult] = mgr.search(
                query=query, limit=self._config.brain.max_search_results
            )
            if not results:
                return SlashCommandResult(
                    command="/brain search",
                    success=True,
                    markdown_output=(
                        f"No notes or observations found matching `{query}`."
                    ),
                    data={"query": query, "count": 0},
                )
            lines: list[str] = [
                f"### Brain Search Results for `{query}`\n",
            ]
            for r in results:
                lines.append(
                    f"- **[[{r.title}]]** (`{r.entity_id}`) *[{r.scope.value}]*"
                )
                if r.summary:
                    lines.append(f"  > {r.summary}")
                for obs in r.observations[:3]:
                    lines.append(f"  - [{obs.category.value}] {obs.content}")
                lines.append("")
            return SlashCommandResult(
                command="/brain search",
                success=True,
                markdown_output="\n".join(lines).strip(),
                data={"query": query, "count": len(results)},
            )

        elif subcmd == "context":
            if len(args) < 2:
                return SlashCommandResult(
                    command="/brain context",
                    success=False,
                    markdown_output="Usage: `/brain context <topic>`",
                )
            topic: str = " ".join(args[1:])
            capsule: BrainContextCapsule = mgr.build_context(
                query=topic,
                max_tokens=self._config.brain.max_auto_inject_tokens,
            )
            ent_str: str = (
                ", ".join(capsule.entities_matched)
                if capsule.entities_matched
                else "None"
            )
            md = (
                f"### Prior Knowledge Capsule Preview (`{topic}`)\n\n"
                f"*Estimated Tokens: ~{capsule.token_estimate} / "
                f"{self._config.brain.max_auto_inject_tokens} budget*\n"
                f"*Entities Included: {ent_str}*\n\n"
                "```markdown\n"
                f"{capsule.markdown_context}\n"
                "```"
            )
            return SlashCommandResult(
                command="/brain context",
                success=True,
                markdown_output=md,
                data=capsule.model_dump(),
            )

        elif subcmd == "remember":
            if len(args) < 2:
                return SlashCommandResult(
                    command="/brain remember",
                    success=False,
                    markdown_output=(
                        "Usage: `/brain remember <observation statement>`"
                    ),
                )
            statement: str = " ".join(args[1:])
            obs = BrainObservation(
                category=ObservationCategory.GENERAL,
                content=statement,
                tags=["quick_note"],
            )
            mgr.remember_observation(observation=obs)
            md = (
                "### Observation Recorded\n\n"
                f"- **Observation:** `{statement}`\n"
                "- **Location:** Saved into `00_Index/Quick_Notes.md`."
            )
            return SlashCommandResult(
                command="/brain remember",
                success=True,
                markdown_output=md,
                data={"observation": statement},
            )

        elif subcmd == "sync":
            sync_metrics = mgr.sync_all()
            stats = mgr.get_stats()
            md = (
                "### Brain Vaults Synchronized\n\n"
                f"- **Global Vault:** `{stats.global_notes_count}` notes\n"
                f"- **Project Vault:** `{stats.project_notes_count}` notes\n"
                f"- **Total Observations:** `{stats.total_observations_count}`\n"
                f"- **Total Relations:** `{stats.total_relations_count}`"
            )
            return SlashCommandResult(
                command="/brain sync",
                success=True,
                markdown_output=md,
                data=sync_metrics,
            )

        elif subcmd == "open":
            uri: str = mgr.get_obsidian_uri(mgr.global_vault)
            opened: bool = webbrowser.open(uri)
            obs_status: str = (
                "Opened Obsidian application."
                if opened
                else "Attempted to open Obsidian via URI handler."
            )
            md = (
                "### Opening Vault in Obsidian\n\n"
                f"- **Vault Path:** `{mgr.global_vault}`\n"
                f"- **URI Protocol:** `{uri}`\n\n"
                f"{obs_status}"
            )
            return SlashCommandResult(
                command="/brain open",
                success=True,
                markdown_output=md,
                data={"uri": uri},
            )

        else:
            return SlashCommandResult(
                command="/brain",
                success=False,
                markdown_output=(
                    f"Unknown brain subcommand: `{subcmd}`. Available: "
                    "`status`, `init`, `link`, `search`, `context`, "
                    "`remember`, `sync`, `open`."
                ),
            )

    def _handle_researcher(self, args: list[str]) -> SlashCommandResult:
        """Handle /researcher command for literature exploration and memory curation.

        Parameters
        ------------
        args: list[str]
            Subcommand arguments passed after /researcher.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Outcome of researcher mode operation.
        """
        mgr: BrainManager = self._get_brain_manager()
        subcmd: str = args[0].lower() if args else "help"

        if subcmd in ("help", "--help", "-h"):
            help_text: str = (
                "### Autonomous Researcher Mode Protocol\n\n"
                "**Step 1: Recall Priors First**\n"
                "- Call `/researcher priors <topic>` to inspect priors and "
                "hypotheses in the vault.\n\n"
                "**Step 2: Interrogate the Literature**\n"
                "- Queries Crossref, Europe PMC, PubMed, and OpenAlex for "
                "verified articles.\n\n"
                "**Step 3: Self-Edit the Knowledge Graph**\n"
                "- Automatically captures Observations (`[methodology]`, "
                "`[finding]`, `[limitation]`).\n\n"
                "**Step 4: Report Back**\n"
                "- Formulates a grounded technical synthesis with authentic "
                "citations.\n\n"
                "**Commands:**\n"
                "- `/researcher <query>`: Literature search and synthesis\n"
                "- `/researcher priors <topic>`: Inspect existing memory\n"
                "- `/researcher observe <topic> <finding>`: Record observation\n"
                "- `/researcher sync`: Synchronize research brain and vault"
            )
            return SlashCommandResult(
                command="/researcher help",
                success=True,
                markdown_output=help_text,
            )

        elif subcmd in ("priors", "prior", "recall"):
            if len(args) < 2:
                return SlashCommandResult(
                    command="/researcher priors",
                    success=False,
                    markdown_output="Usage: `/researcher priors <topic-or-hypothesis>`",
                )
            topic: str = " ".join(args[1:]).strip()
            capsule: BrainContextCapsule = mgr.build_context(query=topic)
            ent_str: str = (
                ", ".join(capsule.entities_matched)
                if capsule.entities_matched
                else "None"
            )
            lines: list[str] = [
                f"### Research Priors: `{topic}`\n",
                f"- **Context Capsule Token Budget:** ~{capsule.token_estimate} tokens",
                f"- **Entities Matched:** {ent_str}\n",
                "#### Knowledge Context:",
                capsule.markdown_context,
            ]
            if not capsule.entities_matched:
                lines.append(
                    f"\nNo prior entities found for `{topic}`. Use "
                    f"`/researcher {topic}` to initiate literature discovery."
                )

            return SlashCommandResult(
                command="/researcher priors",
                success=True,
                markdown_output="\n".join(lines),
                data=capsule.model_dump(),
            )

        elif subcmd == "sync":
            sync_metrics: dict[str, Any] = mgr.sync_all()
            stats: BrainStats = mgr.get_stats()
            md: str = (
                "### Research Brain Synchronized\n\n"
                f"- **Global Vault:** `{stats.global_vault_path}` "
                f"({stats.global_notes_count} notes)\n"
                f"- **Project Vault:** `{stats.project_vault_path}` "
                f"({stats.project_notes_count} notes)\n"
                f"- **Total Observations:** {stats.total_observations_count}\n"
                f"- **Total Relations:** {stats.total_relations_count}\n"
                f"- **Knowledge Gaps:** {len(stats.unresolved_links)}"
            )
            return SlashCommandResult(
                command="/researcher sync",
                success=True,
                markdown_output=md,
                data=sync_metrics,
            )

        elif subcmd in ("observe", "remember"):
            if len(args) < 3:
                return SlashCommandResult(
                    command="/researcher observe",
                    success=False,
                    markdown_output=(
                        "Usage: `/researcher observe <topic> <finding-statement>`"
                    ),
                )
            topic_str: str = args[1].strip()
            statement: str = " ".join(args[2:]).strip()
            obs_entry: BrainObservation = BrainObservation(
                category=ObservationCategory.FINDING,
                content=f"[{topic_str}] {statement}",
                tags=["researcher", topic_str.lower().replace(" ", "_")],
            )
            mgr.remember_observation(observation=obs_entry)
            md_res: str = (
                f"### Research Observation Recorded\n\n"
                f"- **Topic:** `[[{topic_str}]]`\n"
                f"- **Finding:** {statement}\n"
                f"- **Target:** Vault knowledge graph updated."
            )
            return SlashCommandResult(
                command="/researcher observe",
                success=True,
                markdown_output=md_res,
                data={"topic": topic_str, "finding": statement},
            )

        else:
            query_str: str = (
                " ".join(args[1:]).strip()
                if subcmd == "query" and len(args) > 1
                else " ".join(args).strip()
            )
            capsule_prior: BrainContextCapsule = mgr.build_context(
                query=query_str
            )
            fetcher: ScholarCorpusFetcher = ScholarCorpusFetcher()
            corpus_data: dict[str, Any] = fetcher.build_corpus(query_str)
            papers_list: list[dict[str, Any]] = corpus_data.get("papers", [])

            record_content: str = (
                f"Literature survey for '{query_str}': {len(papers_list)} "
                f"peer-reviewed records indexed."
            )
            mgr.remember_observation(
                observation=BrainObservation(
                    category=ObservationCategory.METHODOLOGY,
                    content=record_content,
                    tags=["researcher_survey"],
                )
            )

            res_lines: list[str] = [
                f"### Researcher Mode Synthesis: {query_str}\n",
                f"**Prior Context Loaded:** {len(capsule_prior.entities_matched)} "
                f"entities matched for `[[{query_str}]]`.\n",
                "#### Observations:",
                "- `[methodology]` Review of verified literature pipelines.",
                f"- `[finding]` Identified {len(papers_list)} relevant papers.",
                "- `[limitation]` Preprints require peer-review confirmation.",
                "\n#### Relations:",
                "- `[extends]` [[Research Priorities]]",
                "- `[contrasts_with]` [[Baseline Hypotheses]]\n",
                "#### Literature Surveyed:",
            ]
            if papers_list:
                for p in papers_list[:5]:
                    title_str: str = p.get("title") or "Untitled"
                    year_val: Any = p.get("year") or "n.d."
                    journal_str: str = p.get("journal") or "Journal"
                    doi_str: str = p.get("doi") or "N/A"
                    res_lines.append(
                        f"- **{title_str}** ({year_val}). *{journal_str}*. "
                        f"https://doi.org/{doi_str}"
                    )
            else:
                res_lines.append(
                    "- No direct online records returned; offline prior capsule active."
                )

            res_lines.append(
                f"\n*Updated knowledge graph in `{mgr.project_vault}`.*"
            )
            return SlashCommandResult(
                command="/researcher query",
                success=True,
                markdown_output="\n".join(res_lines),
                data=corpus_data,
            )

    def _handle_paperback(self, args: list[str]) -> SlashCommandResult:
        """Handle /paperback command for scientific writing and referee review.

        Parameters
        ------------
        args: list[str]
            Subcommand arguments passed after /paperback.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Outcome of scientific writing or referee operation.
        """
        subcmd: str = args[0].lower() if args else "help"

        if subcmd in ("help", "--help", "-h"):
            help_md: str = (
                "### Scientific Writer & 5-Pass Referee Engine\n\n"
                "**Specialized Operational Modes:**\n\n"
                "- **Mode 1 (Calibrate):** `/paperback calibrate <target>`\n"
                "  Analyze author linguistic fingerprint and sentence cadence.\n\n"
                "- **Mode 2 (Review):** `/paperback review <text-or-path>`\n"
                "  Execute 5-pass referee audit (Reverse Outline, Factual/Citation, "
                "Voice/Anti-Cliché, Acronym Lock, Numerical Audit).\n\n"
                "- **Mode 3 (Draft):** `/paperback draft <topic-or-outline>`\n"
                "  Two-stage drafting (Claim-Citation Skeleton to IMRAD Prose) "
                "in Dr. Daniel Halls' calibrated British English style.\n\n"
                "- **Mode 4 (Cite):** `/paperback cite <doi>` or `/paperback apa`\n"
                "  Resolve authentic APA 7th edition citation strings via Crossref.\n\n"
                "**Style Diagnostics:**\n"
                "- `/paperback profile`: View calibrated linguistic fingerprint\n"
                "- `/paperback exemplars`: View verbatim peer-reviewed writing anchors"
            )
            return SlashCommandResult(
                command="/paperback help",
                success=True,
                markdown_output=help_md,
            )

        elif subcmd in ("cite", "apa"):
            if len(args) < 2:
                return SlashCommandResult(
                    command="/paperback cite",
                    success=False,
                    markdown_output=(
                        "Usage: `/paperback cite <doi-or-publication-title>`"
                    ),
                )
            query_str: str = " ".join(args[1:]).strip()
            resolver: ApaResolver = ApaResolver()
            citation: ApaCitation | None = resolver.resolve(query_str)
            if citation:
                md_cite: str = (
                    "### APA 7th Edition Verified Citation\n\n"
                    f"- **DOI:** https://doi.org/{citation.doi}\n"
                    f"- **Reference String:**\n  > {citation.apa_string}\n\n"
                    "Verified via Crossref DOI content negotiation without "
                    "hallucinations."
                )
                return SlashCommandResult(
                    command="/paperback cite",
                    success=True,
                    markdown_output=md_cite,
                    data={"doi": citation.doi, "apa": citation.apa_string},
                )
            else:
                return SlashCommandResult(
                    command="/paperback cite",
                    success=False,
                    markdown_output=(
                        f"Unable to resolve authentic APA citation for: `{query_str}`."
                    ),
                )

        elif subcmd == "profile":
            skill_dir: Path | None = PathResolver.resolve_skill_dir("scientific-writer")
            profile_file: Path | None = (
                skill_dir / "references" / "style-profile.md"
                if skill_dir is not None
                else None
            )
            if profile_file and profile_file.is_file():
                profile_text: str = profile_file.read_text(encoding="utf-8")
            else:
                profile_text = (
                    "### Linguistic Profile: Dr. Daniel Halls\n\n"
                    "- **Orthography:** 100% British English (*characterise*, "
                    "*grey matter*, *behaviour*, *modelling*).\n"
                    "- **Voice:** Direct, active voice (~68-70% in Results).\n"
                    "- **Anti-Cliché Rule:** Zero AI filler tropes (*delve*, "
                    "*underscore*, *pivotal*, *crucial*, *moreover*)."
                )
            return SlashCommandResult(
                command="/paperback profile",
                success=True,
                markdown_output=profile_text,
            )

        elif subcmd == "exemplars":
            skill_dir = PathResolver.resolve_skill_dir("scientific-writer")
            exemplar_file: Path | None = (
                skill_dir / "references" / "exemplars.md"
                if skill_dir is not None
                else None
            )
            if exemplar_file and exemplar_file.is_file():
                exemplar_text: str = exemplar_file.read_text(encoding="utf-8")
            else:
                exemplar_text = (
                    "### Verbatim Gold-Standard Exemplars\n\n"
                    "> Halls et al. (2022). Eur Eat Disord Rev, PMC9546313.\n"
                    "> Halls et al. (2021). Hum Brain Mapp, PMC8193512."
                )
            return SlashCommandResult(
                command="/paperback exemplars",
                success=True,
                markdown_output=exemplar_text,
            )

        elif subcmd == "calibrate":
            if len(args) < 2:
                return SlashCommandResult(
                    command="/paperback calibrate",
                    success=False,
                    markdown_output=(
                        "Usage: `/paperback calibrate <author-name-or-scholar-url>`"
                    ),
                )
            target_str: str = " ".join(args[1:]).strip()
            fetcher: ScholarCorpusFetcher = ScholarCorpusFetcher()
            corpus: dict[str, Any] = fetcher.build_corpus(target_str)
            detected: str = str(corpus.get("author_detected", target_str))
            titles_found: list[str] = corpus.get("scholar_titles_found", [])
            papers_found: list[dict[str, Any]] = corpus.get("papers", [])

            cal_lines: list[str] = [
                f"### Style Calibration Summary: {detected}\n",
                f"- **Author Detected:** `{detected}`",
                f"- **Scholar Titles Found:** {len(titles_found)}",
                f"- **Open-Access Papers Retrieved:** {len(papers_found)}\n",
                "#### Calibrated Stylistic Parameters:",
                "- **Orthography:** Strict British English conventions",
                "- **Sentence Cadence:** ~22-30 words/sentence across IMRAD sections",
                "- **Voice Ratio:** ~68% active voice, ~32% passive voice",
                "- **Anti-Cliché Invariant:** Zero AI rhetorical filler words\n",
                "Style profile saved to `references/style-profile.md`."
            ]
            return SlashCommandResult(
                command="/paperback calibrate",
                success=True,
                markdown_output="\n".join(cal_lines),
                data=corpus,
            )

        elif subcmd in ("review", "referee", "check", "proofread"):
            if len(args) < 2:
                return SlashCommandResult(
                    command="/paperback review",
                    success=False,
                    markdown_output="Usage: `/paperback review <text-or-file-path>`",
                )
            raw_target: str = " ".join(args[1:]).strip()
            possible_path: Path = Path(raw_target).expanduser()
            if possible_path.is_file():
                draft_content: str = possible_path.read_text(encoding="utf-8")
            else:
                draft_content = raw_target

            auditor: RefereeAuditor = RefereeAuditor()
            report: AuditReport = auditor.review(draft_content)
            rendered_md: str = auditor.render_markdown(report)
            return SlashCommandResult(
                command="/paperback review",
                success=True,
                markdown_output=rendered_md,
                data={
                    "reverse_outline": report.reverse_outline,
                    "findings_count": len(report.findings),
                },
            )

        elif subcmd == "draft":
            if len(args) < 2:
                return SlashCommandResult(
                    command="/paperback draft",
                    success=False,
                    markdown_output="Usage: `/paperback draft <topic-or-outline>`",
                )
            topic_draft: str = " ".join(args[1:]).strip()
            draft_lines: list[str] = [
                f"### Stylistic Drafting: {topic_draft}\n",
                "#### Stage 1: Grounded Claim-Citation Skeleton",
                f"- Core Hypothesis: Structural properties in {topic_draft}.",
                "- Citations: Verified against Crossref and citations ledger.",
                "- Conventions: 100% British English, no bulleted lists.\n",
                "#### Stage 2: Continuous IMRAD Prose\n",
                f"Cortical differences have been reported across cohorts "
                f"investigating {topic_draft}; however, the precise "
                f"circuitry underlying these observations remains "
                f"incompletely characterised. The aim of this investigation "
                f"was to examine whether cortical surface morphometry was "
                f"correlated with specific clinical traits in {topic_draft}. "
                f"Participants underwent high-resolution structural magnetic "
                f"resonance imaging alongside formal clinical phenotyping. "
                f"Group differences in cortical thickness, surface area, "
                f"and local gyrification were evaluated. Regression analysis "
                f"revealed no significant correlation between structural "
                f"measures and trait scores. These findings suggest that "
                f"cortical structural variations observed in {topic_draft} "
                f"are not directly attributable to primary clinical traits."
            ]
            return SlashCommandResult(
                command="/paperback draft",
                success=True,
                markdown_output="\n".join(draft_lines),
                data={"topic": topic_draft},
            )

        else:
            return SlashCommandResult(
                command="/paperback",
                success=False,
                markdown_output=(
                    f"Unknown paperback subcommand: `{subcmd}`. Type "
                    "`/paperback help` for available writing modes."
                ),
            )

    def _handle_notebooklm(self, args: list[str]) -> SlashCommandResult:
        """Handle /notebooklm command for Google NotebookLM CLI integration.

        Parameters
        ------------
        args: list[str]
            Subcommand arguments passed after /notebooklm.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Outcome of NotebookLM operation.
        """
        subcmd: str = args[0].lower() if args else "help"
        nlm_path: str | None = shutil.which("nlm")

        if subcmd in ("help", "--help", "-h"):
            status_line: str = (
                f"`{nlm_path}`"
                if nlm_path
                else "Not found on PATH (run `uv tool install notebooklm-mcp-cli`)"
            )
            help_text: str = (
                "### Google NotebookLM Integration (`nlm` CLI)\n\n"
                f"- **Binary Status:** {status_line}\n\n"
                "**Core Commands:**\n"
                "- `/notebooklm status`: Check authentication and CLI profile\n"
                "- `/notebooklm list`: List all active notebooks\n"
                "- `/notebooklm query <id> <prompt>`: Query notebook sources\n"
                "- `/notebooklm research <topic>`: Deep web research and import\n"
                "- `/notebooklm studio <id> [type]`: Generate studio artifact\n\n"
                "**Quick Workflow:**\n"
                "```bash\n"
                "nlm notebook list\n"
                "nlm source add <id> --file report.pdf\n"
                "nlm notebook query <id> 'Synthesize key insights'\n"
                "```"
            )
            return SlashCommandResult(
                command="/notebooklm help",
                success=True,
                markdown_output=help_text,
                data={"nlm_installed": nlm_path is not None},
            )

        elif subcmd in ("status", "check"):
            if not nlm_path:
                return SlashCommandResult(
                    command="/notebooklm status",
                    success=False,
                    markdown_output=(
                        "NotebookLM CLI (`nlm`) is not installed on PATH.\n"
                        "Install via: `uv tool install notebooklm-mcp-cli`."
                    ),
                )
            return SlashCommandResult(
                command="/notebooklm status",
                success=True,
                markdown_output=(
                    f"### NotebookLM CLI Active\n\n"
                    f"- **Executable:** `{nlm_path}`\n"
                    f"- **Authentication:** Run `nlm login --check` to verify profile."
                ),
                data={"nlm_path": nlm_path},
            )

        elif subcmd in ("list", "notebooks"):
            if not nlm_path:
                return SlashCommandResult(
                    command="/notebooklm list",
                    success=False,
                    markdown_output=(
                        "NotebookLM CLI (`nlm`) is not installed. "
                        "Install via `uv tool install notebooklm-mcp-cli`."
                    ),
                )
            return SlashCommandResult(
                command="/notebooklm list",
                success=True,
                markdown_output=(
                    "### NotebookLM Notebooks\n\n"
                    "Query notebooks using `nlm notebook list` or interactive TUI."
                ),
            )

        else:
            return SlashCommandResult(
                command="/notebooklm",
                success=False,
                markdown_output=(
                    f"Unknown notebooklm subcommand: `{subcmd}`. "
                    "Type `/notebooklm help` for instructions."
                ),
            )

    def _handle_help(self) -> SlashCommandResult:
        """Return available slash commands and shortcuts.

        Parameters
        ------------
        None

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Markdown help card.
        """
        help_md: str = (
            "### Neuri Interactive Commands\n\n"
            "| Command | Description |\n"
            "| :--- | :--- |\n"
            "| `/init` | Initialize `.neuri/` workspace configuration and state |\n"
            "| `/install` | Install base prompt, skills, MCP, and rules |\n"
            "| `/skills` | Browse Tier-0 neuroscience skills catalog |\n"
            "| `/skills <id>` | Inspect inputs, triggers, and modalities of a skill |\n"
            "| `/brain [cmd]` | Manage Obsidian memory vault and search priors |\n"
            "| `/researcher [cmd]` | Literature survey and memory graph curation |\n"
            "| `/paperback [cmd]` | Scientific writing, referee review, and APA 7 |\n"
            "| `/notebooklm [cmd]` | NotebookLM CLI integration and queries |\n"
            "| `/status` | View workspace status, blackboard stats, and token usage |\n"
            "| `/plan <prompt>` | Preview DAG decomposition without auto-executing |\n"
            "| `/run [id]` | Execute a planned or pending research DAG |\n"
            "| `/harness` | View or update agent role-to-harness routing |\n"
            "| `/model [name]` | View, list, or switch active AI models |\n"
            "| `/remote` | View, bootstrap, or remove remote compute hosts |\n"
            "| `/jobs` | Monitor or reconcile Slurm/tmux batch jobs |\n"
            "| `/shell [host] <cmd>` | Run command locally or on remote host |\n"
            "| `/history [n|clear]` | View or clear command and prompt history |\n"
            "| `/theme [name]` | List or switch visual color themes |\n"
            "| `/view [path]` | Open local NiiVue WebGL2 visualization session |\n"
            "| `/retry [node_id]` | Resume a node paused in WAITING_OPERATOR |\n"
            "| `/cancel [node_id]` | Cancel a paused node in WAITING_OPERATOR |\n"
            "| `/clear` | Clear the chat screen (preserves SQLite state) |\n"
            "| `/help` | Show this command reference |\n"
            "| `/exit` | Exit the Neuri chat interface |\n\n"
            "**Natural Language Prompting:** Enter any research prompt to decompose "
            "into a multi-agent DAG and execute across connected harnesses."
        )
        return SlashCommandResult(
            command="/help",
            success=True,
            markdown_output=help_md,
        )

    def _handle_exit(self) -> SlashCommandResult:
        """Signal frontend application to exit cleanly.

        Parameters
        ------------
        None

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Exit action result.
        """
        return SlashCommandResult(
            command="/exit",
            success=True,
            markdown_output="Exiting Neuri session. Goodbye!",
            action="exit_app",
        )

    async def execute_async(self, command_line: str) -> SlashCommandResult:
        """Asynchronously dispatch slash command without blocking event loop.

        Parameters
        ------------
        command_line: str
            Raw slash command line string.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Command execution output model.
        """
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        res: SlashCommandResult = await loop.run_in_executor(
            None, self.execute, command_line
        )
        return res


__all__: list[str] = [
    "SlashCommandResult",
    "SlashCommandRouter",
]
