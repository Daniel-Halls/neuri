/**
 * Neuri Studio — Compute Fleet & Shell Mode Controller
 * Monitors machine health, Slurm arrays, and handles remote shell targeting.
 */

export class FleetPanel {
  constructor() {
    this.container = document.getElementById("fleet-container");
    this.selectorBar = document.getElementById("machine-selector-bar");
    this.machines = ["localhost"];
    this.selectedMachine = "localhost";
    this.pollInterval = null;
  }

  init() {
    this.fetchMachines();
    this.pollInterval = setInterval(() => this.fetchMachines(), 5000);
  }

  async fetchMachines() {
    try {
      const res = await fetch("/api/v1/machines");
      if (!res.ok) return;
      const data = await res.json();
      const list = data.machines || [];
      this.renderFleet(list);

      // Extract machine names for selector
      const names = list.map((m) => m.host).filter(Boolean);
      if (names.length > 0) {
        this.machines = names;
        this.renderSelectorPills();
      }
    } catch (err) {
      console.warn("Failed to probe compute machines:", err);
    }
  }

  renderFleet(machinesList) {
    if (!this.container) return;
    this.container.innerHTML = "";

    if (machinesList.length === 0) {
      this.container.innerHTML = `
        <div style="color:var(--neuri-muted); font-size:0.85rem; padding:12px;">
          No remote machines configured. Attach one via <code style="color:var(--neuri-primary)">/remote bootstrap &lt;host&gt;</code>.
        </div>`;
      return;
    }

    machinesList.forEach((m) => {
      const card = document.createElement("div");
      card.className = "host-card";

      const isOnline = Boolean(m.online);
      const dotClass = isOnline ? "host-dot-online" : "host-dot-offline";
      const loadArr = m.load_avg || [0, 0, 0];
      const loadVal = loadArr.length > 0 ? parseFloat(loadArr[0]) : 0;
      const cores = parseInt(m.cpu_count || 1, 10);
      const loadPercent = Math.min(100, Math.round((loadVal / Math.max(1, cores)) * 100));

      let meterClass = "meter-fill";
      if (loadPercent >= 100) meterClass += " error";
      else if (loadPercent >= 75) meterClass += " warning";

      let jobsHtml = "";
      const slurmJobs = m.slurm_jobs || [];
      if (slurmJobs.length > 0) {
        jobsHtml = '<div style="margin-top:6px; font-size:0.78rem; font-family:var(--neuri-font-mono);">';
        slurmJobs.forEach((j) => {
          jobsHtml += `<div>Slurm #${j.slurm_job_id} &middot; <span style="color:var(--neuri-success);">${j.state}</span></div>`;
        });
        jobsHtml += "</div>";
      }

      card.innerHTML = `
        <div class="host-header">
          <div class="host-title">
            <span class="${dotClass}">&#9679;</span>
            <span>${m.host}</span>
          </div>
          <div style="font-size:0.75rem; color:var(--neuri-muted);">${cores} CPUs</div>
        </div>
        <div style="font-size:0.76rem; color:var(--neuri-muted); display:flex; justify-content:space-between;">
          <span>Load Avg: ${loadVal.toFixed(2)}</span>
          <span>${loadPercent}%</span>
        </div>
        <div class="meter-bar">
          <div class="${meterClass}" style="width: ${loadPercent}%;"></div>
        </div>
        ${jobsHtml}
        <div style="margin-top:8px; display:flex; gap:6px;">
          <button class="dag-btn shell-target-btn" data-host="${m.host}">Target in Shell</button>
        </div>
      `;

      card.querySelector(".shell-target-btn").addEventListener("click", () => {
        this.selectMachine(m.host);
        const appInstance = window.__neuriApp;
        if (appInstance) appInstance.setShellMode(true);
      });

      this.container.appendChild(card);
    });
  }

  renderSelectorPills() {
    if (!this.selectorBar) return;
    const pillsBox = this.selectorBar.querySelector(".machine-pills-box");
    if (!pillsBox) return;

    pillsBox.innerHTML = "";
    this.machines.forEach((host) => {
      const pill = document.createElement("span");
      pill.className = `machine-pill ${host === this.selectedMachine ? "active" : ""}`;
      pill.textContent = host;
      pill.addEventListener("click", () => this.selectMachine(host));
      pillsBox.appendChild(pill);
    });
  }

  selectMachine(host) {
    this.selectedMachine = host;
    this.renderSelectorPills();
  }

  nextMachine() {
    const idx = this.machines.indexOf(this.selectedMachine);
    const nextIdx = (idx + 1) % this.machines.length;
    this.selectMachine(this.machines[nextIdx]);
  }

  prevMachine() {
    const idx = this.machines.indexOf(this.selectedMachine);
    const prevIdx = (idx - 1 + this.machines.length) % this.machines.length;
    this.selectMachine(this.machines[prevIdx]);
  }
}
