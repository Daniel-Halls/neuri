"""Color theme data model, TOML loader, and manager for Neuri TUI.

Provides oh-my-zsh style color themes stored in $HOME/.neuri/themes/,
including cyberpunk, high-contrast, dark, monokai, and nord, with dynamic
switching and config persistence.

Design rule: no colour literals live in this module or in any widget code.
Every colour comes from a theme TOML file. When a theme omits a token it is
derived from a sibling token in the same theme, and as an absolute last
resort from Textual's own built-in ``textual-dark`` theme.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import tomli_w
from rich.color import Color
from textual.theme import BUILTIN_THEMES, Theme

from neuri.core.paths import PathResolver


def reference_palette() -> dict[str, str]:
    """Return the generated colour map of Textual's built-in dark theme.

    Used only when a theme file is missing a required base token, so that
    no colour literal needs to be written in Neuri's own source code.

    Parameters
    ------------
    None

    Returns
    --------
        dict[str, str]: dict object
            Mapping of Textual design token names to colour strings.
    """
    ref_theme: Theme = BUILTIN_THEMES[NeuriTheme.REFERENCE_THEME_NAME]
    palette: dict[str, str] = ref_theme.to_color_system().generate()
    return palette


def normalize_color(color_val: str, fallback: str = "") -> str:
    """Normalize and sanitize color string for Rich and Textual compatibility.

    Expands 3-digit hex (#RGB) to 6-digit hex (#RRGGBB), strips alpha from
    4-digit (#RGBA) and 8-digit (#RRGGBBAA) hex strings, and validates
    with Rich's Color parser. Falls back to default if color is invalid.

    Parameters
    ------------
    color_val: str
        Raw color string from theme configuration or template.
    fallback: str
        Value returned when the colour is invalid. Defaults to "" which
        signals "unset" so the theme can derive the token itself.

    Returns
    --------
        str: string object
            Sanitized, validated Rich-compatible color string.
    """
    if not isinstance(color_val, str) or not color_val.strip():
        return fallback

    cleaned: str = color_val.strip()
    if cleaned.startswith("#"):
        hex_digits: str = cleaned[1:]
        # 3-digit hex #RGB or 4-digit hex #RGBA -> #RRGGBB (discard alpha)
        if len(hex_digits) in (3, 4):
            cleaned = f"#{hex_digits[0]*2}{hex_digits[1]*2}{hex_digits[2]*2}"
        # 8-digit hex #RRGGBBAA -> #RRGGBB (discard alpha)
        elif len(hex_digits) == 8:
            cleaned = f"#{hex_digits[:6]}"

    try:
        Color.parse(cleaned)
        result: str = cleaned
    except Exception:
        result = fallback

    return result


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
    muted: str
        Muted text color for idle or offline items. Defaults to "" which
        derives the value from ``secondary``.
    selection_bg: str
        Active selection background color. Defaults to "" (``surface``).
    selection_fg: str
        Active selection foreground color. Defaults to "" (``foreground``).
    tokens: str
        Token count tally color. Defaults to "" (``warning``).
    cost: str
        Monetary cost counter color. Defaults to "" (``secondary``).
    surface_elevated: str
        Raised surface colour for pills and popups. Defaults to ""
        (``surface``).
    dark: bool
        Whether theme is a dark variant. Defaults to True.

    Returns
    --------
        NeuriTheme: NeuriTheme instance
            Constructed theme data model.
    """

    REFERENCE_THEME_NAME: ClassVar[str] = "textual-dark"

    # Order matters: each token is derived from tokens resolved before it.
    # A leading "@" means "take it from the Textual reference palette".
    TOKEN_DERIVATIONS: ClassVar[tuple[tuple[str, str], ...]] = (
        ("background", "@background"),
        ("foreground", "@foreground"),
        ("surface", "background"),
        ("panel", "background"),
        ("border", "foreground"),
        ("primary", "foreground"),
        ("secondary", "foreground"),
        ("accent", "primary"),
        ("warning", "@warning"),
        ("error", "@error"),
        ("success", "@success"),
        ("muted", "secondary"),
        ("selection_bg", "surface"),
        ("selection_fg", "foreground"),
        ("tokens", "warning"),
        ("cost", "secondary"),
        ("surface_elevated", "surface"),
    )

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
    warning: str = ""
    error: str = ""
    success: str = ""
    muted: str = ""
    selection_bg: str = ""
    selection_fg: str = ""
    tokens: str = ""
    cost: str = ""
    surface_elevated: str = ""
    dark: bool = True

    def __post_init__(self) -> None:
        """Sanitize colours and derive any unset tokens from sibling tokens.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Normalizes color attributes in-place.
        """
        reference: dict[str, str] | None = None
        for attr, source in self.TOKEN_DERIVATIONS:
            val: str = normalize_color(getattr(self, attr, ""))
            if not val:
                if source.startswith("@"):
                    if reference is None:
                        reference = reference_palette()
                    val = normalize_color(reference.get(source[1:], ""))
                else:
                    val = str(getattr(self, source))
            object.__setattr__(self, attr, val)

    def widget_variables(self) -> dict[str, str]:
        """Map Neuri tokens onto Textual's built-in widget design variables.

        This keeps stock Textual widgets (Footer, Input, Markdown, scrollbars)
        consistent with the active Neuri palette instead of Textual defaults.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, str]: dict object
                Textual design variable overrides derived from this theme.
        """
        variables: dict[str, str] = {
            "border": self.border,
            "border-blurred": self.border,
            "muted": self.muted,
            "selection-bg": self.selection_bg,
            "selection-fg": self.selection_fg,
            "tokens": self.tokens,
            "cost": self.cost,
            "surface-elevated": self.surface_elevated,
            "footer-background": self.background,
            "footer-foreground": self.foreground,
            "footer-key-foreground": self.primary,
            "footer-key-background": self.background,
            "footer-description-foreground": self.foreground,
            "footer-description-background": self.background,
            "footer-item-background": self.background,
            "input-cursor-background": self.primary,
            "input-cursor-foreground": self.background,
            "input-selection-background": self.selection_bg,
            "input-selection-foreground": self.selection_fg,
            "block-cursor-background": self.selection_bg,
            "block-cursor-foreground": self.selection_fg,
            "scrollbar": self.border,
            "scrollbar-hover": self.secondary,
            "scrollbar-active": self.primary,
            "scrollbar-background": self.background,
            "scrollbar-background-hover": self.background,
            "scrollbar-background-active": self.background,
            "scrollbar-corner-color": self.background,
            "markdown-h1-color": self.primary,
            "markdown-h2-color": self.primary,
            "markdown-h3-color": self.primary,
            "markdown-h4-color": self.secondary,
            "markdown-h5-color": self.secondary,
            "markdown-h6-color": self.muted,
        }
        return variables

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
            variables=self.widget_variables(),
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

    DEFAULT_THEME_NAME: str = "dark"

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

            # Unset tokens are passed as "" and derived by NeuriTheme itself.
            color_values: dict[str, str] = {
                attr: str(theme_dict.get(attr, ""))
                for attr, _ in NeuriTheme.TOKEN_DERIVATIONS
            }

            loaded_theme: NeuriTheme = NeuriTheme(
                name=str(theme_dict.get("name", path.stem)),
                display_name=str(
                    theme_dict.get(
                        "display_name", path.stem.replace("_", " ").title()
                    )
                ),
                description=str(
                    theme_dict.get("description", "Custom Neuri color theme.")
                ),
                dark=bool(theme_dict.get("dark", True)),
                **color_values,
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
            fallback: NeuriTheme = self.get_reference_theme()
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
            fallback_theme: NeuriTheme = self.get_default_theme()
            return fallback_theme

        return None

    def get_reference_theme(self) -> NeuriTheme:
        """Return a last-resort theme derived purely from Textual's palette.

        Every colour token is left unset so ``NeuriTheme`` derives it from
        Textual's built-in reference theme. Used only when no theme TOML
        files can be found anywhere on disk.

        Parameters
        ------------
        None

        Returns
        --------
            NeuriTheme: NeuriTheme instance
                Fully derived fallback theme.
        """
        unset: dict[str, str] = {
            attr: "" for attr, _ in NeuriTheme.TOKEN_DERIVATIONS
        }
        ref_theme: NeuriTheme = NeuriTheme(
            name=NeuriTheme.REFERENCE_THEME_NAME.replace("-", "_"),
            display_name="Textual Reference",
            description="Fallback palette derived from Textual defaults.",
            dark=True,
            **unset,
        )
        return ref_theme

    def _load_named_theme(self, name: str) -> NeuriTheme:
        """Load a named theme TOML, falling back to the reference theme.

        Parameters
        ------------
        name: str
            Theme file stem (e.g. 'dark', 'high_contrast').

        Returns
        --------
            NeuriTheme: NeuriTheme instance
                Loaded theme, or the reference theme if the file is missing.
        """
        path: Path | None = PathResolver.resolve_theme_path(
            name, workspace_dir=self._workspace_dir
        )
        loaded: NeuriTheme | None = (
            self.load_theme_from_file(path) if path is not None else None
        )
        if loaded is None:
            return self.get_reference_theme()
        return loaded

    def get_default_theme(self) -> NeuriTheme:
        """Return the Neuri default theme (``DEFAULT_THEME_NAME``).

        Parameters
        ------------
        None

        Returns
        --------
            NeuriTheme: NeuriTheme instance
                Default theme model loaded from its TOML file.
        """
        default_thm: NeuriTheme = self._load_named_theme(
            self.DEFAULT_THEME_NAME
        )
        return default_thm

    def get_dark_theme(self) -> NeuriTheme:
        """Return Obsidian Neuro signature dark theme from ``dark.toml``.

        Parameters
        ------------
        None

        Returns
        --------
            NeuriTheme: NeuriTheme instance
                Obsidian Neuro theme model.
        """
        dark_thm: NeuriTheme = self._load_named_theme("dark")
        return dark_thm

    def get_high_contrast_theme(self) -> NeuriTheme:
        """Return the high contrast theme from ``high_contrast.toml``.

        Parameters
        ------------
        None

        Returns
        --------
            NeuriTheme: NeuriTheme instance
                High contrast theme model.
        """
        hc_theme: NeuriTheme = self._load_named_theme("high_contrast")
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
