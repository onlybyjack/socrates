"""Ollama chat client.

Every failure surfaces as LLMError (or its subclass LLMUnavailable when Ollama can't be reached or the
model is missing), so callers never see raw httpx/json exceptions.
"""

import json
from collections.abc import AsyncIterator
from typing import Protocol

import httpx

# One context size for every call: Ollama reloads the model when num_ctx changes.
# 12k tokens ≈ 1.8GB KV cache for an 8B model, which still fits a 16GB Mac.
NUM_CTX = 12288


class LLMError(RuntimeError):
    pass


class LLMUnavailable(LLMError):
    pass


class LLM(Protocol):
    async def chat_json(self, system: str, user: str) -> dict: ...

    def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]: ...


def _error_detail(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("error") or resp.text)
    except (json.JSONDecodeError, AttributeError):
        return resp.text


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

    def _check_status(self, resp: httpx.Response, detail: str | None = None) -> None:
        if resp.status_code == 404:
            raise LLMUnavailable(f"모델을 찾을 수 없어요: {self.model}")
        if resp.status_code >= 400:
            raise LLMError(f"Ollama 오류 ({resp.status_code}): {detail if detail is not None else _error_detail(resp)}")

    async def chat_json(self, system: str, user: str) -> dict:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "format": "json",
            "stream": False,
            "think": False,
            "options": {"temperature": 0.3, "num_ctx": NUM_CTX},
        }
        last_err: Exception | None = None
        try:
            async with self._client() as c:
                for _ in range(2):
                    resp = await c.post("/api/chat", json=body)
                    self._check_status(resp)
                    content = resp.json().get("message", {}).get("content", "")
                    try:
                        data = json.loads(content)
                        if isinstance(data, dict):
                            return data
                        last_err = LLMError("JSON object expected")
                    except json.JSONDecodeError as e:
                        last_err = e
        except httpx.ConnectError as e:
            raise LLMUnavailable(str(e)) from e
        except httpx.HTTPError as e:
            raise LLMError(f"Ollama 통신 오류: {e!r}") from e
        raise LLMError(f"LLM이 올바른 JSON을 돌려주지 않았어요: {last_err}")

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "think": False,
            "options": {"temperature": 0.7, "num_ctx": NUM_CTX},
        }
        try:
            async with self._client() as c:
                async with c.stream("POST", "/api/chat", json=body) as resp:
                    if resp.status_code >= 400:
                        await resp.aread()
                        self._check_status(resp)
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError as e:
                            raise LLMError(f"Ollama 응답을 해석하지 못했어요: {line[:80]}") from e
                        if chunk.get("error"):
                            raise LLMError(f"Ollama 오류: {chunk['error']}")
                        text = chunk.get("message", {}).get("content", "")
                        if text:
                            yield text
                        if chunk.get("done"):
                            break
        except httpx.ConnectError as e:
            raise LLMUnavailable(str(e)) from e
        except httpx.HTTPError as e:
            raise LLMError(f"Ollama 통신 오류: {e!r}") from e

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


class GatedLLM:
    """Runs LLM calls one at a time behind a lock shared with STT.

    Whisper (mlx) and Ollama both use the Metal GPU. Running them at the same time can starve
    WindowServer long enough for macOS to panic, so GPU work is serialized.
    """

    def __init__(self, inner, lock):
        self.inner = inner
        self.lock = lock

    @property
    def model(self) -> str:
        return getattr(self.inner, "model", "")

    async def chat_json(self, system: str, user: str) -> dict:
        async with self.lock:
            return await self.inner.chat_json(system, user)

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        async with self.lock:
            async for chunk in self.inner.stream_chat(messages):
                yield chunk

    async def check(self) -> dict:
        return await self.inner.check()
