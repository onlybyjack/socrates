"""Run the backend: uv run python -m interview_agent"""

import asyncio
import logging
import os

import uvicorn

from .api import create_app
from .config import get_settings
from .parent_watch import watch_parent
from .llm import GatedLLM, OllamaLLM
from .store import Store
from .stt import MlxWhisperSTT
from .tts import MacSayTTS


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if parent := os.environ.get("IA_PARENT_PID"):
        watch_parent(int(parent))
    s = get_settings()
    gpu = asyncio.Lock()  # Whisper and Ollama share the GPU; never run them at the same time
    stt = MlxWhisperSTT(s.stt_model, lock=gpu)
    llm = GatedLLM(OllamaLLM(s.ollama_url, s.llm_model), gpu)
    app = create_app(llm, stt, MacSayTTS(s.tts_voice), Store(s.data_dir / "interview.db"))

    @app.on_event("startup")
    async def _warm() -> None:
        async def run() -> None:
            try:
                await stt.warmup()
            except Exception:
                logging.getLogger("interview_agent").exception("STT warmup failed (will retry on first answer)")

        asyncio.create_task(run())

    uvicorn.run(app, host="127.0.0.1", port=s.port)


if __name__ == "__main__":
    main()
