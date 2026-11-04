from fakes import FakeLLM
from interview_agent.interview import Orchestrator, TagStripper
from interview_agent.prompts import REPEAT_PROMPT

ANALYSIS = {"job": {"company": "키코", "role": "백엔드 개발자"}, "candidate": {}, "match": {}}
PLAN = {
    "experience": [{"topic": f"경험{i}", "intent": "i"} for i in range(3)],
    "technical": [{"topic": f"기술{i}", "intent": "i"} for i in range(2)],
}


async def collect(agen) -> str:
    return "".join([c async for c in agen])


def make(llm, **kw):
    return Orchestrator(llm, ANALYSIS, PLAN, **kw)


async def test_opening_is_intro_main():
    llm = FakeLLM(stream_responses=["[NEXT]\n안녕하세요. 자기소개 부탁드립니다."])
    o = make(llm)
    text = await collect(o.opening())
    assert text == "안녕하세요. 자기소개 부탁드립니다."
    assert o.stage == "intro" and o.last_kind == "main"


async def test_empty_answer_asks_repeat_no_state_change():
    o = make(FakeLLM())
    await collect(o.opening())
    before = (o.stage, o.main_index, o.follow_ups, len(o.history))
    text = await collect(o.respond("   "))
    assert text == REPEAT_PROMPT
    assert (o.stage, o.main_index, o.follow_ups, len(o.history)) == before
    assert o.last_kind == "repeat"


async def test_tag_stripped_from_output():
    llm = FakeLLM(stream_responses=["[NEXT]\n인사", "[FOLLOW_UP]\n그때 왜 그렇게 하셨나요?"])
    o = make(llm)
    await collect(o.opening())
    text = await collect(o.respond("저는 백엔드 개발자입니다."))
    assert text == "그때 왜 그렇게 하셨나요?"
    assert o.last_kind == "follow_up" and o.follow_ups == 1 and o.stage == "intro"


async def test_missing_tag_treated_as_next():
    llm = FakeLLM(stream_responses=["[NEXT]\n인사", "지원 동기를 말씀해 주세요."])
    o = make(llm)
    await collect(o.opening())
    text = await collect(o.respond("자기소개입니다."))
    assert text == "지원 동기를 말씀해 주세요."
    assert o.stage == "motivation" and o.last_kind == "main"


async def test_follow_up_limit_forces_next():
    llm = FakeLLM(default_stream="[FOLLOW_UP]\n더 자세히요?")
    o = make(llm, max_follow_ups=2)
    await collect(o.opening())
    await collect(o.respond("a1"))
    await collect(o.respond("a2"))
    assert o.follow_ups == 2 and o.stage == "intro"
    await collect(o.respond("a3"))
    assert o.stage == "motivation" and o.follow_ups == 0
    # The forced call used the force-next instruction
    assert "다음으로 넘어갑니다" in llm.stream_calls[-1][-1]["content"]


async def test_instruction_not_stored_in_history():
    llm = FakeLLM()
    o = make(llm)
    await collect(o.opening())
    await collect(o.respond("제 답변"))
    assert o.history[1] == {"role": "user", "content": "제 답변"}
    assert all("[진행 지시]" not in m["content"] for m in o.history)


async def test_full_run_reaches_finished():
    o = make(FakeLLM())  # always [NEXT]
    stages = []
    await collect(o.opening())
    stages.append(o.stage)
    for _ in range(20):
        if o.finished:
            break
        await collect(o.respond("궁금한 거 없습니다" if o.stage == "reverse_qa" else "답변입니다"))
        stages.append(o.stage)
    assert o.finished and o.stage == "closing"
    order = ["intro", "motivation", "experience", "technical", "reverse_qa", "closing"]
    seen = [s for i, s in enumerate(stages) if i == 0 or stages[i - 1] != s]
    assert seen == order
    assert stages.count("experience") == 3 and stages.count("technical") == 2


async def test_reverse_qa_question_then_none_goes_closing():
    o = make(FakeLLM())
    o.stage, o.main_index = "reverse_qa", 1
    await collect(o.respond("팀 규모가 어떻게 되나요?"))
    assert o.stage == "reverse_qa" and not o.finished
    await collect(o.respond("아니요, 없어요."))
    assert o.finished and o.stage == "closing"


async def test_reverse_qa_max_then_finish():
    o = make(FakeLLM(), max_reverse=2)
    o.stage, o.main_index = "reverse_qa", 1
    await collect(o.respond("질문1?"))
    await collect(o.respond("질문2?"))
    assert o.finished


async def test_end_early():
    o = make(FakeLLM(stream_responses=["[NEXT]\n인사", "[NEXT]\n오늘 감사했습니다."]))
    await collect(o.opening())
    text = await collect(o.end_early())
    assert text == "오늘 감사했습니다." and o.finished and o.stage == "closing"


def test_tag_stripper_same_line_and_split_chunks():
    t = TagStripper()
    assert t.feed("[FOL") == ""
    assert t.feed("LOW_UP] 왜") == "왜"
    assert t.feed("요?") == "요?"
    assert t.tag == "FOLLOW_UP"


def test_tag_stripper_short_untagged_flush():
    t = TagStripper()
    assert t.feed("네.") == ""
    assert t.flush() == "네."
    assert t.tag is None


def test_tag_stripper_drops_whitespace_after_early_tag():
    t = TagStripper()
    out = t.feed("[NEXT]") + t.feed("  \n") + t.feed("안녕하세요.")
    assert out == "안녕하세요."
    assert t.tag == "NEXT"


async def test_empty_llm_turn_raises_and_keeps_stage():
    import pytest
    from interview_agent.llm import LLMError

    o = make(FakeLLM(stream_responses=["[NEXT]\n인사", "[NEXT]\n"]))
    await collect(o.opening())
    with pytest.raises(LLMError):
        await collect(o.respond("답변"))
    assert o.stage == "intro" and o.main_index == 1


async def test_repeat_prompt_kind_is_repeat():
    o = make(FakeLLM())
    await collect(o.opening())
    await collect(o.respond(""))
    assert o.last_kind == "repeat"
