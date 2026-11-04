"""Text-to-speech engines."""

import asyncio
import shutil
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Protocol


class TTSEngine(Protocol):
    def available(self) -> bool: ...

    async def synthesize(self, text: str) -> tuple[bytes, str]: ...


@lru_cache(maxsize=1)
def _mac_voices() -> frozenset[str]:
    if sys.platform != "darwin" or not shutil.which("say"):
        return frozenset()
    out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    return frozenset(line.split("  ")[0].strip() for line in out.splitlines() if line.strip())


class MacSayTTS:
    """macOS built-in `say` (offline). Not open source, but local; swap via the TTSEngine interface."""

    def __init__(self, voice: str = "Yuna", rate: int = 190):
        self.voice = voice
        self.rate = rate

    def available(self) -> bool:
        return self.voice in _mac_voices()

    async def synthesize(self, text: str) -> tuple[bytes, str]:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.wav"
            # Text goes through stdin so it can never be parsed as a flag.
            proc = await asyncio.create_subprocess_exec(
                "say", "-v", self.voice, "-r", str(self.rate),
                "--file-format=WAVE", "--data-format=LEI16@22050", "-o", str(out),
                stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, err = await proc.communicate(text.encode("utf-8"))
            if proc.returncode != 0:
                raise RuntimeError(f"say failed: {err.decode(errors='replace')}")
            return out.read_bytes(), "audio/wav"
