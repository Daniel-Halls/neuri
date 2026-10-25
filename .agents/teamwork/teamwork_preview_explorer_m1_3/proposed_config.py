"""Two-tier configuration loader and workspace initializer for Neuri.

Provides hierarchical loading of global operator configurations (~/.neuri/config.toml)
merged with project-local configurations (.neuri/neuri.toml), along with
project workspace scaffolding and Pydantic configuration schemas.
"""

from collections.abc import Mapping
from pathlib import Path
import sqlite3
import tomllib
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator
import tomli_w


class ConfigError(Exception):
    """Exception raised for configuration syntax, loading, or validation errors."""

    def __init__(self, message: str) -> None:
        """Initialize the configuration error.

        Parameters
        ------------
        message: str
            Explanatory error message detailing the failure cause.

        Returns
        --------
            None: NoneType object
                Initializes exception state.
        """
        super().__init__(message)


class WorkspaceConfig(BaseModel):
    """Project-level metadata and remote execution root configuration."""

    name: str = Field(
        default="default-neuro-study",
        description="Name of the neuroscience project or experiment",
    )
    default_remote_host: str = Field(
        default="localhost",
        description="Default SSH/Tailscale remote host alias for compute",
    )
    remote_bids_root: str | None = Field(
        default=None,
        description="Remote root URI for BIDS dataset (e.g. host:///path/to/bids)",
    )


# Backward-compatible alias for ProjectConfig
ProjectConfig = WorkspaceConfig


class HarnessRoutingConfig(BaseModel):
    """Configuration mapping an agent role to a harness backend and execution mode."""

    harness: str = Field(
        default="agy",
        description="Harness identifier (e.g. agy, codex, opencode, openclaw, ollama)",
    )
    mode: str = Field(
        default="headless_json",
        description="Execution mode: headless_json or interactive_pty",
    )

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        """Validate that execution mode is one of the supported contracts.

        Parameters
        ------------
        value: str
            Execution mode string to validate.

        Returns
        --------
            str: string object
                Validated mode string.
        """
        allowed = {"headless_json", "interactive_pty"}
        if value not in allowed:
            raise ValueError(
                f"Invalid execution mode '{value}'. Must be one of {allowed}."
            )
        return value


# Backward-compatible alias for HarnessRouteConfig
HarnessRouteConfig = HarnessRoutingConfig


class BudgetConfig(BaseModel):
    """Resource budgets and circuit breaker thresholds for DAG execution."""

    max_node_tokens: int = Field(
        default=64000,
        description="Maximum token consumption allowed per DAG node",
    )
    max_workflow_cost_usd: float = Field(
        default=10.00,
        description="Maximum estimated cost in USD for the entire workflow",
    )
    max_node_retries: int = Field(
        default=2,
        description="Maximum auto-retries for a failed task node",
    )
    async_job_threshold_seconds: int = Field(
        default=20,
        description="Threshold duration in seconds triggering detach-and-reconcile",
    )
    consecutive_failure_threshold: int = Field(
        default=3,
        description="Number of consecutive identical tool failures to trip breaker",
    )

    @field_validator("max_node_tokens")
    @classmethod
    def validate_max_tokens(cls, value: int) -> int:
        """Validate that maximum node token limit is strictly positive.

        Parameters
        ------------
        value: int
            Token budget value to validate.

        Returns
        --------
            int: integer object
                Validated token limit.
        """
        if value <= 0:
            raise ValueError("max_node_tokens must be greater than zero.")
        return value

    @field_validator("max_workflow_cost_usd")
    @classmethod
    def validate_max_cost(cls, value: float) -> float:
        """Validate that maximum workflow cost is non-negative.

        Parameters
        ------------
        value: float
            Cost budget value in USD.

        Returns
        --------
            float: float object
                Validated cost budget.
        """
        if value < 0.0:
            raise ValueError("max_workflow_cost_usd must be non-negative.")
        return value


# Backward-compatible alias for BudgetsConfig
BudgetsConfig = BudgetConfig


