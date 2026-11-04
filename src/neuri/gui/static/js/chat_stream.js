/**
 * Neuri Studio — Chat & Execution Stream Controller
 * Renders user turns, live streaming cards, tool badges, and shell results.
 */

export class ChatStream {
  constructor() {
    this.container = document.getElementById("chat-scroll");
    this.currentLiveCard = null;
    this.currentThinkingBody = null;
    this.currentContentBody = null;
  }

  init(turns, workspaceDir) {
    if (!this.container) return;
    this.container.innerHTML = "";
    this.renderWelcomeCard(workspaceDir);

    if (Array.isArray(turns) && turns.length > 0) {
      turns.forEach((t) => this.renderTurn(t));
      this.scrollToBottom();
    }
  }

  renderWelcomeCard(workspaceDir) {
    const card = document.createElement("div");
    card.className = "message-card";
    card.style.borderLeft = "4px solid var(--neuri-primary)";
    card.innerHTML = `
      <div class="card-header">
        <span class="card-role-assistant">&gt;&gt; NEURI - Neuroscience Meta-Harness</span>
        <span class="card-time">Workspace: ${workspaceDir || "Active"}</span>
      </div>
      <div class="card-body">
        <p style="margin-bottom: 8px;">Adaptive multi-modal research cockpit. Execute prompts, inspect DAG workflows, stream 3D neuroimaging, and control compute fleets.</p>
        <table class="welcome-table">
          <thead>
            <tr>
              <th>Modality</th>
              <th>Quick Action</th>
              <th>Command</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Natural Language</td>
              <td>Decompose & execute research DAG</td>
              <td><em>Enter any instruction below</em></td>
            </tr>
            <tr>
              <td><button class="welcome-action-pill" data-tab="dag" style="background:var(--neuri-surface); border:1px solid var(--neuri-border); color:var(--neuri-primary); border-radius:4px; padding:2px 8px; cursor:pointer; font-weight:600;">🕸️ DAG Flow</button></td>
              <td>Preview execution plan without running</td>
              <td><span class="welcome-cmd" data-cmd="/plan ">/plan &lt;instruction&gt;</span></td>
            </tr>
            <tr>
              <td><button class="welcome-action-pill" data-tab="niivue" style="background:var(--neuri-surface); border:1px solid var(--neuri-border); color:var(--neuri-accent); border-radius:4px; padding:2px 8px; cursor:pointer; font-weight:600;">🧠 3D Visualization</button></td>
              <td>Inspect NIfTI / GIfTI in WebGL2</td>
              <td><span class="welcome-cmd" data-cmd="/view " data-tab="niivue">/view [path]</span></td>
            </tr>
            <tr>
              <td>Status & Jobs</td>
              <td>Inspect nodes, artifacts, and batch queues</td>
              <td><span class="welcome-cmd" data-cmd="/status">/status</span> or <span class="welcome-cmd" data-cmd="/jobs">/jobs</span></td>
            </tr>
            <tr>
              <td>Fleet Shell</td>
              <td>Run bash command locally or on cluster</td>
              <td><span class="welcome-cmd" data-cmd="!ls -la">!&lt;cmd&gt;</span> or <strong>Ctrl+S</strong></td>
            </tr>
            <tr>
              <td>Command Help</td>
              <td>List all interactive slash commands</td>
              <td><span class="welcome-cmd" data-cmd="/help">/help</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    `;

    // Click handler for quick action pills (switches tab directly)
    card.querySelectorAll(".welcome-action-pill").forEach((el) => {
      el.addEventListener("click", () => {
        const tab = el.getAttribute("data-tab");
        if (tab && window.__neuriApp && window.__neuriApp.studioTabs) {
          window.__neuriApp.studioTabs.switchTab(tab);
        }
      });
    });

    // Click handler for quick action commands
    card.querySelectorAll(".welcome-cmd").forEach((el) => {
      el.addEventListener("click", () => {
        const cmd = el.getAttribute("data-cmd");
        const tab = el.getAttribute("data-tab");
        if (tab && window.__neuriApp && window.__neuriApp.studioTabs) {
          window.__neuriApp.studioTabs.switchTab(tab);
        }
        const promptInput = document.getElementById("prompt-input");
        if (promptInput) {
          promptInput.value = cmd;
          promptInput.focus();
        }
      });
    });

    this.container.appendChild(card);
  }

