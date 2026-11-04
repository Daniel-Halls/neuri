/**
 * Neuri Studio — NiiVue 3D/4D Neuroimaging Panel Controller
 * Bridges Neuri Studio with the full-featured standalone NiiVue visualizer
 * embedded inside pane-niivue, coordinating multi-host volume loading,
 * crosshairs feedback, view modes, and scene manifests.
 */

export class NiiVuePanel {
  constructor() {
    this.iframe = document.getElementById("niivue-embedded-viewer");
    this.latestCoordinates = null;
    this.workspaceVolumes = [];
    this.isLoaded = false;
  }

  async init() {
    this.bindMessageBus();
    await this.fetchWorkspaceVolumes();
  }

  bindMessageBus() {
    window.addEventListener("message", (event) => {
      if (!event.data) return;
      if (event.data.type === "NEURI_NIIVUE_COORDS") {
        this.latestCoordinates = event.data.coords || null;
      }
    });

    if (this.iframe) {
      this.iframe.addEventListener("load", () => {
        this.isLoaded = true;
        this.postToViewer({ type: "NEURI_RESIZE" });
      });
    }
  }

  postToViewer(msg) {
    if (!this.iframe || !this.iframe.contentWindow) return;
    try {
      this.iframe.contentWindow.postMessage(msg, "*");
    } catch (err) {
      console.warn("Failed to post message to NiiVue iframe:", err);
    }
  }

  onTabActivated() {
    this.postToViewer({ type: "NEURI_RESIZE" });
    this.postToViewer({ type: "NEURI_POLL_SCENE" });
  }

  fetchScene() {
    this.postToViewer({ type: "NEURI_POLL_SCENE" });
  }

  loadDemoVolume() {
    this.postToViewer({ type: "NEURI_LOAD_DEMO" });
  }

  loadVolume(volume) {
    this.postToViewer({ type: "NEURI_LOAD_VOLUME", volume: volume });
  }

  setViewMode(mode) {
    this.postToViewer({ type: "NEURI_SET_VIEW", mode: mode });
  }

  async fetchWorkspaceVolumes() {
    try {
      const res = await fetch("/api/v1/volumes");
      if (!res.ok) return;
      const data = await res.json();
      this.workspaceVolumes = data.volumes || [];
    } catch (err) {
      console.warn("Failed to list workspace volumes:", err);
    }
  }
}
