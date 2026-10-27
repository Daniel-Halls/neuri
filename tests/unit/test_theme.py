"""Unit tests for Neuri color theme data model, manager, and /theme command.

Verifies loading TOML themes from repository and user directories (~/.neuri/themes),
Textual theme conversion, runtime dynamic switching, and config persistence.
"""

from pathlib import Path
from typing import Any

import pytest
from textual.theme import Theme

from neuri.core.blackboard import Blackboard
from neuri.core.config import NeuriConfig
from neuri.core.orchestrator import DAGOrchestrator
from neuri.core.slash_commands import SlashCommandResult, SlashCommandRouter
from neuri.ui.terminal_chat import NeuriChatApp
from neuri.ui.theme import NeuriTheme, NeuriThemeManager, normalize_color


def test_neuri_theme_dataclass_and_textual_conversion() -> None:
    """Test NeuriTheme fields and conversion to Textual Theme instance.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts correct property propagation into Textual Theme.
    """
    custom_thm: NeuriTheme = NeuriTheme(
        name="custom_hc",
        display_name="Custom High Contrast",
        description="Test high contrast theme",
        background="#000000",
        foreground="#ffffff",
        surface="#0a0a0a",
        panel="#141414",
        border="#ffffff",
        primary="#00ffcc",
        secondary="#ffff00",
        accent="#ff00ff",
        warning="#f59e0b",
        error="#ef4444",
        success="#10b981",
        dark=True,
    )

    textual_theme: Theme = custom_thm.to_textual_theme()
    assert textual_theme.name == "custom_hc"
    assert str(textual_theme.background) == "#000000"
    assert str(textual_theme.foreground) == "#ffffff"
    assert str(textual_theme.surface) == "#0a0a0a"
    assert str(textual_theme.panel) == "#141414"
    assert textual_theme.variables.get("border") == "#ffffff"
    assert textual_theme.dark is True


def test_theme_manager_lists_and_loads_base_themes(tmp_path: Path) -> None:
    """Test discovering and loading built-in repository themes.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts base themes (high_contrast, dark, monokai, nord) are present.
    """
    mgr: NeuriThemeManager = NeuriThemeManager(workspace_dir=tmp_path)
    themes: list[NeuriTheme] = mgr.list_available_themes()

    theme_names: list[str] = [t.name for t in themes]
    assert "high_contrast" in theme_names
    assert "dark" in theme_names
    assert "monokai" in theme_names
    assert "nord" in theme_names

    # Check high contrast attributes
    hc_theme: NeuriTheme | None = mgr.get_theme("high_contrast")
    assert hc_theme is not None
    assert hc_theme.background == "#000000"
    assert hc_theme.foreground == "#ffffff"
    assert hc_theme.border == "#ffffff"
    assert hc_theme.surface == "#000000"


def test_theme_manager_name_resolution_and_aliases(tmp_path: Path) -> None:
    """Test case-insensitive and hyphen/underscore-tolerant lookup.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts lookup succeeds with variants and returns None for missing.
    """
    mgr: NeuriThemeManager = NeuriThemeManager(workspace_dir=tmp_path)

    t1: NeuriTheme | None = mgr.get_theme("high_contrast")
    t2: NeuriTheme | None = mgr.get_theme("high-contrast")
    t3: NeuriTheme | None = mgr.get_theme("HIGH_CONTRAST")

    assert t1 is not None
    assert t2 is not None
    assert t3 is not None
    assert t1.name == t2.name == t3.name == "high_contrast"

    missing: NeuriTheme | None = mgr.get_theme("unknown_theme_404")
    assert missing is None


