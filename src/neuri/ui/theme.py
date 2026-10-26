"""Color theme data model, TOML loader, and manager for Neuri TUI.

Provides oh-my-zsh style color themes stored in $HOME/.neuri/themes/,
including high-contrast (VS Code style pure black/white), dark, monokai,
and nord, with dynamic switching and config persistence.
"""

from dataclasses import dataclass, field
from pathlib import Path
import tomllib
from typing import Any

from textual.theme import Theme
import tomli_w

from neuri.core.paths import PathResolver


@dataclass(frozen=True)
class NeuriTheme:
    """Encapsulates color palette attributes for Neuri TUI components.

    Parameters
    ------------
    name: str
        Canonical theme identifier (e.g. 'high_contrast', 'dark', 'monokai').
    display_name: str
        Human-readable title for UI menus.
    description: str
        Explanatory description of the color aesthetic.
    background: str
        Terminal background hex color.
    foreground: str
        Primary text and content hex color.
    surface: str
        Surface elements (banner, input container, telemetry bar).
    panel: str
        Sidebar and docked drawer background color.
    border: str
        Frame and box borders hex color.
    primary: str
        Primary accent and user prompts color.
    secondary: str
        Secondary accent and assistant labels color.
    accent: str
        Focus highlights and special pill indicators.
    warning: str
        Warning indicator color.
    error: str
        Error indicator color.
    success: str
        Success and active shell mode indicator color.
    dark: bool
        Whether theme is a dark variant. Defaults to True.

    Returns
    --------
        NeuriTheme: NeuriTheme instance
            Constructed theme data model.
    """

    name: str
    display_name: str
    description: str
    background: str
    foreground: str
    surface: str
    panel: str
    border: str
    primary: str
    secondary: str
    accent: str
    warning: str = "#f59e0b"
    error: str = "#ef4444"
    success: str = "#10b981"
    dark: bool = True

    def to_textual_theme(self) -> Theme:
        """Convert this theme into a native Textual Theme instance.

        Parameters
        ------------
        None

        Returns
        --------
            Theme: Theme instance
                Registered Textual theme object.
        """
        textual_theme: Theme = Theme(
            name=self.name,
            primary=self.primary,
            secondary=self.secondary,
            warning=self.warning,
            error=self.error,
            success=self.success,
            accent=self.accent,
            foreground=self.foreground,
            background=self.background,
            surface=self.surface,
            panel=self.panel,
            dark=self.dark,
            variables={
                "border": self.border,
            },
        )
        return textual_theme


