from fakes import FakeLLM
from interview_agent.terms import confirm_note, fix_terms


async def test_fixes_phonetic_names_and_keeps_the_rest():
    llm = FakeLLM(json_responses=[{"fixes": [
        {"heard": "센터리", "meant": "Sentry", "odd": True},
        {"heard": "슬랙", "meant": "Slack", "odd": False},
        {"heard": "없는말", "meant": "Ghost", "odd": True},     # not in the answer: ignored
        {"heard": "모니터링", "meant": "모니터링", "odd": False},  # not a Hangul->Latin swap: ignored
    ]}])
    text, fixes = await fix_terms(llm, "에러는 센터리로 모니터링했고 알림은 슬랙으로 받았습니다.")
    assert text == "에러는 Sentry로 모니터링했고 알림은 Slack으로 받았습니다."
    assert [f["meant"] for f in fixes] == ["Sentry", "Slack"]


async def test_llm_failure_passes_answer_through():
    class Boom(FakeLLM):
        async def chat_json(self, system, user):
            raise RuntimeError("down")

    assert await fix_terms(Boom(), "셀러리 썼어요") == ("셀러리 썼어요", [])


async def test_no_hangul_skips_llm():
    llm = FakeLLM()
    assert await fix_terms(llm, "OK") == ("OK", [])
    assert llm.json_calls == []


def test_confirm_only_odd_once_per_term():
    seen: set[str] = set()
    fixes = [{"heard": "슬랙", "meant": "Slack", "odd": False}, {"heard": "센터리", "meant": "Sentry", "odd": True}]
    say, note = confirm_note(fixes, seen)
    assert say == "Sentry 말씀하신 거군요. " and "반복하지" in note
    assert confirm_note(fixes, seen) == ("", "")
