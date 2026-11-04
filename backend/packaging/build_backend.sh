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
echo "built: $(du -sh dist/interview-agent-backend | cut -f1)"
