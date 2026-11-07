"""LLM client: the model runs in this process on Apple Silicon (mlx-lm), so the app needs nothing else installed.

Every failure surfaces as LLMError (or its subclass LLMUnavailable when the model is missing or can't be
loaded), so callers never see raw mlx/json exceptions.
"""

import asyncio
import json
import logging
import re
import threading
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

log = logging.getLogger("interview_agent")
DEFAULT_MLX_MODEL = "mlx-community/Qwen3-8B-4bit"

class LLMError(RuntimeError):
    pass


class LLMUnavailable(LLMError):
    pass


class LLM(Protocol):
    async def chat_json(self, system: str, user: str) -> dict: ...

    def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]: ...


_THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def extract_json(text: str) -> dict | None:
    """The first JSON object in a model reply (tolerates <think> blocks, code fences, chatter)."""
    text = _THINK_RE.sub("", text)
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
                    return data if isinstance(data, dict) else None
        start = text.find("{", start + 1)
    return None


class MlxLLM:
    """Runs the model in this process on Apple Silicon (mlx-lm). Nothing to install besides the app.

    The model is a Hugging Face repo (default Qwen3-8B 4-bit, ~4.6GB), downloaded by `pull()` on
    first run and loaded lazily on the first call.
    """

    def __init__(self, model: str = DEFAULT_MLX_MODEL, json_max_tokens: int = 3072, chat_max_tokens: int = 512):
        self.model = model
        self.json_max_tokens = json_max_tokens
        self.chat_max_tokens = chat_max_tokens
        self._loaded = None
        self._lock = threading.Lock()  # one generation at a time on the model

    # ---- model files ----
    def _local_path(self) -> str | None:
        from huggingface_hub import snapshot_download

        try:
            return snapshot_download(self.model, local_files_only=True)
        except Exception:
            return None

    async def check(self) -> dict:
        present = await asyncio.to_thread(self._local_path) is not None
        return {"ok": True, "model_present": present}

    async def pull(self, on_progress) -> None:
        """Download the model, reporting (status, completed_bytes, total_bytes) by watching the cache."""
        from huggingface_hub import HfApi, snapshot_download
        from huggingface_hub.constants import HF_HUB_CACHE

        try:
            info = await asyncio.to_thread(lambda: HfApi().model_info(self.model, files_metadata=True))
            total = sum((f.size or 0) for f in info.siblings or [])
        except Exception as e:
            raise LLMError(f"모델 정보를 가져오지 못했어요: {e}") from e
        blobs = Path(HF_HUB_CACHE) / f"models--{self.model.replace('/', '--')}" / "blobs"

        def done_bytes() -> int:
            return sum(p.stat().st_size for p in blobs.glob("*") if p.is_file()) if blobs.exists() else 0

        task = asyncio.create_task(asyncio.to_thread(snapshot_download, self.model))
        while not task.done():
            on_progress("downloading", min(done_bytes(), total), total)
            await asyncio.sleep(0.5)
        try:
            task.result()
        except Exception as e:
            raise LLMError(f"모델을 내려받지 못했어요: {e}") from e
        on_progress("success", total, total)

    async def warmup(self) -> None:
        """Load the weights ahead of the first question (no-op until the model is downloaded)."""
        if self._loaded is None and await asyncio.to_thread(self._local_path) is not None:
            await asyncio.to_thread(self._ensure)

    # ---- generation ----
    def _ensure(self):
        if self._loaded is None:
            path = self._local_path()
            if path is None:
                raise LLMUnavailable(f"모델이 아직 없어요: {self.model}")
            from mlx_lm import load

            try:
                self._loaded = load(path)
            except Exception as e:
                raise LLMUnavailable(f"모델을 불러오지 못했어요: {e}") from e
        return self._loaded

    def _prompt(self, tokenizer, messages: list[dict]) -> str:
        try:
            return tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, tokenize=False, enable_thinking=False
            )
        except TypeError:  # template without the thinking switch
            return tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)

    def _run(self, messages: list[dict], temp: float, max_tokens: int, on_text=None, stop: threading.Event | None = None) -> str:
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler

        with self._lock:
            model, tokenizer = self._ensure()
            prompt = self._prompt(tokenizer, messages)
            sampler = make_sampler(temp=temp, top_p=0.9 if temp > 0 else 0.0)
            out = []
            for r in stream_generate(model, tokenizer, prompt, max_tokens=max_tokens, sampler=sampler):
                if r.text:
                    out.append(r.text)
                    if on_text:
                        on_text(r.text)
                if stop is not None and stop.is_set():
                    break
            return "".join(out)

    async def chat_json(self, system: str, user: str) -> dict:
        messages = [
            {"role": "system", "content": system + "\n반드시 JSON 객체 하나만 출력합니다. 설명이나 코드 블록 표시는 쓰지 않습니다."},
            {"role": "user", "content": user},
        ]
        last = ""
        for _ in range(2):
            try:
                last = await asyncio.to_thread(self._run, messages, 0.3, self.json_max_tokens)
            except LLMError:
                raise
            except Exception as e:
                raise LLMError(f"LLM 실행 오류: {e!r}") from e
            data = extract_json(last)
            if data is not None:
                return data
        raise LLMError(f"LLM이 올바른 JSON을 돌려주지 않았어요: {last[:120]}")

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()
        stop = threading.Event()
        end = object()

        def worker() -> None:
            try:
                self._run(messages, 0.7, self.chat_max_tokens, lambda t: loop.call_soon_threadsafe(q.put_nowait, t), stop)
                loop.call_soon_threadsafe(q.put_nowait, end)
            except Exception as e:
                loop.call_soon_threadsafe(q.put_nowait, e)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            while True:
                item = await q.get()
                if item is end:
                    break
                if isinstance(item, LLMError):
                    raise item
                if isinstance(item, Exception):
                    raise LLMError(f"LLM 실행 오류: {item!r}") from item
                yield item
        finally:
            stop.set()  # consumer left early (socket closed): stop generating
            await asyncio.to_thread(thread.join)


class GatedLLM:
    """Runs LLM calls one at a time behind a lock shared with STT.

    Whisper and the LLM both use the Metal GPU. Running them at the same time can starve
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

    async def pull(self, on_progress) -> None:
        # Network/disk only, no GPU: not gated.
        await self.inner.pull(on_progress)

    async def warmup(self) -> None:
        async with self.lock:
            await self.inner.warmup()
