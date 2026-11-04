import asyncio

from fakes import FakeLLM
from interview_agent.llm import GatedLLM


async def test_stream_holds_gate_until_finished():
    lock = asyncio.Lock()
    llm = GatedLLM(FakeLLM(default_stream="[NEXT]\n질문입니다. 길게 이어지는 질문입니다."), lock)
    agen = llm.stream_chat([{"role": "user", "content": "x"}])
    first = await agen.__anext__()
    assert first and lock.locked()
    rest = [c async for c in agen]
    assert rest and not lock.locked()


async def test_chat_json_waits_for_gate():
    lock = asyncio.Lock()
    llm = GatedLLM(FakeLLM(json_responses=[{"a": 1}]), lock)
    await lock.acquire()  # e.g. Whisper is transcribing
    task = asyncio.create_task(llm.chat_json("s", "u"))
    await asyncio.sleep(0.01)
    assert not task.done()
    lock.release()
    assert await task == {"a": 1}


async def test_gate_released_when_stream_abandoned():
    lock = asyncio.Lock()
    llm = GatedLLM(FakeLLM(default_stream="abcdefghijklmnop"), lock)
    agen = llm.stream_chat([])
    await agen.__anext__()
    await agen.aclose()
    assert not lock.locked()


async def test_check_passthrough_and_model_attr():
    inner = FakeLLM()
    inner.model = "qwen3:8b"
    llm = GatedLLM(inner, asyncio.Lock())
    assert llm.model == "qwen3:8b"
    assert (await llm.check())["ok"] is True


async def test_stt_uses_shared_gate():
    from interview_agent.stt import MlxWhisperSTT
    from test_tts import _wav

    lock = asyncio.Lock()
    seen = []

    class Probe(MlxWhisperSTT):
        def _run(self, audio):
            seen.append(lock.locked())
            return "답변입니다"

    stt = Probe("m", lock=lock)
    assert await stt.transcribe(_wav(16000)) == "답변입니다"
    assert seen == [True] and not lock.locked()
