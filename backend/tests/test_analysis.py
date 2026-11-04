import json

import httpx
import pytest

from fakes import FakeLLM
from interview_agent.analysis import analyze, make_plan
from interview_agent.llm import LLMError, OllamaLLM


async def test_analyze_blank_source_raises():
    with pytest.raises(ValueError, match="이력서"):
        await analyze(FakeLLM(), "   ", "공고")


async def test_analyze_blank_job_raises():
    with pytest.raises(ValueError, match="공고"):
        await analyze(FakeLLM(), "이력서", " ")


async def test_analyze_returns_llm_json_with_defaults():
    llm = FakeLLM(json_responses=[{"job": {"company": "키코", "role": "백엔드"}, "match": {"strengths": [{"point": "p", "evidence": "e"}]}}])
    out = await analyze(llm, "이력서 텍스트", "공고 텍스트")
    assert out["job"]["company"] == "키코"
    assert out["job"]["required"] == []
    assert out["candidate"]["skills"] == []
    assert out["match"]["strengths"] == [{"point": "p", "evidence": "e"}]
    assert out["match"]["gaps"] == [] and out["match"]["probes"] == []
    system, user = llm.json_calls[0]
    assert "이력서 텍스트" in user and "공고 텍스트" in user


async def test_make_plan_pads_and_truncates():
    llm = FakeLLM(json_responses=[{
        "experience": [{"topic": f"e{i}", "intent": "i"} for i in range(5)],
        "technical": [{"topic": "t0", "intent": "i"}],
    }])
    plan = await make_plan(llm, {"match": {"probes": [{"topic": "probe-x", "why": "w"}]}})
    assert [t["topic"] for t in plan["experience"]] == ["e0", "e1", "e2"]
    assert len(plan["technical"]) == 2
    assert plan["technical"][0]["topic"] == "t0"
    assert plan["technical"][1]["topic"]  # padded with something non-empty


async def test_ollama_chat_json_retries_once():
    calls = []

    def handler(req):
        calls.append(json.loads(req.content))
        content = "not json" if len(calls) == 1 else '{"a": 1}'
        return httpx.Response(200, json={"message": {"content": content}})

    llm = OllamaLLM("http://ollama.test", "qwen3:8b", transport=httpx.MockTransport(handler))
    assert await llm.chat_json("sys", "user") == {"a": 1}
    assert len(calls) == 2
    assert calls[0]["format"] == "json" and calls[0]["think"] is False
    assert calls[0]["model"] == "qwen3:8b"


async def test_ollama_chat_json_gives_up_after_two():
    handler = lambda req: httpx.Response(200, json={"message": {"content": "nope"}})
    llm = OllamaLLM("http://ollama.test", "m", transport=httpx.MockTransport(handler))
    with pytest.raises(LLMError):
        await llm.chat_json("s", "u")


async def test_ollama_stream_chat_yields_content():
    lines = "\n".join(json.dumps({"message": {"content": c}, "done": False}) for c in ["안녕", "하세요"])
    lines += "\n" + json.dumps({"message": {"content": ""}, "done": True})
    handler = lambda req: httpx.Response(200, text=lines)
    llm = OllamaLLM("http://ollama.test", "m", transport=httpx.MockTransport(handler))
    out = [c async for c in llm.stream_chat([{"role": "user", "content": "hi"}])]
    assert "".join(out) == "안녕하세요"


async def test_ollama_http_500_raises_llmerror():
    handler = lambda req: httpx.Response(500, json={"error": "model requires more system memory"})
    llm = OllamaLLM("http://ollama.test", "m", transport=httpx.MockTransport(handler))
    with pytest.raises(LLMError, match="memory"):
        await llm.chat_json("s", "u")
    with pytest.raises(LLMError):
        [c async for c in llm.stream_chat([{"role": "user", "content": "hi"}])]


async def test_ollama_read_error_mapped_to_llmerror():
    def handler(req):
        raise httpx.ReadTimeout("slow", request=req)

    llm = OllamaLLM("http://ollama.test", "m", transport=httpx.MockTransport(handler))
    with pytest.raises(LLMError):
        await llm.chat_json("s", "u")
    with pytest.raises(LLMError):
        [c async for c in llm.stream_chat([{"role": "user", "content": "hi"}])]


async def test_ollama_stream_error_line_raises():
    lines = json.dumps({"message": {"content": "안"}, "done": False}) + "\n" + json.dumps({"error": "oom"})
    llm = OllamaLLM("http://ollama.test", "m", transport=httpx.MockTransport(lambda r: httpx.Response(200, text=lines)))
    with pytest.raises(LLMError, match="oom"):
        [c async for c in llm.stream_chat([{"role": "user", "content": "hi"}])]


async def test_analyze_truncates_long_inputs_to_fit_context():
    llm = FakeLLM(json_responses=[{}])
    await analyze(llm, "뷁" * 50000, "갉" * 50000)
    _, user = llm.json_calls[0]
    assert user.count("뷁") == 9000 and user.count("갉") == 4500


async def test_ollama_uses_single_context_size():
    bodies = []

    def handler(req):
        bodies.append(json.loads(req.content))
        if bodies[-1]["stream"]:
            return httpx.Response(200, text=json.dumps({"message": {"content": "a"}, "done": True}))
        return httpx.Response(200, json={"message": {"content": "{}"}})

    llm = OllamaLLM("http://ollama.test", "m", transport=httpx.MockTransport(handler))
    await llm.chat_json("s", "u")
    [c async for c in llm.stream_chat([])]
    # same num_ctx for both, or Ollama reloads the model between calls
    assert {b["options"]["num_ctx"] for b in bodies} == {12288}
