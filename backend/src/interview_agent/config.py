import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    llm_model: str
    ollama_url: str
    data_dir: Path
    stt_model: str
    tts_voice: str
    port: int


def get_settings() -> Settings:
    env = os.environ.get
    return Settings(
        llm_model=env("IA_LLM_MODEL", "qwen3:8b"),
        ollama_url=env("IA_OLLAMA_URL", "http://localhost:11434"),
        data_dir=Path(
            env("IA_DATA_DIR", str(Path.home() / "Library/Application Support/interview-agent"))
        ).expanduser(),
        stt_model=env("IA_STT_MODEL", "mlx-community/whisper-large-v3-turbo"),
        tts_voice=env("IA_TTS_VOICE", "Yuna"),
        port=int(env("IA_PORT", "8765")),
    )
