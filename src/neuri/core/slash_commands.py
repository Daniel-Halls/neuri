"""Interactive Slash Command Router and Execution Subsystem for Neuri.

Provides structured command dispatch (/init, /skills, /status, /harness,
/retry, /cancel, /clear, /help, /exit) designed for both the terminal chat
interface and future Desktop/Web GUIs.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Coroutine

from pydantic import BaseModel, ConfigDict, Field
import yaml

from neuri.core.blackboard import Blackboard
from neuri.core.config import NeuriConfig, init_project_workspace, load_config
from neuri.core.installer import NeuriInstaller
from neuri.core.orchestrator import DAGOrchestrator
from neuri.core.paths import PathResolver
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
        "/remote",
        "/machines",
        "/cluster",
        "/jobs",
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
        elif cmd == "/remote":
            return self._handle_remote(args)
        elif cmd in ("/machines", "/cluster"):
            return self._handle_machines()
        elif cmd == "/jobs":
            return self._handle_jobs(args)
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

        harness_default: str = "antigravity"
        if isinstance(self._config.harness_routing, dict):
            pe_cfg = self._config.harness_routing.get("pipeline_engineer")
            if pe_cfg is not None:
                harness_default = getattr(pe_cfg, "harness", str(pe_cfg))
        elif hasattr(self._config.harness_routing, "default_harness"):
            harness_default = getattr(
                self._config.harness_routing, "default_harness"
            )

        init_status: str = "Yes" if is_init else "No (type /init to initialize)"
        cost_limit: str = f"${self._config.budgets.max_workflow_cost_usd:.2f}"
        msg: str = (
            f"### Neuri System Status\n\n"
            f"- **Workspace Directory:** `{self._workspace_dir}`\n"
            f"- **Initialized (.neuri):** `{init_status}`\n"
            f"- **Default Remote Host:** `{remote_host}`\n"
            f"- **Default Harness:** `{harness_default}`\n"
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
                "default_harness": harness_default,
            },
        )

    def _handle_harness(self, args: list[str]) -> SlashCommandResult:
        """Display or update role-to-harness routing configuration.

        Parameters
        ------------
        args: list[str]
            Optional [role, harness_id] pair to update.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Routing table or confirmation card.
        """
        routing_map: dict[str, str] = {}
        harness_default: str = "antigravity"

        if isinstance(self._config.harness_routing, dict):
            for role_name, r_cfg in self._config.harness_routing.items():
                target_h = getattr(r_cfg, "harness", str(r_cfg))
                routing_map[role_name] = target_h
            if "pipeline_engineer" in routing_map:
                harness_default = routing_map["pipeline_engineer"]
        elif hasattr(self._config.harness_routing, "role_map"):
            routing_map = dict(getattr(self._config.harness_routing, "role_map"))
            harness_default = getattr(
                self._config.harness_routing, "default_harness", "antigravity"
            )

        if len(args) >= 2:
            role: str = args[0].strip()
            h_id: str = args[1].strip()
            if isinstance(self._config.harness_routing, dict):
                from neuri.core.config import HarnessRoutingConfig

                self._config.harness_routing[role] = HarnessRoutingConfig(
                    harness=h_id,
                    execution_mode="interactive_pty",
                )
                routing_map[role] = h_id
            elif hasattr(self._config.harness_routing, "role_map"):
                self._config.harness_routing.role_map[role] = h_id
                routing_map[role] = h_id

            msg: str = (
                f"Updated harness routing: Sub-agent role `{role}` is now "
                f"dispatched to harness `{h_id}`."
            )
            return SlashCommandResult(
                command="/harness",
                success=True,
                markdown_output=msg,
                data={"role": role, "harness_id": h_id},
            )

        lines: list[str] = [
            "### Harness Routing Map\n",
            f"**Default Harness:** `{harness_default}`\n",
            "| Agent Role | Target Harness |",
            "| :--- | :--- |",
        ]
        for r, h in routing_map.items():
            lines.append(f"| `{r}` | `{h}` |")

        return SlashCommandResult(
            command="/harness",
            success=True,
            markdown_output="\n".join(lines),
            data=dict(routing_map),
        )

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

        return SlashCommandResult(
            command="/remote",
            success=False,
            markdown_output=(
                f"Unknown remote subcommand `{subcmd}`. "
                "Use `/remote list` or `/remote bootstrap <host>`."
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
            status_badge: str = "🟢 Online" if online else "🔴 Offline"
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

    def _handle_view(self, args: list[str]) -> SlashCommandResult:
        """Launch or inspect local NiiVue WebGL2 visualization bridge.

        Parameters
        ------------
        args: list[str]
            Optional artifact URI or file path to view.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Visualization link and instructions card.
        """
        viewer_url: str = "http://localhost:8421"
        target_uri: str = args[0].strip() if args else ""
        if target_uri:
            msg: str = (
                f"### NiiVue Visualization Bridge\n\n"
                f"- **Viewer URL:** [{viewer_url}]({viewer_url})\n"
                f"- **Target Artifact:** `{target_uri}`\n\n"
                f"Open the link above in your browser to inspect this volume."
            )
            return SlashCommandResult(
                command="/view",
                success=True,
                markdown_output=msg,
                data={"viewer_url": viewer_url, "target_uri": target_uri},
            )
        msg_default: str = (
            f"### NiiVue Visualization Bridge\n\n"
            f"- **Viewer URL:** [{viewer_url}]({viewer_url})\n\n"
            f"Active WebGL2 neuroimaging session listening on port 8421."
        )
        return SlashCommandResult(
            command="/view",
            success=True,
            markdown_output=msg_default,
            data={"viewer_url": viewer_url},
        )

    def _handle_retry(self, args: list[str]) -> SlashCommandResult:
        """Retry a node paused in WAITING_OPERATOR.

        Parameters
        ------------
        args: list[str]
            Arguments containing the node_id to retry.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Retry outcome card.
        """
        if not args:
            return SlashCommandResult(
                command="/retry",
                success=False,
                markdown_output="Usage: `/retry <node_id>`",
            )

        node_id: str = args[0].strip()
        ok: bool = self._orchestrator.retry_node(node_id)
        if ok:
            msg: str = (
                f"Node `{node_id}` reset to `PENDING` state and queued "
                f"for execution."
            )
            return SlashCommandResult(
                command="/retry",
                success=True,
                markdown_output=msg,
                data={"node_id": node_id, "new_state": "PENDING"},
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
            Arguments containing the node_id to cancel.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Cancellation outcome card.
        """
        if not args:
            return SlashCommandResult(
                command="/cancel",
                success=False,
                markdown_output="Usage: `/cancel <node_id>`",
            )

        node_id: str = args[0].strip()
        ok: bool = self._orchestrator.cancel_node(node_id)
        if ok:
            return SlashCommandResult(
                command="/cancel",
                success=True,
                markdown_output=f"Node `{node_id}` transitioned to `CANCELLED`.",
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
            "| `/status` | View workspace status, blackboard stats, and token usage |\n"
            "| `/harness` | View or update agent role-to-harness routing |\n"
            "| `/remote` | View or bootstrap remote compute hosts |\n"
            "| `/jobs` | Monitor or reconcile Slurm/tmux batch jobs |\n"
            "| `/view` | Open local NiiVue WebGL2 visualization session |\n"
            "| `/retry <node_id>` | Resume a node paused in WAITING_OPERATOR |\n"
            "| `/cancel <node_id>` | Cancel a paused node in WAITING_OPERATOR |\n"
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


__all__: list[str] = [
    "SlashCommandResult",
    "SlashCommandRouter",
]