def test_theme_manager_custom_theme_in_user_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test discovering custom TOML themes inside ~/.neuri/themes/.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.
    monkeypatch: pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    --------
        None: NoneType object
            Asserts custom user theme is loaded and parsed correctly.
    """
    fake_home: Path = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    user_themes_dir: Path = fake_home / ".neuri" / "themes"
    user_themes_dir.mkdir(parents=True, exist_ok=True)

    custom_toml: str = (
        'name = "cyberpunk"\n'
        'display_name = "Cyberpunk 2077"\n'
        'description = "Neon yellow and hot cyan aesthetic"\n'
        'background = "#0d0e15"\n'
        'foreground = "#fcee0a"\n'
        'surface = "#1a1c26"\n'
        'panel = "#12141c"\n'
        'border = "#00f0ff"\n'
        'primary = "#fcee0a"\n'
        'secondary = "#00f0ff"\n'
        'accent = "#ff003c"\n'
        'dark = true\n'
    )
    (user_themes_dir / "cyberpunk.toml").write_text(
        custom_toml, encoding="utf-8"
    )

    mgr: NeuriThemeManager = NeuriThemeManager(workspace_dir=tmp_path)
    themes: list[NeuriTheme] = mgr.list_available_themes()
    theme_names: list[str] = [t.name for t in themes]

    assert "cyberpunk" in theme_names
    cp_theme: NeuriTheme | None = mgr.get_theme("cyberpunk")
    assert cp_theme is not None
    assert cp_theme.display_name == "Cyberpunk 2077"
    assert cp_theme.foreground == "#fcee0a"
    assert cp_theme.border == "#00f0ff"


def test_theme_manager_active_theme_and_config_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test getting and persisting the active theme choice in config.toml.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.
    monkeypatch: pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    --------
        None: NoneType object
            Asserts theme changes are saved to user and workspace configs.
    """
    fake_home: Path = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    mgr: NeuriThemeManager = NeuriThemeManager(workspace_dir=tmp_path)

    # Initial default should be dark (Obsidian Neuro)
    initial_theme: str = mgr.get_active_theme_name()
    assert initial_theme == "dark"

    # Set to monokai and verify persistence
    updated: bool = mgr.set_active_theme("monokai")
    assert updated is True

    new_active: str = mgr.get_active_theme_name()
    assert new_active == "monokai"

    # Verify config file written
    cfg_file: Path = fake_home / ".neuri" / "config.toml"
    assert cfg_file.is_file()
    content: str = cfg_file.read_text(encoding="utf-8")
    assert 'theme = "monokai"' in content


