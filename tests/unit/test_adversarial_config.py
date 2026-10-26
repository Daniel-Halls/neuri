"""Adversarial stress-test suite for Neuri configuration and catalog (M1).

Stress-tests two-tier hierarchical configuration merging, corrupted/empty
TOML parsing, concurrent workspace scaffolding, SQLite WAL mode persistence,
boundary value validation, and skills/index.yaml token bounds.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
from typing import Any
import pytest
import tomli_w
import yaml

from neuri.core.paths import PathResolver
from neuri.core.config import (
    BudgetConfig,
    ConfigError,
    ConfigManager,
    HarnessRoutingConfig,
    NeuriConfig,
    WorkspaceConfig,
    deep_merge,
    init_workspace,
    load_config,
)


def test_deep_merge_scalar_overwrites_dict() -> None:
    """Verify scalar in override replaces nested dictionary in base.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts scalar replaces dictionary without exception.
    """
    base: dict[str, Any] = {"section": {"nested_key": "nested_value"}}
    override: dict[str, Any] = {"section": 42}
    merged: dict[str, Any] = deep_merge(base, override)
    assert merged["section"] == 42


def test_deep_merge_dict_overwrites_scalar() -> None:
    """Verify dictionary in override replaces scalar in base.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts dictionary replaces scalar without exception.
    """
    base: dict[str, Any] = {"section": 42}
    override: dict[str, Any] = {"section": {"new_key": "new_val"}}
    merged: dict[str, Any] = deep_merge(base, override)
    assert merged["section"] == {"new_key": "new_val"}


def test_deep_merge_list_replacement_semantics() -> None:
    """Verify lists are replaced atomically rather than concatenated.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts override list takes full precedence.
    """
    base: dict[str, Any] = {"items": [1, 2, 3], "tags": ["alpha"]}
    override: dict[str, Any] = {"items": [4, 5]}
    merged: dict[str, Any] = deep_merge(base, override)
    assert merged["items"] == [4, 5]
    assert merged["tags"] == ["alpha"]


def test_deep_merge_deeply_nested_hierarchy() -> None:
    """Verify 15-level recursive merge preserves disjoint keys.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts deep traversal preserves sibling keys across depth.
    """
    base: dict[str, Any] = {}
    curr_base: dict[str, Any] = base
    for depth in range(15):
        curr_base[f"level_{depth}_base"] = f"base_val_{depth}"
        next_dict: dict[str, Any] = {}
        curr_base["child"] = next_dict
        curr_base = next_dict

    override: dict[str, Any] = {}
    curr_override: dict[str, Any] = override
    for depth in range(15):
        curr_override[f"level_{depth}_override"] = f"override_val_{depth}"
        next_dict = {}
        curr_override["child"] = next_dict
        curr_override = next_dict

    merged: dict[str, Any] = deep_merge(base, override)

    probe: dict[str, Any] = merged
    for depth in range(15):
        assert probe[f"level_{depth}_base"] == f"base_val_{depth}"
        assert probe[f"level_{depth}_override"] == f"override_val_{depth}"
        probe = probe["child"]


def test_deep_merge_empty_and_special_keys() -> None:
    """Verify deep merge with empty dictionaries and unicode keys.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts merge with empty dicts and unicode keys behaves cleanly.
    """
    assert deep_merge({}, {}) == {}
    assert deep_merge({"a": 1}, {}) == {"a": 1}
    assert deep_merge({}, {"b": 2}) == {"b": 2}

    base: dict[str, Any] = {"🧠": {"key.with.dots": "val1"}}
    override: dict[str, Any] = {"🧠": {"key_underscores": "val2"}}
    merged: dict[str, Any] = deep_merge(base, override)
    assert merged["🧠"]["key.with.dots"] == "val1"
    assert merged["🧠"]["key_underscores"] == "val2"


def test_load_config_empty_toml_files(tmp_path: Path) -> None:
    """Verify empty TOML files load default configuration without crashing.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts zero-byte configuration files resolve to valid defaults.
    """
    empty_global: Path = tmp_path / "empty_global.toml"
    empty_global.touch()

    project_root: Path = tmp_path / "project_empty"
    neuri_dir: Path = project_root / ".neuri"
    neuri_dir.mkdir(parents=True)
    empty_project: Path = neuri_dir / "neuri.toml"
    empty_project.touch()

    config: NeuriConfig = load_config(
        project_root=project_root,
        global_config_path=empty_global,
    )
    assert config.project.name == "default-neuro-study"
    assert config.budgets.max_node_tokens == 64000
    assert len(config.harness_routing) == 7


def test_load_config_whitespace_and_comments_only(tmp_path: Path) -> None:
    """Verify TOML files containing only comments load default configuration.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts comment-only files resolve to valid defaults.
    """
    global_file: Path = tmp_path / "commented_global.toml"
    global_file.write_text(
        "# Just comments and whitespace\n\n# Another comment\n",
        encoding="utf-8",
    )

    project_root: Path = tmp_path / "project_comments"
    project_root.mkdir()

    config: NeuriConfig = load_config(
        project_root=project_root,
        global_config_path=global_file,
    )
    assert config.project.default_remote_host == "localhost"
    assert config.budgets.max_workflow_cost_usd == 10.00


def test_load_config_malformed_syntax_raises_config_error(
    tmp_path: Path,
) -> None:
    """Verify various malformed TOML structures raise ConfigError.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts ConfigError is raised on invalid TOML syntax.
    """
    project_root: Path = tmp_path / "bad_syntax_proj"
    neuri_dir: Path = project_root / ".neuri"
    neuri_dir.mkdir(parents=True)
    bad_file: Path = neuri_dir / "neuri.toml"

    # 1. Unclosed array
    bad_file.write_text("array = [1, 2,\n", encoding="utf-8")
    with pytest.raises(ConfigError) as exc_info:
        load_config(
            project_root=project_root,
            global_config_path=tmp_path / "none.toml",
        )
    assert "Syntax error in project config" in str(exc_info.value)

    # 2. Duplicate keys
    bad_file.write_text("key = 1\nkey = 2\n", encoding="utf-8")
    with pytest.raises(ConfigError) as exc_info:
        load_config(
            project_root=project_root,
            global_config_path=tmp_path / "none.toml",
        )
    assert "Syntax error in project config" in str(exc_info.value)


def test_load_config_directory_as_config_file_raises_config_error(
    tmp_path: Path,
) -> None:
    """Verify passing directory path as config file raises ConfigError.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts ConfigError on directory read error.
    """
    bogus_dir: Path = tmp_path / "bogus_dir.toml"
    bogus_dir.mkdir()

    project_root: Path = tmp_path / "proj"
    project_root.mkdir()

    with pytest.raises(ConfigError) as exc_info:
        load_config(
            project_root=project_root,
            global_config_path=bogus_dir,
        )
    assert "Failed to read global config" in str(exc_info.value)


def test_load_config_unicode_and_emojis(tmp_path: Path) -> None:
    """Verify Unicode strings and emojis in project config parse correctly.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts UTF-8 emojis and multilingual names load intact.
    """
    project_root: Path = tmp_path / "unicode_proj"
    neuri_dir: Path = project_root / ".neuri"
    neuri_dir.mkdir(parents=True)
    proj_file: Path = neuri_dir / "neuri.toml"

    content: str = """
    [project]
    name = "🧠 脳神経科学プロジェクト α"
    default_remote_host = "cluster.東京.jp"
    remote_bids_root = "cluster.東京.jp:///data/研究/bids"
    """
    proj_file.write_text(content, encoding="utf-8")

    config: NeuriConfig = load_config(
        project_root=project_root,
        global_config_path=tmp_path / "none.toml",
    )
    assert config.project.name == "🧠 脳神経科学プロジェクト α"
    assert config.project.default_remote_host == "cluster.東京.jp"
    assert config.project.remote_bids_root == "cluster.東京.jp:///data/研究/bids"


def test_budget_config_boundary_and_extremes() -> None:
    """Verify boundary extremes on BudgetConfig fields.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts boundary validations for tokens and costs.
    """
    # Minimum positive integer for max_node_tokens
    b_min: BudgetConfig = BudgetConfig(max_node_tokens=1)
    assert b_min.max_node_tokens == 1

    # Exact zero is rejected for max_node_tokens
    with pytest.raises(Exception):
        BudgetConfig(max_node_tokens=0)

    # Exact zero is permitted for max_workflow_cost_usd
    b_zero_cost: BudgetConfig = BudgetConfig(max_workflow_cost_usd=0.0)
    assert b_zero_cost.max_workflow_cost_usd == 0.0

    # Negative cost is rejected
    with pytest.raises(Exception):
        BudgetConfig(max_workflow_cost_usd=-0.001)

    # Large budget numbers are handled without overflow
    b_large: BudgetConfig = BudgetConfig(
        max_node_tokens=10**9,
        max_workflow_cost_usd=100000.0,
    )
    assert b_large.max_node_tokens == 10**9
    assert b_large.max_workflow_cost_usd == 100000.0


def test_harness_routing_mode_strict_validation() -> None:
    """Verify strict validation of harness execution mode.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts rejection of invalid modes and case sensitivity.
    """
    # Valid modes
    r1: HarnessRoutingConfig = HarnessRoutingConfig(mode="headless_json")
    assert r1.mode == "headless_json"
    r2: HarnessRoutingConfig = HarnessRoutingConfig(mode="interactive_pty")
    assert r2.mode == "interactive_pty"

    # Invalid uppercase mode
    with pytest.raises(Exception):
        HarnessRoutingConfig(mode="HEADLESS_JSON")

    # Invalid arbitrary string
    with pytest.raises(Exception):
        HarnessRoutingConfig(mode="batch")


def test_harness_routing_custom_roles_preservation(tmp_path: Path) -> None:
    """Verify custom agent roles are preserved alongside 7 default roles.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts custom roles are merged into harness routing table.
    """
    project_root: Path = tmp_path / "custom_roles_proj"
    neuri_dir: Path = project_root / ".neuri"
    neuri_dir.mkdir(parents=True)
    proj_file: Path = neuri_dir / "neuri.toml"

    content: str = """
    [harness_routing.neuromorphic_specialist]
    harness = "ollama"
    mode = "headless_json"

    [harness_routing.coordinator]
    harness = "codex"
    mode = "interactive_pty"
    """
    proj_file.write_text(content, encoding="utf-8")

    config: NeuriConfig = load_config(
        project_root=project_root,
        global_config_path=tmp_path / "none.toml",
    )
    # Custom 8th role is present
    assert "neuromorphic_specialist" in config.harness_routing
    assert config.harness_routing["neuromorphic_specialist"].harness == "ollama"

    # Coordinator was overridden
    assert config.harness_routing["coordinator"].harness == "codex"
    assert config.harness_routing["coordinator"].mode == "interactive_pty"

    # Other 6 defaults remain intact
    assert config.harness_routing["pipeline_engineer"].harness == "codex"
    assert config.harness_routing["critic_qa"].harness == "agy"
    assert len(config.harness_routing) == 8


def test_save_project_config_none_exclusion(tmp_path: Path) -> None:
    """Verify save_project_config excludes None fields so TOML serialization succeeds.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts config with None field serializes cleanly without TypeError.
    """
    project_root: Path = tmp_path / "save_test_proj"
    manager: ConfigManager = ConfigManager(project_root=project_root)

    cfg: NeuriConfig = NeuriConfig(
        project=WorkspaceConfig(
            name="exclude-none-study",
            remote_bids_root=None,
        )
    )
    saved_path: Path = manager.save_project_config(cfg)
    assert saved_path.is_file()

    # Re-reading config confirms roundtrip
    loaded: NeuriConfig = manager.load()
    assert loaded.project.name == "exclude-none-study"
    assert loaded.project.remote_bids_root is None


def test_init_workspace_sqlite_wal_pragmas_and_persistence(
    tmp_path: Path,
) -> None:
    """Verify SQLite database created by init_workspace persists WAL journal mode.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts SQLite format 3 header, WAL journal mode, and read-write ops.
    """
    project_root: Path = tmp_path / "wal_study"
    paths: dict[str, Path] = init_workspace(
        project_root=project_root,
        project_name="wal-persistence-test",
    )

    db_path: Path = paths["state_db"]
    assert db_path.is_file()

    # Verify SQLite file header (16 bytes: 'SQLite format 3\x00')
    with open(db_path, "rb") as fh:
        header: bytes = fh.read(16)
    assert header == b"SQLite format 3\x00"

    # Open fresh independent connection to confirm persistent WAL mode
    conn: sqlite3.Connection = sqlite3.connect(str(db_path))
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode;")
    row: tuple[Any, ...] | None = cursor.fetchone()
    assert row is not None
    assert str(row[0]).lower() == "wal"

    # Verify basic read/write operation works in WAL mode
    cursor.execute("CREATE TABLE test_kv (k TEXT PRIMARY KEY, v TEXT);")
    cursor.execute("INSERT INTO test_kv VALUES ('probe', 'verified');")
    conn.commit()

    cursor.execute("SELECT v FROM test_kv WHERE k = 'probe';")
    val_row: tuple[Any, ...] | None = cursor.fetchone()
    assert val_row is not None
    assert val_row[0] == "verified"
    conn.close()


def test_init_workspace_concurrent_scaffolding(tmp_path: Path) -> None:
    """Verify concurrent init_workspace invocations on distinct roots succeed.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts multi-threaded workspace initialization completes cleanly.
    """
    def _init_worker(worker_id: int) -> bool:
        """Initialize a dedicated workspace per worker thread.

        Parameters
        ------------
        worker_id: int
            Thread identifier.

        Returns
        --------
            bool: boolean object
                True if workspace scaffolded successfully.
        """
        root: Path = tmp_path / f"worker_{worker_id}"
        out: dict[str, Path] = init_workspace(
            project_root=root,
            project_name=f"study-{worker_id}",
        )
        status: bool = out["config_file"].is_file() and out["state_db"].is_file()
        return status

    with ThreadPoolExecutor(max_workers=4) as executor:
        results: list[bool] = list(executor.map(_init_worker, range(4)))

    assert all(results)
    assert len(results) == 4


def test_skills_catalog_token_and_word_count_limits() -> None:
    """Empirically verify skills/index.yaml is strictly below 300 tokens.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts word count < 250 and character count < 2500.
    """
    catalog_path: Path = PathResolver.get_default_skills_index()
    assert catalog_path.is_file(), f"Catalog not found at {catalog_path}"

    text: str = catalog_path.read_text(encoding="utf-8")
    words: list[str] = text.split()
    word_count: int = len(words)
    char_count: int = len(text)
    line_count: int = len(text.splitlines())

    # Tier-0 compact catalog constraint: < 300 tokens (< 250 word target)
    assert word_count < 250, (
        f"Catalog word count ({word_count}) exceeds budget."
    )
    # Text length should be under 2500 characters
    assert char_count < 2500, (
        f"Catalog character count ({char_count}) exceeds budget."
    )
    assert line_count <= 60, (
        f"Catalog line count ({line_count}) exceeds budget."
    )


def test_skills_catalog_structure_and_completeness() -> None:
    """Verify skills/index.yaml contains all 7 public neuroscience skill packs.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts presence and required schema fields for 7 skill packs.
    """
    catalog_path: Path = PathResolver.get_default_skills_index()
    data: dict[str, Any] = yaml.safe_load(
        catalog_path.read_text(encoding="utf-8")
    )

    assert data.get("version") == "1.0"
    assert data.get("catalog") == "neuro_skills_tier0"

    skills: list[dict[str, Any]] = data.get("skills", [])
    assert len(skills) == 7, f"Expected 7 skills, found {len(skills)}"

    expected_ids: set[str] = {
        "bids-standard",
        "neuroimaging-preproc",
        "fmri-postproc",
        "dwi-tractography",
        "eeg-meg-pipeline",
        "remote-compute-slurm",
        "scientific-writing-neuro",
    }
    actual_ids: set[str] = {s["id"] for s in skills}
    assert actual_ids == expected_ids

    required_keys: set[str] = {
        "id",
        "aliases",
        "name",
        "description",
        "modalities",
        "triggers",
    }
    for skill in skills:
        assert required_keys.issubset(set(skill.keys()))
        assert isinstance(skill["aliases"], list) and len(skill["aliases"]) >= 1
        assert isinstance(skill["modalities"], list) and len(skill["modalities"]) >= 1
        assert isinstance(skill["triggers"], list) and len(skill["triggers"]) >= 1
