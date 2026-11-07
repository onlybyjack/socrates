"""Text-to-speech: Supertonic 3 (open-source, on-device ONNX), one interviewer voice per session."""

import asyncio
import io
import logging
import wave
import zlib
from typing import Protocol

import numpy as np

log = logging.getLogger("interview_agent")


class TTSEngine(Protocol):
    def available(self) -> bool: ...

    def voice_for(self, session_id: str) -> str | None: ...

    async def synthesize(self, text: str, voice: str | None = None) -> tuple[bytes, str]: ...


def pick_voice(voices: tuple[str, ...], session_id: str) -> str:
    """Random-looking but stable per session, so a reconnect keeps the same interviewer."""
    return voices[zlib.crc32(session_id.encode()) % len(voices)]


def to_wav(samples: np.ndarray, rate: int) -> bytes:
    pcm = (np.clip(samples.reshape(-1), -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


class SupertonicTTS:
    """Supertonic 3 (code MIT, model OpenRAIL-M). The model (~400MB) downloads on first warmup."""

    def __init__(self, voices: tuple[str, ...] = ("M3", "F2"), model: str = "supertonic-3"):
        self.voices = voices
        self.model = model
        self.ready = False
        self._tts = None
        self._styles: dict = {}
        self._load_lock = asyncio.Lock()
        self._run_lock = asyncio.Lock()  # one synthesis at a time on the ONNX session

    def available(self) -> bool:
        return self.ready

    def voice_for(self, session_id: str) -> str:
        return pick_voice(self.voices, session_id)

    def _load(self) -> None:
        from supertonic import TTS  # heavy import (onnxruntime), deferred

        tts = TTS(model=self.model)
        self._styles = {v: tts.get_voice_style(v) for v in self.voices}
        self._tts = tts

    async def warmup(self) -> None:
        async with self._load_lock:
            if self._tts is None:
                await asyncio.to_thread(self._load)
                self.ready = True

    def _run(self, text: str, voice: str) -> bytes:
        wav, _ = self._tts.synthesize(text, self._styles[voice], lang="ko")
        return to_wav(np.asarray(wav, dtype=np.float32), self._tts.sample_rate)

    async def synthesize(self, text: str, voice: str | None = None) -> tuple[bytes, str]:
        await self.warmup()
        voice = voice if voice in self._styles else self.voices[0]
        async with self._run_lock:
            audio = await asyncio.to_thread(self._run, text, voice)
        return audio, "audio/wav"
