/**
 * Neuri Studio — Theme Engine
 * Synchronizes NeuriTheme TOML tokens with DOM CSS Custom Properties.
 */

export class ThemeEngine {
  constructor() {
    this.activeTheme = "dark";
    this.themes = [];
    this.themeSelectEl = document.getElementById("header-theme-select");
    this.themeBtnEl = document.getElementById("theme-toggle-btn");
  }

  async init() {
    if (this.themeBtnEl) {
      this.themeBtnEl.addEventListener("click", () => {
        this.cycleTheme();
      });
    }

    if (this.themeSelectEl) {
      this.themeSelectEl.addEventListener("change", (e) => {
        this.setTheme(e.target.value);
      });
    }

    await this.fetchThemes();
  }

  async fetchThemes() {
    try {
      const res = await fetch("/api/v1/themes");
      if (!res.ok) return;
      const data = await res.json();
      this.themes = data.themes || [];
      this.activeTheme = data.active_theme || "dark";
      this.populateSelect();

      const current = this.themes.find((t) => t.name === this.activeTheme);
      if (current && current.css_variables) {
        this.applyCssVariables(current.css_variables);
      }
    } catch (err) {
      console.warn("Failed to load themes:", err);
    }
  }

  populateSelect() {
    if (!this.themeSelectEl) return;
    this.themeSelectEl.innerHTML = "";
    this.themes.forEach((t) => {
      const opt = document.createElement("option");
      opt.value = t.name;
      opt.textContent = t.display_name || t.name;
      if (t.name === this.activeTheme) {
        opt.selected = true;
      }
      this.themeSelectEl.appendChild(opt);
    });
  }

  applyCssVariables(vars) {
    if (!vars) return;
    const root = document.documentElement;
    Object.entries(vars).forEach(([key, val]) => {
      root.style.setProperty(key, val);
    });
    // Set color-scheme if dark property is available
    if (vars["--neuri-dark"] === "true") {
      root.style.colorScheme = "dark";
    } else if (vars["--neuri-dark"] === "false") {
      root.style.colorScheme = "light";
    }
  }

  cycleTheme() {
    if (!this.themes || this.themes.length === 0) return;
    const currentIdx = this.themes.findIndex((t) => t.name === this.activeTheme);
    const nextIdx = (currentIdx + 1) % this.themes.length;
    const nextTheme = this.themes[nextIdx];
    this.setTheme(nextTheme.name);
    if (this.themeSelectEl) {
      this.themeSelectEl.value = nextTheme.name;
    }
  }

  async setTheme(themeName) {
    // 1. Optimistic apply so UI changes instantly
    this.activeTheme = themeName;
    const target = this.themes.find((t) => t.name === themeName);
    if (target && target.css_variables) {
      this.applyCssVariables(target.css_variables);
    }
    if (this.themeSelectEl) {
      this.themeSelectEl.value = themeName;
    }

    // 2. Persist to server
    try {
      const res = await fetch("/api/v1/themes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ theme: themeName }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.theme && data.theme.css_variables) {
          this.applyCssVariables(data.theme.css_variables);
        }
      }
    } catch (err) {
      console.error("Error setting theme:", err);
    }
  }
}
