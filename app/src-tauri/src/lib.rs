use std::fs::{self, File};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::{Manager, RunEvent};

/// The bundled Python backend (PyInstaller onedir copied into Resources/backend/).
struct Backend(Mutex<Option<Child>>);

/// Start the bundled backend. Skipped in `tauri dev`, where you run it yourself with `uv run`.
fn spawn_backend(app: &tauri::App) -> Option<Child> {
    if cfg!(debug_assertions) {
        return None;
    }
    let exe = app
        .path()
        .resource_dir()
        .ok()?
        .join("backend")
        .join("interview-agent-backend");
    let log_dir = app.path().home_dir().ok()?.join("Library/Logs/interview-agent");
    let _ = fs::create_dir_all(&log_dir);
    let log = File::create(log_dir.join("backend.log")).ok()?;
    let err = log.try_clone().ok()?;
    Command::new(exe)
        // Lets the backend exit on its own if this app dies without running the exit hook.
        .env("IA_PARENT_PID", std::process::id().to_string())
        .stdout(Stdio::from(log))
        .stderr(Stdio::from(err))
        .spawn()
        .map_err(|e| eprintln!("failed to start backend: {e}"))
        .ok()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let child = spawn_backend(app);
            app.manage(Backend(Mutex::new(child)));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|handle, event| {
            if let RunEvent::Exit = event {
                if let Some(mut child) = handle.state::<Backend>().0.lock().unwrap().take() {
                    let _ = child.kill();
                    let _ = child.wait();
                }
            }
        });
}
