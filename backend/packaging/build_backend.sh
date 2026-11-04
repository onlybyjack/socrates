#!/usr/bin/env bash
# Build the backend into a standalone folder: backend/dist/interview-agent-backend/
set -euo pipefail
cd "$(dirname "$0")/.."
uv run pyinstaller packaging/entry.py \
  --name interview-agent-backend \
  --onedir --noconfirm --clean \
  --distpath dist --workpath build \
  --collect-all mlx \
  --collect-all mlx_whisper \
  --collect-all trafilatura \
  --collect-all justext \
  --collect-data courlan \
  --collect-data htmldate \
  --collect-submodules uvicorn \
  --collect-submodules interview_agent \
  --exclude-module torch \
  --exclude-module sympy \
  --exclude-module mlx_whisper.torch_whisper \
  --exclude-module tkinter

# Tauri copies bundle resources by following symlinks, so PyInstaller's
# _internal/libmlx.dylib -> mlx/lib/libmlx.dylib becomes a real file in the .app.
# MLX looks for mlx.metallib next to the dylib it loaded, so put a copy beside it,
# and materialize the symlinks now so dev and packaged layouts are identical.
INTERNAL=dist/interview-agent-backend/_internal
find "$INTERNAL" -maxdepth 1 -type l | while read -r link; do
  cp -L "$link" "$link.real" && mv -f "$link.real" "$link"
done
cp "$INTERNAL/mlx/lib/mlx.metallib" "$INTERNAL/mlx.metallib"
test -z "$(find dist/interview-agent-backend -type l)" || { echo "symlinks remain" >&2; exit 1; }

echo "built: $(du -sh dist/interview-agent-backend | cut -f1)"
