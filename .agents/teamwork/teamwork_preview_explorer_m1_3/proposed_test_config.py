"""Unit tests for Neuri configuration loader and workspace initialization (M1).

Verifies two-tier TOML loading (~/.neuri/config.toml + .neuri/neuri.toml),
deep merge resolution, workspace scaffolding, Pydantic model validation,
and corrupted file error handling.
"""

from pathlib import Path
import sqlite3
from typing import Any

from pydantic import ValidationError
import pytest
import tomli_w

from neuri.core.config import (
    BudgetConfig,
    ConfigError,
    ConfigManager,
    HarnessRoutingConfig,
    NeuriConfig,
    WorkspaceConfig,
    deep_merge,
    find_project_root,
    init_workspace,
    load_config,
)


def test_workspace_config_defaults() -> None:
    """Verify default values for WorkspaceConfig and ProjectConfig alias.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts workspace config default attributes.
    """
    config = WorkspaceConfig()
    assert config.name == "default-neuro-study"
    assert config.default_remote_host == "localhost"
    assert config.remote_bids_root is None


def test_harness_routing_config_validation() -> None:
    """Verify HarnessRoutingConfig default attributes and execution mode validation.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts valid execution modes and rejects invalid modes.
    """
    valid_route = HarnessRoutingConfig(harness="agy", mode="headless_json")
    assert valid_route.harness == "agy"
    assert valid_route.mode == "headless_json"

    interactive_route = HarnessRoutingConfig(harness="codex", mode="interactive_pty")
    assert interactive_route.mode == "interactive_pty"

    with pytest.raises(ValidationError):
        HarnessRoutingConfig(harness="agy", mode="unsupported_mode")


def test_budget_config_validation() -> None:
    """Verify BudgetConfig defaults and boundary validation rules.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts budget defaults and rejects negative numbers.
    """
    budgets = BudgetConfig()
    assert budgets.max_node_tokens == 64000
    assert budgets.max_workflow_cost_usd == 10.00
    assert budgets.max_node_retries == 2
    assert budgets.async_job_threshold_seconds == 20
    assert budgets.consecutive_failure_threshold == 3

    # Rejects non-positive token budget
    with pytest.raises(ValidationError):
        BudgetConfig(max_node_tokens=0)

    with pytest.raises(ValidationError):
        BudgetConfig(max_node_tokens=-500)

    # Rejects negative workflow cost
    with pytest.raises(ValidationError):
        BudgetConfig(max_workflow_cost_usd=-1.0)


def test_neuri_config_default_routing_roles() -> None:
    """Verify that default NeuriConfig populates all 7 required agent roles.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts that the 7 core agent roles are present in harness routing.
    """
    cfg = NeuriConfig()
    expected_roles = {
        "coordinator",
        "pipeline_engineer",
        "neuroimaging_specialist",
        "electrophys_specialist",
        "compute_operator",
        "critic_qa",
        "scientific_writer",
    }
    actual_roles = set(cfg.harness_routing.keys())
    assert expected_roles.issubset(actual_roles)
    assert cfg.harness_routing["coordinator"].harness == "agy"
    assert cfg.harness_routing["pipeline_engineer"].harness == "codex"
    assert cfg.workspace.name == "default-neuro-study"
    assert cfg.harnesses_routing == cfg.harness_routing


def test_deep_merge_basic_and_nested() -> None:
    """Verify recursive dictionary merging with precedence logic.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts deep merge behavior for shallow and nested dictionaries.
    """
    base: dict[str, Any] = {
        "project": {"name": "base-study", "host": "local"},
        "budgets": {"max_tokens": 1000, "max_cost": 5.0},
        "flags": ["a", "b"],
    }
    override: dict[str, Any] = {
        "project": {"name": "override-study"},
        "budgets": {"max_tokens": 2000},
        "flags": ["c"],
        "extra": "new_val",
    }
    merged = deep_merge(base, override)

    # Nested fields are merged recursively without dropping sibling keys
    assert merged["project"]["name"] == "override-study"
    assert merged["project"]["host"] == "local"
    assert merged["budgets"]["max_tokens"] == 2000
    assert merged["budgets"]["max_cost"] == 5.0
    assert merged["flags"] == ["c"]
    assert merged["extra"] == "new_val"


def test_load_config_defaults_when_files_absent(tmp_path: Path) -> None:
    """Verify load_config returns clean defaults when config files do not exist.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts clean default configuration instantiation.
    """
    empty_root = tmp_path / "empty_workspace"
    empty_root.mkdir()
    nonexistent_global = tmp_path / "missing_global.toml"

    config = load_config(
        project_root=empty_root,
        global_config_path=nonexistent_global,
    )
    assert isinstance(config, NeuriConfig)
    assert config.project.name == "default-neuro-study"
    assert config.budgets.max_node_tokens == 64000


