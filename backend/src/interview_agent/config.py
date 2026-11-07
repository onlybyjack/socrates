import os
from dataclasses import dataclass
from pathlib import Path

from .llm import DEFAULT_MLX_MODEL


@dataclass(frozen=True)
class Settings:
    llm_model: str
    data_dir: Path
    stt_model: str
    tts_voices: tuple[str, ...]
    port: int


def get_settings() -> Settings:
    env = os.environ.get
    return Settings(
        llm_model=env("IA_LLM_MODEL", DEFAULT_MLX_MODEL),
        data_dir=Path(
            env("IA_DATA_DIR", str(Path.home() / "Library/Application Support/interview-agent"))
        ).expanduser(),
        stt_model=env("IA_STT_MODEL", "mlx-community/whisper-large-v3-turbo"),
        # Supertonic voice per session, picked at random: M3 (male) / F2 (female)
        tts_voices=tuple(v.strip() for v in env("IA_TTS_VOICES", "M3,F2").split(",") if v.strip()),
        port=int(env("IA_PORT", "8765")),
    )
