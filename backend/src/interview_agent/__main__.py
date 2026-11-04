"""Run the backend: uv run python -m interview_agent"""

import asyncio
import logging

import uvicorn

from .api import create_app
from .config import get_settings
from .llm import OllamaLLM
from .store import Store
from .stt import MlxWhisperSTT
from .tts import MacSayTTS


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    s = get_settings()
    stt = MlxWhisperSTT(s.stt_model)
    app = create_app(OllamaLLM(s.ollama_url, s.llm_model), stt, MacSayTTS(s.tts_voice), Store(s.data_dir / "interview.db"))

    @app.on_event("startup")
    async def _warm() -> None:
        asyncio.create_task(stt.warmup())

    uvicorn.run(app, host="127.0.0.1", port=s.port)


if __name__ == "__main__":
    main()
