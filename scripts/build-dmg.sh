#!/usr/bin/env bash
# Build Interview Agent.app and .dmg with the Python backend bundled inside.
# Output: app/src-tauri/target/release/bundle/dmg/*.dmg
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="/opt/homebrew/opt/rustup/bin:$HOME/.cargo/bin:$PATH"

echo "==> 1/2 backend (PyInstaller)"
"$ROOT/backend/packaging/build_backend.sh"

echo "==> 2/2 app (Tauri)"
cd "$ROOT/app"
pnpm install --frozen-lockfile
pnpm tauri build --bundles app,dmg

ls -lh "$ROOT"/app/src-tauri/target/release/bundle/dmg/*.dmg
