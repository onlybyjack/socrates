"""Speech-to-text."""

import asyncio
import io
import re
import wave
from math import gcd
from typing import Protocol

import numpy as np

WHISPER_RATE = 16000

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


def load_wav_16k(data: bytes) -> np.ndarray:
    """Decode a PCM16 WAV into mono float32 at 16 kHz.

    Done in Python so the app never needs the ffmpeg binary (mlx-whisper shells out to ffmpeg for
    file paths, and a Finder-launched .app has no Homebrew PATH).
    """
    with wave.open(io.BytesIO(data), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("16-bit PCM WAV만 지원해요.")
        rate, channels = w.getframerate(), w.getnchannels()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    audio = pcm.astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if rate != WHISPER_RATE:
        from scipy.signal import resample_poly

        g = gcd(rate, WHISPER_RATE)
        audio = resample_poly(audio, WHISPER_RATE // g, rate // g).astype(np.float32)
    return audio


class STT(Protocol):
    async def transcribe(self, wav: bytes, hint: str = "") -> str: ...


# Terms Whisper tends to spell phonetically in Korean speech ("제미나", "패스트잎").
_BASE_TERMS = [
    "Python", "Java", "TypeScript", "FastAPI", "Spring", "React", "Next.js", "Node.js",
    "LLM", "Gemini", "OpenAI", "GPT", "Claude", "Whisper", "STT", "TTS", "RAG",
    "API", "REST", "GraphQL", "Docker", "Kubernetes", "AWS", "GCP", "Kafka", "Redis",
    "PostgreSQL", "MySQL", "MongoDB",
]
_MAX_HINT_CHARS = 300  # Whisper's prompt window is ~224 tokens; keep it well under


def vocabulary_terms(analysis: dict | None) -> list[str]:
    """Tech terms from the candidate's materials and the job posting first, then common ones."""
    analysis = analysis or {}
    job = analysis.get("job") or {}
    cand = analysis.get("candidate") or {}
    found: list[str] = []
    for item in [*(cand.get("skills") or []), *(job.get("required") or []), *(job.get("preferred") or [])]:
        for word in re.findall(r"[A-Za-z][A-Za-z0-9.+#/-]{1,30}", str(item)):
            found.append(word)
    terms, seen = [], set()
    for t in [*found, *_BASE_TERMS]:
        if t.lower() not in seen:
            seen.add(t.lower())
            terms.append(t)
    return terms


def vocabulary_hint(analysis: dict | None) -> str:
    """Whisper `initial_prompt`: the candidate's and the job's own tech terms, so they are written correctly."""
    terms = vocabulary_terms(analysis)
    head = "개발자 기술 면접 답변입니다. 용어: "
    out = head
    for t in terms:
        nxt = f"{out}{t}, " if out != head else f"{out}{t}, "
        if len(nxt) > _MAX_HINT_CHARS:
            break
        out = nxt
    return out.rstrip(", ") + "."


class MlxWhisperSTT:
    def __init__(self, model: str, lock: asyncio.Lock | None = None):
        self.model = model
        self.ready = False
        self._lock = lock or asyncio.Lock()  # shared with the LLM so GPU work never overlaps

    def _run(self, audio: np.ndarray, hint: str = "") -> str:
        import mlx_whisper  # heavy import, deferred

        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=self.model,
            language="ko",
            condition_on_previous_text=False,
            initial_prompt=hint or None,
        )
        self.ready = True
        return str(result.get("text", "")).strip()

    async def transcribe(self, wav: bytes, hint: str = "") -> str:
        audio = load_wav_16k(wav)
        async with self._lock:
            text = await asyncio.to_thread(self._run, audio, hint)
        # With a prompt, silence can come back as the prompt itself.
        if hint and text.strip().startswith(hint[:12]):
            return ""
        return "" if is_hallucination(text) else text

    async def warmup(self) -> None:
        """Download/load the model by transcribing 0.5s of silence."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 8000)
        await self.transcribe(buf.getvalue())