class NeuriThemeManager:
    """Manages discovery, loading, and persistence of Neuri visual themes.

    Parameters
    ------------
    workspace_dir: Path | None
        Optional workspace directory. Defaults to None.

    Returns
    --------
        NeuriThemeManager: NeuriThemeManager instance
            Constructed theme manager utility.
    """

    DEFAULT_THEME_NAME: str = "high_contrast"

    def __init__(self, workspace_dir: Path | None = None) -> None:
        """Initialize theme manager with workspace context.

        Parameters
        ------------
        workspace_dir: Path | None
            Workspace directory path. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes manager state.
        """
        self._workspace_dir: Path | None = workspace_dir

    def load_theme_from_file(self, path: Path) -> NeuriTheme | None:
        """Parse a theme definition TOML file into a NeuriTheme instance.

        Parameters
        ------------
        path: Path
            Path to theme TOML file.

        Returns
        --------
            NeuriTheme | None: NeuriTheme instance or None
                Loaded theme if valid, None on parse failure.
        """
        if not path.is_file():
            return None

        try:
            content: str = path.read_text(encoding="utf-8")
            raw_data: dict[str, Any] = tomllib.loads(content)
            theme_dict: dict[str, Any] = raw_data.get("theme", raw_data)

            loaded_theme: NeuriTheme = NeuriTheme(
                name=str(theme_dict.get("name", path.stem)),
                display_name=str(
                    theme_dict.get("display_name", path.stem.replace("_", " ").title())
                ),
                description=str(
                    theme_dict.get("description", "Custom Neuri color theme.")
                ),
                background=str(theme_dict.get("background", "#000000")),
                foreground=str(theme_dict.get("foreground", "#ffffff")),
                surface=str(theme_dict.get("surface", "#000000")),
                panel=str(theme_dict.get("panel", "#000000")),
                border=str(theme_dict.get("border", "#ffffff")),
                primary=str(theme_dict.get("primary", "#ffffff")),
                secondary=str(theme_dict.get("secondary", "#ffffff")),
                accent=str(theme_dict.get("accent", "#00ffff")),
                warning=str(theme_dict.get("warning", "#ffea00")),
                error=str(theme_dict.get("error", "#ff0055")),
                success=str(theme_dict.get("success", "#00ff66")),
                dark=bool(theme_dict.get("dark", True)),
            )
            return loaded_theme
        except Exception:
            return None

    def list_available_themes(self) -> list[NeuriTheme]:
        """Discover and load all available themes from user and base folders.

        Parameters
        ------------
        None

        Returns
        --------
            list[NeuriTheme]: list object
                Sorted list of unique available Neuri themes.
        """
        search_dirs: list[Path] = []
        if self._workspace_dir is not None:
            local_themes: Path = self._workspace_dir / ".neuri" / "themes"
            if local_themes.is_dir():
                search_dirs.append(local_themes)

        user_themes: Path = Path.home() / ".neuri" / "themes"
        if user_themes.is_dir() and user_themes not in search_dirs:
            search_dirs.append(user_themes)

        base_themes: Path = PathResolver.get_base_template_dir() / "themes"
        if base_themes.is_dir() and base_themes not in search_dirs:
            search_dirs.append(base_themes)

        repo_themes: Path = PathResolver.get_repo_root() / "themes"
        if repo_themes.is_dir() and repo_themes not in search_dirs:
            search_dirs.append(repo_themes)

        seen_names: set[str] = set()
        themes: list[NeuriTheme] = []

        for s_dir in search_dirs:
            for toml_file in sorted(s_dir.glob("*.toml")):
                t: NeuriTheme | None = self.load_theme_from_file(toml_file)
                if t is not None and t.name not in seen_names:
                    seen_names.add(t.name)
                    themes.append(t)

        if not themes:
            fallback: NeuriTheme = self.get_high_contrast_theme()
            themes.append(fallback)

        return themes

    def get_theme(
        self, name: str, fallback_to_default: bool = False
    ) -> NeuriTheme | None:
        """Resolve theme by name or optionally return high-contrast fallback.

        Parameters
        ------------
        name: str
            Theme name to find (e.g. 'high_contrast', 'dark', 'nord').
        fallback_to_default: bool
            Whether to return default theme when not found. Defaults to False.

        Returns
        --------
            NeuriTheme | None: optional NeuriTheme instance
                Matching theme model or default fallback if requested.
        """
        clean_name: str = name.lower().replace("-", "_").strip()
        path: Path | None = PathResolver.resolve_theme_path(
            clean_name, workspace_dir=self._workspace_dir
        )
        if path is not None:
            loaded: NeuriTheme | None = self.load_theme_from_file(path)
            if loaded is not None:
                return loaded

        available: list[NeuriTheme] = self.list_available_themes()
        for t in available:
            if t.name.lower().replace("-", "_") == clean_name:
                return t

        if fallback_to_default:
            fallback_theme: NeuriTheme = self.get_high_contrast_theme()
            return fallback_theme

        return None

    def get_high_contrast_theme(self) -> NeuriTheme:
        """Return canonical VS Code style high contrast black-and-white theme.

        Parameters
        ------------
        None

        Returns
        --------
            NeuriTheme: NeuriTheme instance
                High contrast theme model.
        """
        hc_theme: NeuriTheme = NeuriTheme(
            name="high_contrast",
            display_name="High Contrast",
            description=(
                "Pure black background with crisp white text and borders "
                "(VS Code style)"
            ),
            background="#000000",
            foreground="#ffffff",
            surface="#000000",
            panel="#000000",
            border="#ffffff",
            primary="#ffffff",
            secondary="#ffffff",
            accent="#00ffff",
            warning="#ffea00",
            error="#ff0055",
            success="#00ff66",
            dark=True,
        )
        return hc_theme

    def get_active_theme_name(self) -> str:
        """Read active theme name from project or global config.toml.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Active theme name (defaults to 'high_contrast').
        """
        config_paths: list[Path] = []
        if self._workspace_dir is not None:
            config_paths.append(self._workspace_dir / ".neuri" / "config.toml")
        config_paths.append(Path.home() / ".neuri" / "config.toml")

        for cfg_path in config_paths:
            if cfg_path.is_file():
                try:
                    data: dict[str, Any] = tomllib.loads(
                        cfg_path.read_text(encoding="utf-8")
                    )
                    theme_val: Any = data.get("project", {}).get(
                        "theme"
                    ) or data.get("ui", {}).get("theme") or data.get("theme")
                    if isinstance(theme_val, str) and theme_val.strip():
                        return theme_val.strip()
                except Exception:
                    pass

        return self.DEFAULT_THEME_NAME

    def set_active_theme(self, theme_name: str) -> bool:
        """Save selected theme name into ~/.neuri/config.toml.

        Parameters
        ------------
        theme_name: str
            Theme name to persist.

        Returns
        --------
            bool: boolean object
                True if configuration was updated successfully.
        """
        clean_name: str = theme_name.lower().replace("-", "_").strip()
        target_file: Path = Path.home() / ".neuri" / "config.toml"
        target_file.parent.mkdir(parents=True, exist_ok=True)

        existing: dict[str, Any] = {}
        if target_file.is_file():
            try:
                existing = tomllib.loads(
                    target_file.read_text(encoding="utf-8")
                )
            except Exception:
                existing = {}

        if "project" not in existing:
            existing["project"] = {}
        existing["project"]["theme"] = clean_name

        try:
            with open(target_file, "wb") as fh:
                tomli_w.dump(existing, fh)

            if self._workspace_dir is not None:
                local_cfg: Path = (
                    self._workspace_dir / ".neuri" / "config.toml"
                )
                if local_cfg.is_file():
                    try:
                        local_data: dict[str, Any] = tomllib.loads(
                            local_cfg.read_text(encoding="utf-8")
                        )
                        if "project" not in local_data:
                            local_data["project"] = {}
                        local_data["project"]["theme"] = clean_name
                        with open(local_cfg, "wb") as lfh:
                            tomli_w.dump(local_data, lfh)
                    except Exception:
                        pass
            return True
        except Exception:
            return False


__all__: list[str] = [
    "NeuriTheme",
    "NeuriThemeManager",
]
