"""Run the backend: uv run python -m interview_agent"""

import asyncio
import logging
import os

import uvicorn

from .api import create_app
from .config import get_settings
from .parent_watch import watch_parent
from .llm import GatedLLM, MlxLLM
from .store import Store
from .stt import MlxWhisperSTT
from .tts import SupertonicTTS


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if parent := os.environ.get("IA_PARENT_PID"):
        watch_parent(int(parent))
    s = get_settings()
    gpu = asyncio.Lock()  # Whisper and the LLM share the GPU; never run them at the same time
    stt = MlxWhisperSTT(s.stt_model, lock=gpu)
    llm = GatedLLM(MlxLLM(s.llm_model), gpu)
    tts = SupertonicTTS(s.tts_voices)
    app = create_app(llm, stt, tts, Store(s.data_dir / "interview.db"))

    @app.on_event("startup")
    async def _warm() -> None:
        async def run() -> None:
            try:
                await stt.warmup()
            except Exception:
                logging.getLogger("interview_agent").exception("STT warmup failed (will retry on first answer)")

        async def run_tts() -> None:
            try:
                await tts.warmup()
            except Exception:
                logging.getLogger("interview_agent").exception("TTS warmup failed (health check retries it)")

        async def run_llm() -> None:
            try:
                await llm.warmup()
            except Exception:
                logging.getLogger("interview_agent").exception("LLM warmup failed (loads on first use)")

        asyncio.create_task(run())
        asyncio.create_task(run_tts())
        asyncio.create_task(run_llm())

    uvicorn.run(app, host="127.0.0.1", port=s.port)


if __name__ == "__main__":
    main()
