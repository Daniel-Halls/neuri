/**
 * Neuri Studio — Master Application Coordinator
 * Connects SSE event stream, routes keyboard shortcuts, and orchestrates panels.
 */

import { ThemeEngine } from "./theme_engine.js";
import { ChatStream } from "./chat_stream.js";
import { DagCanvas } from "./dag_canvas.js";
import { FleetPanel } from "./fleet_panel.js";
import { NiiVuePanel } from "./niivue_panel.js";
import { StudioTabs } from "./studio_tabs.js";

export class NeuriApp {
  constructor() {
    this.themeEngine = new ThemeEngine();
    this.chatStream = new ChatStream();
    this.dagCanvas = new DagCanvas();
    this.fleetPanel = new FleetPanel();
    this.niivuePanel = new NiiVuePanel();
    this.studioTabs = new StudioTabs();

    this.isShellMode = false;
    this.tokensCount = 0;
    this.costUsd = 0.0;
    this.historyEntries = [];
    this.historyIndex = -1;
    this.slashCommands = [];

    this.promptInput = document.getElementById("prompt-input");
    this.sendBtn = document.getElementById("send-btn");
    this.autocompletePopup = document.getElementById("autocomplete-popup");
    this.selectedAutocompleteIdx = 0;
    this.matchingCommands = [];
  }

  async init() {
    window.__neuriApp = this;
    await this.themeEngine.init();
    this.studioTabs.init();
    this.dagCanvas.init();
    this.fleetPanel.init();
    this.niivuePanel.init();

    await this.fetchInitialState();
    await this.fetchIntrospection();
    this.connectEventStream();
    this.bindEvents();
  }

  async fetchInitialState() {
    try {
      const res = await fetch("/api/v1/state");
      if (!res.ok) return;
      const state = await res.json();

      // Populate header info
      const wsName = document.getElementById("header-workspace-name");
      if (wsName) wsName.textContent = state.workspace_name || state.workspace_dir;

      const harnessSelect = document.getElementById("header-harness-select");
      if (harnessSelect && state.harness) harnessSelect.value = state.harness;

      const modelSelect = document.getElementById("header-model-select");
      if (modelSelect && state.model) modelSelect.value = state.model;

      // Initialize chat turns
      this.chatStream.init(state.turns, state.workspace_name || state.workspace_dir);

      // Fetch history entries
      const histRes = await fetch("/api/v1/history");
      if (histRes.ok) {
        const hData = await histRes.json();
        this.historyEntries = hData.entries || [];
      }
    } catch (err) {
      console.warn("Error loading state:", err);
    }
  }

  async fetchIntrospection() {
    try {
      const res = await fetch("/api/v1/introspect");
      if (!res.ok) return;
      const data = await res.json();
      this.slashCommands = data.slash_commands || [];

      // Populate models in header
      const modelSelect = document.getElementById("header-model-select");
      const harnessInfo = data.harnesses_info;
      this.harnessInfo = harnessInfo;
      if (modelSelect && harnessInfo && harnessInfo.models_by_harness) {
        const activeHarness = harnessInfo.active_harness || "agy";
        const models = harnessInfo.models_by_harness[activeHarness] || ["default"];
        modelSelect.innerHTML = "";
        models.forEach((m) => {
          const opt = document.createElement("option");
          opt.value = m;
          opt.textContent = m;
          if (m === harnessInfo.active_model) opt.selected = true;
          modelSelect.appendChild(opt);
        });
      }
    } catch (err) {
      console.warn("Introspection fetch error:", err);
    }
  }