class NeuriConfig(BaseModel):
    """Complete two-tier Neuri configuration model."""

    project: WorkspaceConfig = Field(
        default_factory=WorkspaceConfig,
        description="Project workspace configuration",
    )
    harness_routing: dict[str, HarnessRoutingConfig] = Field(
        default_factory=dict,
        description="Mapping of agent roles to harness routing configs",
    )
    budgets: BudgetConfig = Field(
        default_factory=BudgetConfig,
        description="Resource budgets and circuit breaker thresholds",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_input_data(cls, data: Any) -> Any:
        """Normalize configuration keys from various TOML table conventions.

        Parameters
        ------------
        data: Any
            Raw data dictionary before model validation.

        Returns
        --------
            Any: Any object
                Normalized data dictionary with standard keys.
        """
        if not isinstance(data, dict):
            return data

        normalized: dict[str, Any] = dict(data)

        # Handle [workspace] alias for [project]
        if "workspace" in normalized and "project" not in normalized:
            normalized["project"] = normalized["workspace"]

        # Handle [harnesses.routing] nested table or [harnesses_routing]
        if "harnesses" in normalized and isinstance(normalized["harnesses"], dict):
            if "routing" in normalized["harnesses"]:
                normalized["harness_routing"] = normalized["harnesses"]["routing"]
        elif "harnesses_routing" in normalized and "harness_routing" not in normalized:
            normalized["harness_routing"] = normalized["harnesses_routing"]

        # Populate default routing if missing or empty
        if "harness_routing" not in normalized or not normalized["harness_routing"]:
            normalized["harness_routing"] = {
                "coordinator": {"harness": "agy", "mode": "headless_json"},
                "pipeline_engineer": {"harness": "codex", "mode": "headless_json"},
                "neuroimaging_specialist": {"harness": "agy", "mode": "headless_json"},
                "electrophys_specialist": {"harness": "agy", "mode": "headless_json"},
                "compute_operator": {"harness": "codex", "mode": "headless_json"},
                "critic_qa": {"harness": "agy", "mode": "headless_json"},
                "scientific_writer": {"harness": "agy", "mode": "headless_json"},
            }

        return normalized

    @property
    def harnesses_routing(self) -> dict[str, HarnessRoutingConfig]:
        """Provide backward compatibility alias for harnesses_routing.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, HarnessRoutingConfig]: dictionary object
                Mapping of agent roles to harness routing configs.
        """
        result: dict[str, HarnessRoutingConfig] = self.harness_routing
        return result

    @property
    def workspace(self) -> WorkspaceConfig:
        """Provide backward compatibility alias for workspace.

        Parameters
        ------------
        None

        Returns
        --------
            WorkspaceConfig: WorkspaceConfig object
                Workspace project configuration.
        """
        result: WorkspaceConfig = self.project
        return result


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge two dictionaries, with override values taking precedence.

    Parameters
    ------------
    base: Mapping[str, Any]
        Base dictionary containing baseline or lower-tier configuration values.
    override: Mapping[str, Any]
        Overriding dictionary containing higher-priority values.

    Returns
    --------
        dict[str, Any]: dictionary object
            New merged dictionary containing combined hierarchical keys.
    """
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def find_project_root(start_path: Path | None = None) -> Path:
    """Locate the project root directory containing a .neuri/ folder.

    Traverses upwards from start_path looking for a .neuri directory.
    If none is found, returns start_path or current working directory.

    Parameters
    ------------
    start_path: Path | None
        Starting directory path for root search. Defaults to Path.cwd().

    Returns
    --------
        Path: Path object
            Discovered project root path.
    """
    current: Path = (start_path or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        if (parent / ".neuri").is_dir():
            return parent
    return current


class ConfigManager:
    """Manager for two-tier hierarchical configuration loading and persistence."""

    GLOBAL_DIR_NAME: str = ".neuri"
    GLOBAL_CONFIG_FILENAME: str = "config.toml"
    PROJECT_DIR_NAME: str = ".neuri"
    PROJECT_CONFIG_FILENAME: str = "neuri.toml"
    STATE_DB_FILENAME: str = "state.db"
    REFERENCES_FILENAME: str = "references.bib"
    HISTORY_FILENAME: str = "execution_history.json"
    QA_SNAPSHOTS_DIRNAME: str = "qa_snapshots"
    SKILLS_DIRNAME: str = "skills"

    def __init__(
        self,
        project_root: Path | None = None,
        global_config_path: Path | None = None,
    ) -> None:
        """Initialize the ConfigManager with project root and global paths.

        Parameters
        ------------
        project_root: Path | None
            Root directory of the project. If None, resolved via find_project_root().
        global_config_path: Path | None
            Custom path to global config.toml. Defaults to ~/.neuri/config.toml.

        Returns
        --------
            None: NoneType object
                Initializes ConfigManager instance state.
        """
        self.project_root: Path = project_root or find_project_root()
        self.global_config_path: Path = (
            global_config_path
            or Path.home() / self.GLOBAL_DIR_NAME / self.GLOBAL_CONFIG_FILENAME
        )
        self.project_config_path: Path = (
            self.project_root / self.PROJECT_DIR_NAME / self.PROJECT_CONFIG_FILENAME
        )

    def load(self) -> NeuriConfig:
        """Load and merge two-tier configuration from global and project files.

        Reads ~/.neuri/config.toml if present, deeply merges .neuri/neuri.toml
        overrides if present, and returns a validated NeuriConfig instance.

        Parameters
        ------------
        None

        Returns
        --------
            NeuriConfig: NeuriConfig object
                Validated two-tier configuration.
        """
        merged_dict: dict[str, Any] = {}

        if self.global_config_path.exists():
            try:
                with open(self.global_config_path, "rb") as fh:
                    global_data = tomllib.load(fh)
                    merged_dict = deep_merge(merged_dict, global_data)
            except tomllib.TOMLDecodeError as exc:
                raise ConfigError(
                    f"Syntax error in global config '{self.global_config_path}': {exc}"
                ) from exc
            except OSError as exc:
                raise ConfigError(
                    f"Failed to read global config '{self.global_config_path}': {exc}"
                ) from exc

        if self.project_config_path.exists():
            try:
                with open(self.project_config_path, "rb") as fh:
                    project_data = tomllib.load(fh)
                    merged_dict = deep_merge(merged_dict, project_data)
            except tomllib.TOMLDecodeError as exc:
                raise ConfigError(
                    f"Syntax error in project config '{self.project_config_path}': {exc}"
                ) from exc
            except OSError as exc:
                raise ConfigError(
                    f"Failed to read project config '{self.project_config_path}': {exc}"
                ) from exc

        try:
            config = NeuriConfig(**merged_dict)
        except Exception as exc:
            raise ConfigError(
                f"Configuration schema validation failed: {exc}"
            ) from exc

        return config

    def save_project_config(self, config: NeuriConfig) -> Path:
        """Serialize and write a NeuriConfig to the project .neuri/neuri.toml file.

        Parameters
        ------------
        config: NeuriConfig
            Configuration model instance to serialize.

        Returns
        --------
            Path: Path object
                Filesystem path to the written project configuration file.
        """
        neuri_dir: Path = self.project_root / self.PROJECT_DIR_NAME
        neuri_dir.mkdir(parents=True, exist_ok=True)

        config_dict = config.model_dump(mode="python", exclude_none=True)
        try:
            with open(self.project_config_path, "wb") as fh:
                tomli_w.dump(config_dict, fh)
        except OSError as exc:
            raise ConfigError(
                f"Failed to write project config '{self.project_config_path}': {exc}"
            ) from exc

        return self.project_config_path

    def init_project_workspace(
        self,
        project_name: str = "default-neuro-study",
        force: bool = False,
    ) -> dict[str, Path]:
        """Scaffold the .neuri/ project workspace directory and default files.

        Creates neuri.toml, state.db in SQLite WAL mode, references.bib,
        execution_history.json, qa_snapshots/, and skills/.

        Parameters
        ------------
        project_name: str
            Name of the project to initialize. Defaults to 'default-neuro-study'.
        force: bool
            If True, overwrites existing config without raising FileExistsError.

        Returns
        --------
            dict[str, Path]: dictionary object
                Mapping of created workspace artifact identifiers to Path objects.
        """
        neuri_dir: Path = self.project_root / self.PROJECT_DIR_NAME

        if self.project_config_path.exists() and not force:
            raise FileExistsError(
                f"Workspace already initialized at '{neuri_dir}'. "
                "Use force=True to overwrite."
            )

        neuri_dir.mkdir(parents=True, exist_ok=True)
        qa_dir = neuri_dir / self.QA_SNAPSHOTS_DIRNAME
        qa_dir.mkdir(exist_ok=True)
        skills_dir = neuri_dir / self.SKILLS_DIRNAME
        skills_dir.mkdir(exist_ok=True)

        default_config = NeuriConfig(project=WorkspaceConfig(name=project_name))
        self.save_project_config(default_config)

        state_db_path = neuri_dir / self.STATE_DB_FILENAME
        if not state_db_path.exists() or force:
            self._init_sqlite_wal(state_db_path)

        bib_path = neuri_dir / self.REFERENCES_FILENAME
        if not bib_path.exists() or force:
            bib_path.write_text(
                "% Neuri Verified Citations Ledger\n",
                encoding="utf-8",
            )

        history_path = neuri_dir / self.HISTORY_FILENAME
        if not history_path.exists() or force:
            history_path.write_text("[]\n", encoding="utf-8")

        result: dict[str, Path] = {
            "neuri_dir": neuri_dir,
            "config_file": self.project_config_path,
            "state_db": state_db_path,
            "references_bib": bib_path,
            "execution_history": history_path,
            "qa_snapshots_dir": qa_dir,
            "skills_dir": skills_dir,
        }
        return result

    def _init_sqlite_wal(self, db_path: Path) -> None:
        """Create an empty SQLite database with WAL journal mode enabled.

        Attempts to use Blackboard DDL if importable, otherwise runs base WAL pragmas.

        Parameters
        ------------
        db_path: Path
            Filesystem path to the target state.db file.

        Returns
        --------
            None: NoneType object
                Creates and configures the SQLite WAL database.
        """
        try:
            from neuri.core.blackboard import Blackboard
            Blackboard(db_path)
        except (ImportError, Exception):
            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA foreign_keys=ON;")
                conn.commit()
            finally:
                conn.close()


def load_config(
    project_root: Path | None = None,
    global_config_path: Path | None = None,
) -> NeuriConfig:
    """Load and merge two-tier configuration from global and project files.

    Parameters
    ------------
    project_root: Path | None
        Optional project root path. Defaults to automatic discovery.
    global_config_path: Path | None
        Optional explicit path to global config.toml. Defaults to ~/.neuri/config.toml.

    Returns
    --------
        NeuriConfig: NeuriConfig object
            Loaded and validated two-tier configuration.
    """
    manager = ConfigManager(
        project_root=project_root,
        global_config_path=global_config_path,
    )
    result: NeuriConfig = manager.load()
    return result


def init_workspace(
    project_root: Path | None = None,
    project_name: str = "default-neuro-study",
    force: bool = False,
) -> dict[str, Path]:
    """Scaffold a .neuri/ workspace directory in the specified project root.

    Parameters
    ------------
    project_root: Path | None
        Target directory to initialize. Defaults to current working directory.
    project_name: str
        Name of the neuroscience project. Defaults to 'default-neuro-study'.
    force: bool
        Whether to overwrite existing configuration. Defaults to False.

    Returns
    --------
        dict[str, Path]: dictionary object
            Mapping of initialized files and directory paths.
    """
    manager = ConfigManager(project_root=project_root)
    result: dict[str, Path] = manager.init_project_workspace(
        project_name=project_name,
        force=force,
    )
    return result