  renderTurn(turn) {
    const card = document.createElement("div");
    const role = (turn.role || "assistant").toLowerCase();
    const timeStr = turn.timestamp ? new Date(turn.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();

    card.className = `message-card message-card-${role === "user" ? "user" : "assistant"}`;

    let headerHtml = "";
    if (role === "user") {
      headerHtml = `
        <div class="card-header">
          <span class="card-role-user">&rsaquo; you</span>
          <span class="card-time">${timeStr}</span>
        </div>`;
    } else {
      const label = turn.node_id ? `specialist &middot; ${turn.node_id}` : "neuri";
      headerHtml = `
        <div class="card-header">
          <span class="card-role-assistant">&gt;&gt; ${label}</span>
          <span class="card-time">${timeStr}</span>
        </div>`;
    }

    let thinkingHtml = "";
    if (turn.thinking_trace) {
      thinkingHtml = `
        <div class="reasoning-drawer">
          <div class="reasoning-header">&blacktriangleright; reasoning trace</div>
          <div class="reasoning-body" style="display:none;">${this.escapeHtml(turn.thinking_trace)}</div>
        </div>`;
    }

    const contentHtml = `<div class="card-body">${this.renderMarkdown(turn.content)}</div>`;
    card.innerHTML = headerHtml + thinkingHtml + contentHtml;

    // Toggle reasoning drawer
    const rHeader = card.querySelector(".reasoning-header");
    if (rHeader) {
      rHeader.addEventListener("click", () => {
        const body = card.querySelector(".reasoning-body");
        if (body) {
          const isOpen = body.style.display !== "none";
          body.style.display = isOpen ? "none" : "block";
          rHeader.innerHTML = isOpen ? "&blacktriangleright; reasoning trace" : "&blacktriangledown; reasoning trace";
        }
      });
    }

    this.container.appendChild(card);
  }

  appendUserMessage(text) {
    this.renderTurn({ role: "user", content: text, timestamp: new Date().toISOString() });
    this.scrollToBottom();
  }

  createLiveCard(nodeId) {
    this.finalizeLiveCard();
    const card = document.createElement("div");
    card.className = "message-card message-card-assistant";
    const timeStr = new Date().toLocaleTimeString();
    const label = nodeId ? `specialist &middot; ${nodeId}` : "neuri";

    card.innerHTML = `
      <div class="card-header">
        <span class="card-role-assistant">&gt;&gt; ${label} (live)</span>
        <span class="card-time">${timeStr}</span>
      </div>
      <div class="live-tools-container"></div>
      <div class="reasoning-drawer" style="display:none;">
        <div class="reasoning-header">&blacktriangledown; reasoning trace</div>
        <div class="reasoning-body"></div>
      </div>
      <div class="card-body live-body-content"></div>
    `;

    this.container.appendChild(card);
    this.currentLiveCard = card;
    this.currentThinkingBody = card.querySelector(".reasoning-body");
    this.currentContentBody = card.querySelector(".live-body-content");
    this.scrollToBottom();
  }

  appendThinkingDelta(delta) {
    if (!this.currentLiveCard) {
      this.createLiveCard();
    }
    const drawer = this.currentLiveCard.querySelector(".reasoning-drawer");
    if (drawer) drawer.style.display = "block";
    if (this.currentThinkingBody) {
      this.currentThinkingBody.textContent += delta;
      this.scrollToBottom();
    }
  }

  appendContentDelta(delta) {
    if (!this.currentLiveCard) {
      this.createLiveCard();
    }
    if (this.currentContentBody) {
      this.currentContentBody.textContent += delta;
      this.scrollToBottom();
    }
  }

  appendToolCallBadge(toolInfo) {
    if (!this.currentLiveCard) {
      this.createLiveCard();
    }
    const toolsBox = this.currentLiveCard.querySelector(".live-tools-container");
    if (toolsBox) {
      const badge = document.createElement("div");
      badge.className = "tool-badge";
      const host = toolInfo.tool_host || "localhost";
      const status = toolInfo.tool_status || "running";
      const duration = toolInfo.duration_ms ? `${toolInfo.duration_ms}ms` : "";
      badge.innerHTML = `<span>&#9881; ${this.escapeHtml(toolInfo.tool_name)}</span> &middot; <span style="color:var(--neuri-muted)">${host}</span> &middot; <span style="color:var(--neuri-primary)">${status}</span> ${duration}`;
      toolsBox.appendChild(badge);
      this.scrollToBottom();
    }
  }

  finalizeLiveCard(finalText) {
    if (this.currentLiveCard && this.currentContentBody) {
      const rawText = finalText || this.currentContentBody.textContent;
      this.currentContentBody.innerHTML = this.renderMarkdown(rawText);
    }
    this.currentLiveCard = null;
    this.currentThinkingBody = null;
    this.currentContentBody = null;
    this.scrollToBottom();
  }

  scrollToBottom() {
    if (this.container) {
      this.container.scrollTop = this.container.scrollHeight;
    }
  }

  escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  renderMarkdown(text) {
    if (!text) return "";
    let html = this.escapeHtml(text);

    // Code blocks ```code```
    html = html.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
      return `<pre><code class="language-${lang}">${code}</code></pre>`;
    });

    // Inline code `code`
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3 style="color:var(--neuri-primary); margin:8px 0 4px 0; font-size:1.05rem;">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 style="color:var(--neuri-primary); margin:10px 0 6px 0; font-size:1.15rem;">$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1 style="color:var(--neuri-primary); margin:12px 0 8px 0; font-size:1.25rem;">$1</h1>');

    // Bold & italic
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");

    // Markdown tables
    html = html.replace(/((?:\|[^\n]+\|\r?\n)+)/g, (tableMatch) => {
      const rows = tableMatch.trim().split("\n");
      if (rows.length < 2) return tableMatch;
      let tableHtml = '<table class="welcome-table" style="margin:8px 0;">';
      rows.forEach((r, idx) => {
        if (r.includes("---")) return; // divider
        const cols = r.split("|").filter((c, i, a) => i > 0 && i < a.length - 1);
        tableHtml += "<tr>";
        cols.forEach((c) => {
          const tag = idx === 0 ? "th" : "td";
          tableHtml += `<${tag}>${c.trim()}</${tag}>`;
        });
        tableHtml += "</tr>";
      });
      tableHtml += "</table>";
      return tableHtml;
    });

    // Bullet points
    html = html.replace(/^\s*-\s+(.*$)/gim, '<li style="margin-left:18px;">$1</li>');

    // Line breaks to <br> outside <pre>
    const parts = html.split(/(<pre[\s\S]*?<\/pre>|<table[\s\S]*?<\/table>)/g);
    for (let i = 0; i < parts.length; i += 2) {
      parts[i] = parts[i].replace(/\n/g, "<br>");
    }
    return parts.join("");
  }
}
