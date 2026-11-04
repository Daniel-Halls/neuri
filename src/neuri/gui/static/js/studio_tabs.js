/**
 * Neuri Studio — Studio Viewport Tabs & Layout Resizer
 * Manages tab switching (DAG, NiiVue, Fleet, QC, Brain) and split-pane resizing.
 */

export class StudioTabs {
  constructor() {
    this.tabs = document.querySelectorAll(".studio-tab");
    this.panes = document.querySelectorAll(".studio-content-pane");
    this.divider = document.getElementById("pane-divider");
    this.chatColumn = document.getElementById("chat-column");
    this.studioViewport = document.getElementById("studio-viewport");
    this.activeTab = "dag";
  }

  init() {
    this.tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const target = tab.getAttribute("data-tab");
        this.switchTab(target);
      });
    });

    this.bindDividerDrag();
  }

  switchTab(tabId) {
    this.activeTab = tabId;

    // Update tab bar buttons
    this.tabs.forEach((tab) => {
      if (tab.getAttribute("data-tab") === tabId) {
        tab.classList.add("active");
      } else {
        tab.classList.remove("active");
      }
    });

    // Update content panes
    this.panes.forEach((pane) => {
      if (pane.id === `pane-${tabId}`) {
        pane.classList.add("active");
      } else {
        pane.classList.remove("active");
      }
    });

    // Sync activity rail
    document.querySelectorAll(".rail-btn").forEach((btn) => {
      if (btn.getAttribute("data-target") === tabId) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });

    // Refresh NiiVue workspace volumes and canvas size when switched
    if (tabId === "niivue" && window.__neuriApp && window.__neuriApp.niivuePanel) {
      if (typeof window.__neuriApp.niivuePanel.onTabActivated === "function") {
        window.__neuriApp.niivuePanel.onTabActivated();
      }
      if (typeof window.__neuriApp.niivuePanel.fetchWorkspaceVolumes === "function") {
        window.__neuriApp.niivuePanel.fetchWorkspaceVolumes();
      }
    }
  }

  bindDividerDrag() {
    if (!this.divider || !this.chatColumn || !this.studioViewport) return;

    let isDragging = false;

    this.divider.addEventListener("mousedown", (e) => {
      isDragging = true;
      this.divider.classList.add("dragging");
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    });

    window.addEventListener("mousemove", (e) => {
      if (!isDragging) return;
      const totalWidth = window.innerWidth - 50; // exclude activity rail
      const newChatWidth = Math.max(360, Math.min(totalWidth - 300, e.clientX - 50));
      const newStudioWidth = totalWidth - newChatWidth;

      this.chatColumn.style.flex = "none";
      this.chatColumn.style.width = `${newChatWidth}px`;
      this.studioViewport.style.width = `${newStudioWidth}px`;
    });

    window.addEventListener("mouseup", () => {
      if (isDragging) {
        isDragging = false;
        this.divider.classList.remove("dragging");
        document.body.style.cursor = "default";
        document.body.style.userSelect = "auto";
      }
    });
  }
}
