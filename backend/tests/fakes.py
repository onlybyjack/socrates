"""Test doubles for LLM / STT / TTS."""

from collections.abc import AsyncIterator


class FakeLLM:
    def __init__(self, json_responses=None, stream_responses=None, default_stream=None):
        self.json_responses = list(json_responses or [])
        self.stream_responses = list(stream_responses or [])
        self.default_stream = default_stream
        self.json_calls: list[tuple[str, str]] = []
        self.stream_calls: list[list[dict]] = []

    async def chat_json(self, system: str, user: str) -> dict:
        self.json_calls.append((system, user))
        return self.json_responses.pop(0) if self.json_responses else {}

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        self.stream_calls.append(messages)
        if self.stream_responses:
            text = self.stream_responses.pop(0)
        elif self.default_stream is not None:
            text = self.default_stream
        else:
            text = "[NEXT]\n다음 질문입니다."
        for i in range(0, len(text), 5):
            yield text[i : i + 5]

    async def check(self) -> dict:
        return {"ok": True, "model_present": True}


class FakeSTT:
    def __init__(self, texts=None):
        self.texts = list(texts or [])

    async def transcribe(self, wav: bytes) -> str:
        return self.texts.pop(0) if self.texts else "네, 답변입니다."


class FakeTTS:
    def available(self) -> bool:
        return True

    async def synthesize(self, text: str) -> tuple[bytes, str]:
        return b"RIFF" + text.encode(), "audio/wav"
