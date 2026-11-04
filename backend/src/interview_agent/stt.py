"""Speech-to-text."""

import asyncio
import re
import tempfile
from pathlib import Path
from typing import Protocol

# Phrases Whisper tends to invent on silence/noise (Korean YouTube-subtitle artifacts).
_HALLUCINATIONS = [
    "시청해주셔서 감사합니다",
    "시청해 주셔서 감사합니다",
    "구독과 좋아요",
    "구독 좋아요",
    "다음 영상에서 만나요",
    "MBC 뉴스",
    "자막 제공",
]


def is_hallucination(text: str) -> bool:
    t = text.strip()
    if not re.search(r"[0-9A-Za-z가-힣]", t):
        return True
    norm = re.sub(r"[\s.!?,]", "", t)
    return any(re.sub(r"\s", "", h) in norm for h in _HALLUCINATIONS) and len(norm) < 30


class STT(Protocol):
    async def transcribe(self, wav: bytes) -> str: ...


class MlxWhisperSTT:
    def __init__(self, model: str):
        self.model = model
        self.ready = False
        self._lock = asyncio.Lock()

    def _run(self, path: str) -> str:
        import mlx_whisper  # heavy import, deferred

        result = mlx_whisper.transcribe(
            path, path_or_hf_repo=self.model, language="ko", condition_on_previous_text=False
        )
        self.ready = True
        return str(result.get("text", "")).strip()

    async def transcribe(self, wav: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav)
            path = f.name
        try:
            async with self._lock:  # one transcription at a time on the GPU
                text = await asyncio.to_thread(self._run, path)
        finally:
            Path(path).unlink(missing_ok=True)
        return "" if is_hallucination(text) else text

    async def warmup(self) -> None:
        """Download/load the model by transcribing 0.5s of silence."""
        import io
        import wave

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 8000)
        await self.transcribe(buf.getvalue())
