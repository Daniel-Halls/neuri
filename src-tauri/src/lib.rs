use std::io::BufRead;
use std::sync::{Arc, Mutex};
use tauri::Manager;

pub fn run() {
    let child_holder: Arc<Mutex<Option<std::process::Child>>> = Arc::new(Mutex::new(None));
    let child_holder_exit = child_holder.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(move |app| {
            let app_handle = app.handle().clone();

            // Determine command based on debug (dev) vs release
            let mut command = if cfg!(debug_assertions) {
                // In dev mode, run live python environment via uv
                let mut cmd = std::process::Command::new("uv");
                cmd.args(["run", "python", "-m", "neuri.gui.sidecar", "--dev", "--port", "0"]);
                cmd
            } else {
                // In production mode, locate bundled sidecar binary
                let exe_dir = std::env::current_exe()
                    .ok()
                    .and_then(|p| p.parent().map(|p| p.to_path_buf()))
                    .unwrap_or_else(|| std::path::PathBuf::from("."));
                let sidecar_bin = exe_dir.join("neuri-engine");
                let mut cmd = std::process::Command::new(sidecar_bin);
                cmd.args(["--port", "0"]);
                cmd
            };

            // Forward CLI arguments (e.g. --workspace, --model, --harness) from neuri-desktop
            let args: Vec<String> = std::env::args().skip(1).collect();
            if !args.is_empty() {
                command.args(&args);
            }

            if let Ok(cwd) = std::env::current_dir() {
                command.current_dir(cwd);
            }

            command.stdout(std::process::Stdio::piped());
            command.stdin(std::process::Stdio::piped());

            match command.spawn() {
                Ok(mut child) => {
                    if let Some(stdout) = child.stdout.take() {
                        let handle = app_handle.clone();
                        std::thread::spawn(move || {
                            let reader = std::io::BufReader::new(stdout);
                            for line in reader.lines().flatten() {
                                if line.starts_with("NEURI_STUDIO_READY ") {
                                    let url_str = line
                                        .trim_start_matches("NEURI_STUDIO_READY ")
                                        .trim();
                                    if let Ok(target_url) = url_str.parse::<url::Url>() {
                                        if let Some(window) = handle.get_webview_window("main") {
                                            let _ = window.navigate(target_url);
                                        }
                                    }
                                    break;
                                }
                            }
                        });
                    }

                    if let Ok(mut lock) = child_holder.lock() {
                        *lock = Some(child);
                    }
                }
                Err(err) => {
                    eprintln!("[Neuri Desktop] Failed to spawn sidecar process: {}", err);
                }
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(move |_app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                if let Ok(mut lock) = child_holder_exit.lock() {
                    if let Some(mut child) = lock.take() {
                        let _ = child.kill();
                        let _ = child.wait();
                    }
                }
            }
        });
}