def test_load_config_global_override_only(tmp_path: Path) -> None:
    """Verify global config file overrides baseline defaults.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts global configuration overrides.
    """
    global_file = tmp_path / "global_config.toml"
    global_data = {
        "project": {"default_remote_host": "cluster.neuro.edu"},
        "budgets": {"max_workflow_cost_usd": 25.0},
    }
    with open(global_file, "wb") as fh:
        tomli_w.dump(global_data, fh)

    project_root = tmp_path / "project_no_config"
    project_root.mkdir()

    config = load_config(
        project_root=project_root,
        global_config_path=global_file,
    )
    assert config.project.default_remote_host == "cluster.neuro.edu"
    assert config.budgets.max_workflow_cost_usd == 25.0
    assert config.project.name == "default-neuro-study"


def test_load_config_project_override_only(tmp_path: Path) -> None:
    """Verify project-local config file overrides baseline defaults.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts project configuration overrides.
    """
    project_root = tmp_path / "my_project"
    neuri_dir = project_root / ".neuri"
    neuri_dir.mkdir(parents=True)
    project_file = neuri_dir / "neuri.toml"

    project_data = {
        "project": {"name": "fmri-resting-state"},
        "budgets": {"max_node_tokens": 128000},
    }
    with open(project_file, "wb") as fh:
        tomli_w.dump(project_data, fh)

    missing_global = tmp_path / "no_global.toml"
    config = load_config(
        project_root=project_root,
        global_config_path=missing_global,
    )
    assert config.project.name == "fmri-resting-state"
    assert config.budgets.max_node_tokens == 128000
    assert config.project.default_remote_host == "localhost"


def test_load_config_two_tier_hierarchical_merge(tmp_path: Path) -> None:
    """Verify two-tier hierarchy: project config overrides global config.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts hierarchical merge precedence.
    """
    # 1. Global config specifies cluster and high cost limit
    global_file = tmp_path / "global_config.toml"
    global_data = {
        "project": {
            "name": "global-name",
            "default_remote_host": "hpc-cluster",
        },
        "budgets": {
            "max_node_tokens": 100000,
            "max_workflow_cost_usd": 50.0,
        },
    }
    with open(global_file, "wb") as fh:
        tomli_w.dump(global_data, fh)

    # 2. Project config overrides name and tokens, preserves host and cost
    project_root = tmp_path / "study_project"
    neuri_dir = project_root / ".neuri"
    neuri_dir.mkdir(parents=True)
    project_file = neuri_dir / "neuri.toml"
    project_data = {
        "project": {"name": "specific-study"},
        "budgets": {"max_node_tokens": 32000},
    }
    with open(project_file, "wb") as fh:
        tomli_w.dump(project_data, fh)

    config = load_config(
        project_root=project_root,
        global_config_path=global_file,
    )
    # Project overrides global
    assert config.project.name == "specific-study"
    assert config.budgets.max_node_tokens == 32000
    # Global inherited when not overridden by project
    assert config.project.default_remote_host == "hpc-cluster"
    assert config.budgets.max_workflow_cost_usd == 50.0


def test_load_config_corrupted_toml_raises_config_error(tmp_path: Path) -> None:
    """Verify syntax error in TOML configuration raises ConfigError.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts ConfigError is raised on syntax corruption.
    """
    corrupted_global = tmp_path / "bad_global.toml"
    corrupted_global.write_text('project = { name = "unclosed string\n', encoding="utf-8")

    project_root = tmp_path / "proj"
    project_root.mkdir()

    with pytest.raises(ConfigError) as exc_info:
        load_config(
            project_root=project_root,
            global_config_path=corrupted_global,
        )
    assert "Syntax error in global config" in str(exc_info.value)


