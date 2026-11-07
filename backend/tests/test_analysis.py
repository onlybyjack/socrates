import pytest

from fakes import FakeLLM
from interview_agent.analysis import analyze, make_plan
from interview_agent.llm import LLMError, LLMUnavailable, MlxLLM, extract_json


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


class ScriptedMlx(MlxLLM):
    """MlxLLM with the model replaced by canned replies (no weights needed)."""

    def __init__(self, replies, chunks=None):
        super().__init__("test/model")
        self.replies = list(replies)
        self.chunks = chunks or []
        self.calls = []

    def _run(self, messages, temp, max_tokens, on_text=None, stop=None):
        self.calls.append((messages, temp))
        if on_text:
            for c in self.chunks:
                on_text(c)
                if stop is not None and stop.is_set():
                    break
            return "".join(self.chunks)
        return self.replies.pop(0)


async def test_mlx_chat_json_retries_once_and_tolerates_chatter():
    llm = ScriptedMlx(["not json", '<think></think>네, 결과입니다: ```json\n{"a": 1}\n```'])
    assert await llm.chat_json("sys", "user") == {"a": 1}
    assert len(llm.calls) == 2 and "JSON" in llm.calls[0][0][0]["content"]


async def test_mlx_chat_json_gives_up_after_two():
    with pytest.raises(LLMError):
        await ScriptedMlx(["nope", "still nope"]).chat_json("s", "u")


async def test_mlx_stream_chat_yields_chunks():
    llm = ScriptedMlx([], chunks=["안녕", "하세요"])
    out = [c async for c in llm.stream_chat([{"role": "user", "content": "hi"}])]
    assert "".join(out) == "안녕하세요"


async def test_mlx_missing_model_is_unavailable(monkeypatch):
    llm = MlxLLM("nobody/not-downloaded")
    monkeypatch.setattr(llm, "_local_path", lambda: None)
    assert (await llm.check()) == {"ok": True, "model_present": False}
    with pytest.raises(LLMUnavailable):
        await llm.chat_json("s", "u")


def test_extract_json():
    assert extract_json('앞말 {"a": "}{", "b": [1]} 뒷말') == {"a": "}{", "b": [1]}
    assert extract_json("{bad} {\"ok\": 1}") == {"ok": 1}
    assert extract_json("no json") is None
