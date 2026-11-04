/**
 * Neuri Studio — Native Desktop Bridge & Hot-Reload Client
 * Provides safe abstraction for Tauri native features and live CSS/HTML reloads.
 */

export class DesktopBridge {
  static isTauri() {
    return Boolean(
      window.__TAURI__ ||
      window.__TAURI_INTERNALS__ ||
      (window.location.protocol === "tauri:")
    );
  }

  static async openFileDialog(options = {}) {
    if (this.isTauri() && window.__TAURI__?.dialog?.open) {
      try {
        const selected = await window.__TAURI__.dialog.open({
          directory: Boolean(options.directory),
          multiple: Boolean(options.multiple),
          title: options.title || "Select Neuroimaging File",
          filters: options.filters || [
            { name: "Neuroimaging", extensions: ["nii", "nii.gz", "mgz", "mgh", "dcm"] }
          ]
        });
        return selected;
      } catch (err) {
        console.warn("Tauri dialog error, falling back:", err);
      }
    }
    return null;
  }

  static handleLiveReloadEvent(payload) {
    if (!payload || payload.action !== "live_reload_assets") return;

    const changedPath = payload.path || "";
    console.log("[Neuri HotReload] Live asset changed:", changedPath);

    if (changedPath.endsWith(".css")) {
      // Hot-swap all stylesheet links with cache-busting timestamp
      const links = document.querySelectorAll('link[rel="stylesheet"]');
      const timestamp = Date.now();
      links.forEach((link) => {
        const href = link.getAttribute("href");
        if (href) {
          const cleanHref = href.split("?")[0];
          link.setAttribute("href", `${cleanHref}?v=${timestamp}`);
        }
      });
    } else if (changedPath.endsWith(".html") || changedPath.endsWith(".js")) {
      // Refresh page content
      window.location.reload();
    }
  }
}
