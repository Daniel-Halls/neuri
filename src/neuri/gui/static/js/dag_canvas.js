/**
 * Neuri Studio — Interactive Topological DAG Graph Canvas & Editor
 * Visualizes TaskNodes and TaskEdges, supports click-to-edit, and /run triggers.
 */

export class DagCanvas {
  constructor() {
    this.container = document.getElementById("dag-container");
    this.svg = document.getElementById("dag-svg");
    this.inspector = document.getElementById("node-inspector-drawer");
    this.addDrawer = document.getElementById("node-add-drawer");
    this.nodes = [];
    this.edges = [];
    this.selectedNodeId = null;
    this.workflowId = null;
  }

  init() {
    this.bindControls();
    this.fetchDag();
  }

  bindControls() {
    const refreshBtn = document.getElementById("dag-btn-refresh");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => this.fetchDag());
    }

    const addBtn = document.getElementById("dag-btn-add-node");
    if (addBtn) {
      addBtn.addEventListener("click", () => this.openAddDrawer());
    }

    const closeAddDrawer = document.getElementById("add-drawer-close-btn");
    if (closeAddDrawer && this.addDrawer) {
      closeAddDrawer.addEventListener("click", () => {
        this.addDrawer.classList.remove("open");
      });
    }

    const submitAddBtn = document.getElementById("add-node-submit-btn");
    if (submitAddBtn) {
      submitAddBtn.addEventListener("click", () => this.submitAddNode());
    }

    const runBtn = document.getElementById("dag-btn-run");
    if (runBtn) {
      runBtn.addEventListener("click", () => {
        const promptInput = document.getElementById("prompt-input");
        const sendBtn = document.getElementById("send-btn");
        if (promptInput && sendBtn) {
          promptInput.value = "/run";
          sendBtn.click();
        }
      });
    }

    const closeInspector = document.getElementById("inspector-close-btn");
    if (closeInspector && this.inspector) {
      closeInspector.addEventListener("click", () => {
        this.inspector.classList.remove("open");
      });
    }

    const saveNodeBtn = document.getElementById("inspector-save-btn");
    if (saveNodeBtn) {
      saveNodeBtn.addEventListener("click", () => this.saveNodeEdits());
    }
  }

  async fetchDag() {
    try {
      const res = await fetch("/api/v1/dag");
      if (!res.ok) return;
      const data = await res.json();
      this.workflowId = data.workflow_id;
      this.nodes = data.nodes || [];
      this.edges = data.edges || [];
      this.renderGraph();
    } catch (err) {
      console.warn("Failed to fetch DAG:", err);
    }
  }

  renderGraph() {
    if (!this.svg) return;
    this.svg.innerHTML = "";

    if (this.nodes.length === 0) {
      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", "50%");
      text.setAttribute("y", "50%");
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("fill", "var(--neuri-muted)");
      text.setAttribute("font-size", "14");
      text.textContent = "No active DAG planned. Use /plan <instruction> to preview.";
      this.svg.appendChild(text);
      return;
    }

    // Topological layered layout calculation
    const inDegrees = new Map();
    const adj = new Map();
    this.nodes.forEach((n) => {
      inDegrees.set(n.node_id, 0);
      adj.set(n.node_id, []);
    });

    this.edges.forEach((e) => {
      if (inDegrees.has(e.to_node_id)) {
        inDegrees.set(e.to_node_id, (inDegrees.get(e.to_node_id) || 0) + 1);
      }
      if (adj.has(e.from_node_id)) {
        adj.get(e.from_node_id).push(e.to_node_id);
      }
    });

    // Waves assignment
    const waves = [];
    let currentWave = [];
    inDegrees.forEach((deg, id) => {
      if (deg === 0) currentWave.push(id);
    });

    const nodeWave = new Map();
    let waveIdx = 0;
    const remaining = new Map(inDegrees);

    while (currentWave.length > 0) {
      waves.push(currentWave);
      currentWave.forEach((id) => nodeWave.set(id, waveIdx));
      const nextWave = [];

      currentWave.forEach((fromId) => {
        (adj.get(fromId) || []).forEach((toId) => {
          remaining.set(toId, remaining.get(toId) - 1);
          if (remaining.get(toId) === 0) {
            nextWave.push(toId);
          }
        });
      });
      currentWave = nextWave;
      waveIdx++;
    }

    // Layout coordinates
    const nodeWidth = 260;
    const nodeHeight = 64;
    const colSpacing = 360;
    const rowSpacing = 100;
    const paddingX = 40;
    const paddingY = 40;

    const nodeCoords = new Map();
    waves.forEach((wave, col) => {
      wave.forEach((nodeId, row) => {
        const x = paddingX + col * colSpacing;
        const y = paddingY + row * rowSpacing;
        nodeCoords.set(nodeId, { x, y });
      });
    });

    // Place any orphan nodes
    this.nodes.forEach((n, idx) => {
      if (!nodeCoords.has(n.node_id)) {
        nodeCoords.set(n.node_id, { x: paddingX, y: paddingY + idx * rowSpacing });
      }
    });

    // 1. Draw Edges
    this.edges.forEach((e) => {
      const from = nodeCoords.get(e.from_node_id);
      const to = nodeCoords.get(e.to_node_id);
      if (from && to) {
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        const startX = from.x + nodeWidth;
        const startY = from.y + nodeHeight / 2;
        const endX = to.x;
        const endY = to.y + nodeHeight / 2;
        const dx = (endX - startX) / 2;
        const d = `M ${startX} ${startY} C ${startX + dx} ${startY}, ${endX - dx} ${endY}, ${endX} ${endY}`;
        path.setAttribute("d", d);
        path.setAttribute("class", "dag-edge");
        this.svg.appendChild(path);
      }
    });

    // 2. Draw Nodes
    const statusSymbols = {
      PENDING: "○",
      RUNNING: "⠋",
      COMPLETED: "✓",
      WAITING_OPERATOR: "!",
      FAILED: "✗",
    };

    this.nodes.forEach((n) => {
      const coord = nodeCoords.get(n.node_id);
      if (!coord) return;

      const state = n.state || "PENDING";
      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute("class", `dag-node ${state}`);
      g.setAttribute("transform", `translate(${coord.x}, ${coord.y})`);

      // 1. Main Node Card Box
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("class", "dag-node-bg");
      rect.setAttribute("width", nodeWidth);
      rect.setAttribute("height", nodeHeight);
      rect.setAttribute("rx", "8");

      // 2. Status Box on Left
      const statusBox = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      statusBox.setAttribute("class", "dag-status-box");
      statusBox.setAttribute("x", "12");
      statusBox.setAttribute("y", "14");
      statusBox.setAttribute("width", "36");
      statusBox.setAttribute("height", "36");
      statusBox.setAttribute("rx", "6");

      // 3. Status Icon inside Status Box
      const statusIcon = document.createElementNS("http://www.w3.org/2000/svg", "text");
      statusIcon.setAttribute("class", "dag-status-icon");
      statusIcon.setAttribute("x", "30");
      statusIcon.setAttribute("y", "37");
      statusIcon.setAttribute("text-anchor", "middle");
      statusIcon.textContent = statusSymbols[state] || "○";

      // 4. Node Title (Moved to the right of the status box)
      const title = document.createElementNS("http://www.w3.org/2000/svg", "text");
      title.setAttribute("class", "dag-node-title");
      title.setAttribute("x", "58");
      title.setAttribute("y", "28");
      title.setAttribute("fill", "var(--neuri-foreground)");
      title.setAttribute("font-size", "12");
      title.setAttribute("font-weight", "bold");
      title.setAttribute("font-family", "var(--neuri-font-mono)");
      title.textContent = this.truncate(n.node_id, 20);

      // 5. Underlying Subtitle Text (Moved to the right so boxes don't overlap it)
      const sub = document.createElementNS("http://www.w3.org/2000/svg", "text");
      sub.setAttribute("class", "dag-node-sub");
      sub.setAttribute("x", "58");
      sub.setAttribute("y", "48");
      sub.setAttribute("fill", "var(--neuri-muted)");
      sub.setAttribute("font-size", "10");
      sub.setAttribute("font-family", "var(--neuri-font-mono)");
      const subContent = `${n.agent_role} · ${n.harness_id} · ${state}`;
      sub.textContent = this.truncate(subContent, 24);

      // 6. Tooltip with full details on hover
      const tooltip = document.createElementNS("http://www.w3.org/2000/svg", "title");
      tooltip.textContent = `Node: ${n.node_id}\nRole: ${n.agent_role}\nHarness: ${n.harness_id}\nState: ${state}\nInstruction: ${n.instruction || "None"}`;

      g.appendChild(rect);
      g.appendChild(statusBox);
      g.appendChild(statusIcon);
      g.appendChild(title);
      g.appendChild(sub);
      g.appendChild(tooltip);

      g.addEventListener("click", () => this.openInspector(n));
      this.svg.appendChild(g);
    });
  }

  openAddDrawer() {
    if (this.inspector) this.inspector.classList.remove("open");
    const parentSelect = document.getElementById("add-node-parent-select");
    if (parentSelect) {
      parentSelect.innerHTML = `
        <option value="auto">Auto-link to last box</option>
        <option value="none">None (Root / Parallel branch)</option>
      `;
      this.nodes.forEach((n) => {
        const opt = document.createElement("option");
        opt.value = n.node_id;
        opt.textContent = `${n.node_id} (${n.agent_role})`;
        parentSelect.appendChild(opt);
      });
    }
    const instrInput = document.getElementById("add-node-instruction");
    if (instrInput) instrInput.value = "";
    if (this.addDrawer) this.addDrawer.classList.add("open");
  }

  async submitAddNode() {
    const instrInput = document.getElementById("add-node-instruction");
    const instr = instrInput ? instrInput.value.trim() : "";
    if (!instr) {
      alert("Please enter a task instruction for the new box.");
      return;
    }
    const role = document.getElementById("add-node-role-select")?.value;
    const harness = document.getElementById("add-node-harness-select")?.value;
    const parentId = document.getElementById("add-node-parent-select")?.value;

    try {
      const res = await fetch("/api/v1/dag/node/new", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          instruction: instr,
          agent_role: role,
          harness_id: harness,
          parent_node_id: parentId,
        }),
      });
      if (res.ok) {
        if (this.addDrawer) this.addDrawer.classList.remove("open");
        if (instrInput) instrInput.value = "";
        await this.fetchDag();
      }
    } catch (err) {
      console.error("Failed to add node:", err);
    }
  }

  openInspector(node) {
    if (this.addDrawer) this.addDrawer.classList.remove("open");
    this.selectedNodeId = node.node_id;
    if (!this.inspector) return;

    document.getElementById("inspector-node-id").textContent = node.node_id;
    document.getElementById("inspector-role").textContent = node.agent_role;
    document.getElementById("inspector-state").textContent = node.state;
    document.getElementById("inspector-harness-select").value = node.harness_id || "agy";
    document.getElementById("inspector-instruction").value = node.instruction || "";

    this.inspector.classList.add("open");
  }

  async saveNodeEdits() {
    if (!this.selectedNodeId) return;
    const harness = document.getElementById("inspector-harness-select").value;
    const instruction = document.getElementById("inspector-instruction").value;

    try {
      const res = await fetch("/api/v1/dag/node", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          node_id: this.selectedNodeId,
          harness_id: harness,
          instruction: instruction,
        }),
      });
      if (res.ok) {
        if (this.inspector) this.inspector.classList.remove("open");
        await this.fetchDag();
      }
    } catch (err) {
      console.error("Failed to save node:", err);
    }
  }

  truncate(str, maxLen = 24) {
    if (!str) return "";
    return str.length > maxLen ? `${str.slice(0, maxLen - 1)}…` : str;
  }
}
