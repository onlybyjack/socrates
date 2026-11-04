"""Ollama chat client."""

import json
from collections.abc import AsyncIterator
from typing import Protocol

import httpx


class LLMError(RuntimeError):
    pass


class LLMUnavailable(LLMError):
    pass


class LLM(Protocol):
    async def chat_json(self, system: str, user: str) -> dict: ...

    def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]: ...


class OllamaLLM:
    def __init__(self, base_url: str, model: str, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            transport=self._transport,
            timeout=httpx.Timeout(300, connect=5),
        )

    async def chat_json(self, system: str, user: str) -> dict:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "format": "json",
            "stream": False,
            "think": False,
            "options": {"temperature": 0.3, "num_ctx": 16384},
        }
        last_err: Exception | None = None
        async with self._client() as c:
            for _ in range(2):
                try:
                    resp = await c.post("/api/chat", json=body)
                except httpx.ConnectError as e:
                    raise LLMUnavailable(str(e)) from e
                if resp.status_code == 404:
                    raise LLMUnavailable(f"모델을 찾을 수 없어요: {self.model}")
                resp.raise_for_status()
                content = resp.json().get("message", {}).get("content", "")
                try:
                    data = json.loads(content)
                    if isinstance(data, dict):
                        return data
                    last_err = LLMError("JSON object expected")
                except json.JSONDecodeError as e:
                    last_err = e
        raise LLMError(f"LLM이 올바른 JSON을 돌려주지 않았어요: {last_err}")

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "think": False,
            "options": {"temperature": 0.7, "num_ctx": 16384},
        }
        async with self._client() as c:
            try:
                async with c.stream("POST", "/api/chat", json=body) as resp:
                    if resp.status_code == 404:
                        raise LLMUnavailable(f"모델을 찾을 수 없어요: {self.model}")
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        chunk = json.loads(line)
                        text = chunk.get("message", {}).get("content", "")
                        if text:
                            yield text
                        if chunk.get("done"):
                            break
            except httpx.ConnectError as e:
                raise LLMUnavailable(str(e)) from e

    async def check(self) -> dict:
        try:
            async with self._client() as c:
                resp = await c.get("/api/tags")
                resp.raise_for_status()
        except httpx.HTTPError:
            return {"ok": False, "model_present": False}
        names = {m.get("name", "") for m in resp.json().get("models", [])}
        present = self.model in names or f"{self.model}:latest" in names
        return {"ok": True, "model_present": present}