def test_load_config_invalid_schema_type_raises_config_error(tmp_path: Path) -> None:
    """Verify non-numeric value for numeric budget raises ConfigError.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts ConfigError is raised on schema type mismatch.
    """
    project_root = tmp_path / "type_mismatch_proj"
    neuri_dir = project_root / ".neuri"
    neuri_dir.mkdir(parents=True)
    project_file = neuri_dir / "neuri.toml"

    # Write integer field as invalid string
    project_file.write_text(
        '[budgets]\nmax_node_tokens = "invalid_string_tokens"\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError) as exc_info:
        load_config(
            project_root=project_root,
            global_config_path=tmp_path / "missing.toml",
        )
    assert "Configuration schema validation failed" in str(exc_info.value)


def test_load_config_harness_routing_table_formats(tmp_path: Path) -> None:
    """Verify [harnesses.routing] nested table in TOML is normalized.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts normalization of harness routing table syntax.
    """
    project_root = tmp_path / "routing_project"
    neuri_dir = project_root / ".neuri"
    neuri_dir.mkdir(parents=True)
    project_file = neuri_dir / "neuri.toml"

    # Write TOML using nested table syntax
    toml_content = """
    [project]
    name = "routing-test"

    [harnesses.routing]
    coordinator = { harness = "codex", mode = "headless_json" }
    pipeline_engineer = { harness = "opencode", mode = "headless_json" }
    """
    project_file.write_text(toml_content, encoding="utf-8")

    config = load_config(
        project_root=project_root,
        global_config_path=tmp_path / "missing.toml",
    )
    assert config.harness_routing["coordinator"].harness == "codex"
    assert config.harness_routing["pipeline_engineer"].harness == "opencode"
    # Unmentioned roles retain defaults
    assert config.harness_routing["critic_qa"].harness == "agy"


def test_init_workspace_clean_scaffolding(tmp_path: Path) -> None:
    """Verify init_workspace scaffolds all required files and directories.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts presence and contents of all scaffolded workspace files.
    """
    project_root = tmp_path / "new_neuro_study"
    project_root.mkdir()

    paths = init_workspace(
        project_root=project_root,
        project_name="sub-01-preprocessing",
    )

    # 1. Directory exists
    assert paths["neuri_dir"].is_dir()
    assert (project_root / ".neuri").is_dir()

    # 2. neuri.toml exists and has correct project name
    assert paths["config_file"].is_file()
    loaded_config = load_config(project_root=project_root)
    assert loaded_config.project.name == "sub-01-preprocessing"

    # 3. state.db is valid SQLite file in WAL mode
    assert paths["state_db"].is_file()
    conn = sqlite3.connect(str(paths["state_db"]))
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    conn.close()
    assert mode.lower() == "wal"

    # 4. references.bib has header
    assert paths["references_bib"].is_file()
    assert "% Neuri Verified Citations Ledger" in paths["references_bib"].read_text(
        encoding="utf-8"
    )

    # 5. execution_history.json is valid empty JSON list
    assert paths["execution_history"].is_file()
    assert paths["execution_history"].read_text(encoding="utf-8").strip() == "[]"

    # 6. qa_snapshots/ and skills/ directories exist
    assert paths["qa_snapshots_dir"].is_dir()
    assert paths["skills_dir"].is_dir()


def test_init_workspace_collision_raises_file_exists_error(tmp_path: Path) -> None:
    """Verify init_workspace raises FileExistsError on existing workspace without force.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts FileExistsError on unforced re-initialization.
    """
    project_root = tmp_path / "colliding_study"
    project_root.mkdir()

    init_workspace(project_root=project_root, project_name="initial-study")

    with pytest.raises(FileExistsError) as exc_info:
        init_workspace(project_root=project_root, project_name="second-study")
    assert "Workspace already initialized" in str(exc_info.value)


def test_init_workspace_force_overwrites(tmp_path: Path) -> None:
    """Verify init_workspace with force=True reinitializes workspace cleanly.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts successful overwrite when force is True.
    """
    project_root = tmp_path / "forced_study"
    project_root.mkdir()

    init_workspace(project_root=project_root, project_name="first-run")
    cfg1 = load_config(project_root=project_root)
    assert cfg1.project.name == "first-run"

    # Force reinitialize with new name
    init_workspace(
        project_root=project_root,
        project_name="second-run",
        force=True,
    )
    cfg2 = load_config(project_root=project_root)
    assert cfg2.project.name == "second-run"


def test_find_project_root_discovery(tmp_path: Path) -> None:
    """Verify find_project_root traverses parent directories to discover .neuri/.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts root discovery from deep subdirectories.
    """
    project_root = tmp_path / "repo_root"
    deep_subdir = project_root / "src" / "deep" / "nested" / "dir"
    deep_subdir.mkdir(parents=True)

    # Before .neuri exists, find_project_root returns deep_subdir
    assert find_project_root(deep_subdir) == deep_subdir.resolve()

    # Create .neuri at project_root
    (project_root / ".neuri").mkdir()

    # Now traverses up and discovers project_root
    discovered = find_project_root(deep_subdir)
    assert discovered == project_root.resolve()