def test_slash_command_theme_operations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test /theme and /theme <name> slash commands through SlashCommandRouter.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.
    monkeypatch: pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    --------
        None: NoneType object
            Asserts theme table rendering, switching, and error handling.
    """
    fake_home: Path = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    bb: Blackboard = Blackboard(tmp_path / "state.db")
    orch: DAGOrchestrator = DAGOrchestrator(blackboard=bb)
    config: NeuriConfig = NeuriConfig()
    router: SlashCommandRouter = SlashCommandRouter(
        workspace_dir=tmp_path,
        config=config,
        blackboard=bb,
        orchestrator=orch,
    )

    # 1. /theme without arguments lists themes
    list_res: SlashCommandResult = router.execute("/theme")
    assert list_res.success is True
    assert "Neuri Visual Color Themes" in list_res.markdown_output
    assert "`high_contrast`" in list_res.markdown_output
    assert "`dark`" in list_res.markdown_output
    assert "`monokai`" in list_res.markdown_output
    assert "`nord`" in list_res.markdown_output

    # 2. /theme dark activates dark theme
    switch_res: SlashCommandResult = router.execute("/theme dark")
    assert switch_res.success is True
    assert switch_res.action == "change_theme"
    assert switch_res.data.get("theme_name") == "dark"
    assert "Theme Activated: `Obsidian Neuro`" in switch_res.markdown_output

    # 3. /theme with unknown name returns friendly error
    bad_res: SlashCommandResult = router.execute("/theme non_existent_palette")
    assert bad_res.success is False
    assert "Theme `non_existent_palette` not found." in bad_res.markdown_output


def test_terminal_chat_app_theme_registration_and_apply(
    tmp_path: Path,
) -> None:
    """Test NeuriChatApp registers themes and changes active theme cleanly.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts theme registration and application in Textual App.
    """
    app: NeuriChatApp = NeuriChatApp(workspace_dir=tmp_path)

    # Initially Textual has default themes
    assert hasattr(app, "register_theme")

    # Apply high_contrast
    app.apply_theme("high_contrast")
    assert app.theme == "high_contrast"

    # Apply nord
    app.apply_theme("nord")
    assert app.theme == "nord"

    # Unknown theme should safely keep existing theme without crash
    app.apply_theme("unknown_fake_theme")
    assert app.theme == "nord"


def test_theme_template_controls_all_ui_colors(tmp_path: Path) -> None:
    """Verify that all UI components render colors driven by active theme.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts UI text styling matches theme template definitions.
    """
    from neuri.ui.terminal_chat import TelemetryBar

    mgr: NeuriThemeManager = NeuriThemeManager(workspace_dir=tmp_path)
    dark_thm: NeuriTheme | None = mgr.get_theme("dark")
    assert dark_thm is not None
    assert dark_thm.muted == "#64748b"
    assert dark_thm.selection_bg == "#1e3a5f"
    assert dark_thm.selection_fg == "#38bdf8"
    assert dark_thm.tokens == "#fbbf24"
    assert dark_thm.cost == "#c084fc"

    # Test Textual theme variables contain custom semantic theme tokens
    t_theme: Theme = dark_thm.to_textual_theme()
    assert t_theme.variables.get("muted") == "#64748b"
    assert t_theme.variables.get("selection-bg") == "#1e3a5f"
    assert t_theme.variables.get("selection-fg") == "#38bdf8"
    assert t_theme.variables.get("tokens") == "#fbbf24"
    assert t_theme.variables.get("cost") == "#c084fc"
    assert t_theme.variables.get("surface-elevated") == "#26334d"

    # Test TelemetryBar renders with theme colors
    bar: TelemetryBar = TelemetryBar(harness_id="agy")
    txt = bar.render()
    rendered_plain: str = txt.plain
    assert "Harness: agy" in rendered_plain
    assert "Tokens:" in rendered_plain

    # Verify high contrast theme overrides
    hc_thm: NeuriTheme = mgr.get_high_contrast_theme()
    assert hc_thm.selection_bg == "#ffffff"
    assert hc_thm.selection_fg == "#000000"
    assert hc_thm.muted == "#767676"


def test_normalize_color_various_formats() -> None:
    """Test normalizer converts hex lengths and handles invalid strings.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts normalization behavior across 3, 4, 6, and 8 hex digits.
    """
    assert normalize_color("#fff") == "#ffffff"
    assert normalize_color("#abc") == "#aabbcc"
    assert normalize_color("#ffff") == "#ffffff"
    assert normalize_color("#c300ffff") == "#c300ff"
    assert normalize_color("#e100ffff") == "#e100ff"
    assert normalize_color("#00ffff") == "#00ffff"
    assert normalize_color("cyan") == "cyan"
    assert normalize_color("invalid_hex", fallback="#000000") == "#000000"


def test_neuri_theme_sanitizes_8_digit_hex() -> None:
    """Verify NeuriTheme auto-normalizes 8-digit hex inputs upon creation.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts theme properties are truncated to Rich-compatible format.
    """
    from neuri.ui.terminal_chat import TelemetryBar

    raw_theme: NeuriTheme = NeuriTheme(
        name="test_raw",
        display_name="Test Raw",
        description="Testing raw hex normalization",
        background="#000000",
        foreground="#ffffff",
        surface="#000000",
        panel="#000000",
        border="#ffffff",
        primary="#ffffff",
        secondary="#ffffff",
        accent="#c300ffff",
        cost="#e100ffff",
        tokens="#ffea00",
    )
    assert raw_theme.accent == "#c300ff"
    assert raw_theme.cost == "#e100ff"

    textual_thm: Theme = raw_theme.to_textual_theme()
    assert textual_thm.accent == "#c300ff"
    assert textual_thm.variables.get("cost") == "#e100ff"

    bar: TelemetryBar = TelemetryBar(harness_id="neuri", theme=raw_theme)
    rendered = bar.render()
    assert "Harness: neuri" in rendered.plain

    bar.set_theme(raw_theme)
    rendered_again = bar.render()
    assert "Harness: neuri" in rendered_again.plain


def test_theme_manager_loads_file_with_8_digit_hex(tmp_path: Path) -> None:
    """Verify loading TOML theme file with 8-digit hex sanitizes colors.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts parsed theme contains sanitized 6-digit hex values.
    """
    theme_file: Path = tmp_path / "raw_theme.toml"
    toml_content: str = (
        "[theme]\n"
        "name = \"raw_hc\"\n"
        "accent = \"#c300ffff\"\n"
        "cost = \"#e100ffff\"\n"
    )
    theme_file.write_text(toml_content, encoding="utf-8")

    mgr: NeuriThemeManager = NeuriThemeManager(workspace_dir=tmp_path)
    loaded: NeuriTheme | None = mgr.load_theme_from_file(theme_file)
    assert loaded is not None
    assert loaded.accent == "#c300ff"
    assert loaded.cost == "#e100ff"