  connectEventStream() {
    const es = new EventSource("/api/v1/events");

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handleSessionEvent(data);
      } catch (e) {}
    };

    es.onerror = () => {
      // Automatic reconnect handled by EventSource
    };
  }

  handleSessionEvent(data) {
    const type = (data.event_type || "").toUpperCase();
    const p = data.payload || {};

    if (type === "ASSISTANT_CHUNK") {
      this.chatStream.appendContentDelta(p.content_delta);
      this.setStatus("STREAMING", "running");
    } else if (type === "THINKING_CHUNK") {
      this.chatStream.appendThinkingDelta(p.thinking_delta);
      this.setStatus("THINKING", "warning");
    } else if (type === "TOOL_CALL_UPDATE") {
      this.chatStream.appendToolCallBadge(p);
    } else if (type === "STATUS_UPDATE") {
      if (p.action === "token_increment") {
        this.updateTelemetry(p.tokens || 0, p.cost_usd || 0.0);
      } else if (p.action === "change_theme" && p.theme && p.theme.css_variables) {
        this.themeEngine.applyCssVariables(p.theme.css_variables);
      }
    } else if (type === "WORKFLOW_COMPLETED") {
      this.chatStream.finalizeLiveCard();
      this.dagCanvas.fetchDag();
      this.setStatus("READY", "ready");
      if (p.total_tokens) this.updateTelemetry(p.total_tokens, p.cost_usd || 0.0, true);
    } else if (type === "CIRCUIT_BREAKER_TRIGGERED") {
      this.setStatus("CIRCUIT BREAKER", "error");
      this.chatStream.appendContentDelta(`\n\n> **[!] Circuit Breaker Triggered:** ${p.reason || "Paused for operator input"}`);
    }
  }

  updateTelemetry(tokens, cost, isAbsolute = false) {
    if (isAbsolute) {
      this.tokensCount = tokens;
      this.costUsd = cost;
    } else {
      this.tokensCount += tokens;
      this.costUsd += cost;
    }
    const tEl = document.getElementById("telemetry-tokens");
    const cEl = document.getElementById("telemetry-cost");
    if (tEl) tEl.textContent = `${this.tokensCount.toLocaleString()} / 64,000`;
    if (cEl) cEl.textContent = `$${this.costUsd.toFixed(2)}`;
  }

  setStatus(text, styleClass) {
    const sEl = document.getElementById("telemetry-status");
    if (sEl) {
      sEl.textContent = text;
      sEl.className = `status-badge status-${styleClass}`;
    }
  }

  bindEvents() {
    if (this.sendBtn) {
      this.sendBtn.addEventListener("click", () => this.submitPrompt());
    }

    if (this.promptInput) {
      this.promptInput.addEventListener("keydown", (e) => this.handlePromptKey(e));
      this.promptInput.addEventListener("input", () => this.handlePromptInput());
    }

    // Cross-frame message bus from embedded NiiVue visualizer
    window.addEventListener("message", (event) => {
      if (!event.data) return;
      if (event.data.type === "NEURI_ATTACH_COORDS") {
        if (this.promptInput) {
          const coordText = event.data.text || "";
          this.promptInput.value += coordText;
          this.promptInput.focus();
        }
      }
    });

    // Activity Rail Clicks
    document.querySelectorAll(".rail-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = btn.getAttribute("data-target");
        if (target) this.studioTabs.switchTab(target);
      });
    });

    // Global Keybindings (F2, F3, Ctrl+S, Ctrl+L, Cmd+K)
    window.addEventListener("keydown", (e) => {
      if (e.key === "F2") {
        e.preventDefault();
        this.studioTabs.switchTab("fleet");
      } else if (e.key === "F3") {
        e.preventDefault();
        this.studioTabs.switchTab("dag");
      } else if (e.ctrlKey && e.key.toLowerCase() === "s") {
        e.preventDefault();
        this.toggleShellMode();
      } else if (e.ctrlKey && e.key.toLowerCase() === "l") {
        e.preventDefault();
        if (this.promptInput) {
          this.promptInput.value = "/clear";
          this.submitPrompt();
        }
      } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (this.promptInput) {
          this.promptInput.value = "/";
          this.promptInput.focus();
          this.handlePromptInput();
        }
      }
    });

    // Harness Dropdown change
    const harnessSelect = document.getElementById("header-harness-select");
    if (harnessSelect) {
      harnessSelect.addEventListener("change", async (e) => {
        const h = e.target.value;
        this.setStatus("UPDATING HARNESS", "warning");
        try {
          const res = await fetch("/api/v1/input", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: `/harness ${h}` }),
          });
          if (res.ok) {
            const turn = await res.json();
            this.chatStream.renderTurn(turn);
            this.setStatus("READY", "ready");
            this.updateModelDropdown(h);
          }
        } catch (err) {
          console.warn("Failed to switch harness:", err);
          this.setStatus("READY", "ready");
        }
      });
    }

    // Model Dropdown change
    const modelSelect = document.getElementById("header-model-select");
    if (modelSelect) {
      modelSelect.addEventListener("change", async (e) => {
        const m = e.target.value;
        try {
          const res = await fetch("/api/v1/input", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: `/model ${m}` }),
          });
          if (res.ok) {
            const turn = await res.json();
            this.chatStream.renderTurn(turn);
          }
        } catch (err) {
          console.warn("Failed to switch model:", err);
        }
      });
    }
  }

  updateModelDropdown(harness) {
    const modelSelect = document.getElementById("header-model-select");
    if (!modelSelect || !this.harnessInfo || !this.harnessInfo.models_by_harness) return;
    const models = this.harnessInfo.models_by_harness[harness] || ["default"];
    modelSelect.innerHTML = "";
    models.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      modelSelect.appendChild(opt);
    });
  }

  handlePromptKey(e) {
    // Autocomplete Navigation
    if (this.autocompletePopup && this.autocompletePopup.style.display !== "none") {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        this.selectNextAutocomplete();
        return;
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        this.selectPrevAutocomplete();
        return;
      } else if (e.key === "Tab" || e.key === "Enter") {
        e.preventDefault();
        this.acceptAutocomplete();
        return;
      } else if (e.key === "Escape") {
        this.hideAutocomplete();
        return;
      }
    }

    // Tab in Shell Mode -> Cycle target machines
    if (this.isShellMode && e.key === "Tab") {
      e.preventDefault();
      if (e.shiftKey) {
        this.fleetPanel.prevMachine();
      } else {
        this.fleetPanel.nextMachine();
      }
      return;
    }

    // Up / Down arrow bash history navigation
    if (e.key === "ArrowUp" && !this.promptInput.value) {
      e.preventDefault();
      if (this.historyEntries.length > 0) {
        this.historyIndex = Math.min(this.historyIndex + 1, this.historyEntries.length - 1);
        this.promptInput.value = this.historyEntries[this.historyEntries.length - 1 - this.historyIndex];
      }
      return;
    } else if (e.key === "ArrowDown" && this.historyIndex >= 0) {
      e.preventDefault();
      this.historyIndex--;
      if (this.historyIndex >= 0) {
        this.promptInput.value = this.historyEntries[this.historyEntries.length - 1 - this.historyIndex];
      } else {
        this.promptInput.value = "";
      }
      return;
    }

    // Enter to submit
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      this.submitPrompt();
    }
  }

  handlePromptInput() {
    const val = this.promptInput.value;
    if (val.startsWith("/") && !val.includes(" ")) {
      const match = val.toLowerCase();
      this.matchingCommands = this.slashCommands.filter((c) => c.command.toLowerCase().startsWith(match));
      if (this.matchingCommands.length > 0) {
        this.showAutocomplete(this.matchingCommands);
      } else {
        this.hideAutocomplete();
      }
    } else {
      this.hideAutocomplete();
    }
  }

  showAutocomplete(commands) {
    if (!this.autocompletePopup) return;
    this.autocompletePopup.innerHTML = "";
    this.selectedAutocompleteIdx = 0;

    commands.forEach((c, idx) => {
      const row = document.createElement("div");
      row.className = `autocomplete-row ${idx === 0 ? "selected" : ""}`;
      row.innerHTML = `<span class="autocomplete-cmd">${c.command}</span><span class="autocomplete-desc">${c.description}</span>`;
      row.addEventListener("click", () => {
        this.selectedAutocompleteIdx = idx;
        this.acceptAutocomplete();
      });
      this.autocompletePopup.appendChild(row);
    });

    this.autocompletePopup.style.display = "block";
  }

  hideAutocomplete() {
    if (this.autocompletePopup) {
      this.autocompletePopup.style.display = "none";
    }
  }

  selectNextAutocomplete() {
    const rows = this.autocompletePopup.querySelectorAll(".autocomplete-row");
    if (rows.length === 0) return;
    rows[this.selectedAutocompleteIdx].classList.remove("selected");
    this.selectedAutocompleteIdx = (this.selectedAutocompleteIdx + 1) % rows.length;
    rows[this.selectedAutocompleteIdx].classList.add("selected");
  }

  selectPrevAutocomplete() {
    const rows = this.autocompletePopup.querySelectorAll(".autocomplete-row");
    if (rows.length === 0) return;
    rows[this.selectedAutocompleteIdx].classList.remove("selected");
    this.selectedAutocompleteIdx = (this.selectedAutocompleteIdx - 1 + rows.length) % rows.length;
    rows[this.selectedAutocompleteIdx].classList.add("selected");
  }

  acceptAutocomplete() {
    if (this.matchingCommands.length > 0 && this.selectedAutocompleteIdx < this.matchingCommands.length) {
      const selected = this.matchingCommands[this.selectedAutocompleteIdx];
      this.promptInput.value = `${selected.command} `;
      this.promptInput.focus();
    }
    this.hideAutocomplete();
  }

  toggleShellMode() {
    this.setShellMode(!this.isShellMode);
  }

  setShellMode(enabled) {
    this.isShellMode = enabled;
    const wrapper = document.querySelector(".prompt-box-wrapper");
    const bar = document.getElementById("machine-selector-bar");

    if (this.isShellMode) {
      if (wrapper) wrapper.classList.add("shell-mode");
      if (bar) bar.classList.add("visible");
      this.setStatus("SHELL", "shell");
      this.promptInput.placeholder = `Run shell command on [${this.fleetPanel.selectedMachine}] (Tab to switch host, Ctrl+S to exit)...`;
    } else {
      if (wrapper) wrapper.classList.remove("shell-mode");
      if (bar) bar.classList.remove("visible");
      this.setStatus("READY", "ready");
      this.promptInput.placeholder = "Type a research prompt, /command, or !<cmd>...";
    }
  }

  async submitPrompt() {
    const text = this.promptInput.value.trim();
    if (!text) return;

    this.promptInput.value = "";
    this.hideAutocomplete();
    this.historyEntries.push(text);
    this.historyIndex = -1;

    // Direct shell command (! prefix or shell mode)
    if (this.isShellMode || text.startsWith("!")) {
      const cleanCmd = text.startsWith("!") ? text.substring(1).trim() : text;
      const host = this.fleetPanel.selectedMachine || "localhost";
      this.chatStream.appendUserMessage(`[${host}] $ ${cleanCmd}`);

      try {
        const res = await fetch("/api/v1/shell", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ command: cleanCmd, host: host }),
        });
        if (res.ok) {
          const turn = await res.json();
          this.chatStream.renderTurn(turn);
        }
      } catch (err) {
        this.chatStream.renderTurn({ role: "assistant", content: `Error running shell: ${err.message}` });
      }
      return;
    }

    // Standard research prompt or slash command
    this.chatStream.appendUserMessage(text);
    this.chatStream.createLiveCard();
    this.setStatus("EXECUTING", "running");

    try {
      const res = await fetch("/api/v1/input", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text }),
      });
      if (res.ok) {
        const turn = await res.json();
        this.chatStream.finalizeLiveCard(turn.content);
        this.setStatus("READY", "ready");
        if (text.startsWith("/view")) {
          this.studioTabs.switchTab("niivue");
          this.niivuePanel.fetchScene();
        } else if (text.startsWith("/plan")) {
          this.studioTabs.switchTab("dag");
          this.dagCanvas.fetchDag();
        }
      } else {
        const errData = await res.json().catch(() => ({}));
        this.chatStream.finalizeLiveCard(`⚠️ Server Error: ${errData.error || res.statusText}`);
        this.setStatus("ERROR", "error");
      }
    } catch (err) {
      this.chatStream.finalizeLiveCard(`Error executing: ${err.message}`);
      this.setStatus("ERROR", "error");
    }
  }
}

// Auto-start NeuriApp when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  const app = new NeuriApp();
  app.init();
});
