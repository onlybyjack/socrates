from fakes import FakeLLM
from interview_agent.report import make_report, pair_questions

TURNS = [
    {"role": "interviewer", "text": "안녕하세요, 자기소개 부탁드려요.", "stage": "intro", "kind": "main"},
    {"role": "candidate", "text": "저는 5년차 백엔드입니다.", "stage": "intro", "kind": "answer"},
    {"role": "interviewer", "text": "죄송해요, 잘 못 들었어요.", "stage": "intro", "kind": "other"},
    {"role": "interviewer", "text": "왜 Kafka를 쓰셨나요?", "stage": "experience", "kind": "follow_up"},
    {"role": "candidate", "text": "처리량 때문입니다.", "stage": "experience", "kind": "answer"},
    {"role": "interviewer", "text": "궁금한 점 있으세요?", "stage": "reverse_qa", "kind": "other"},
    {"role": "candidate", "text": "없습니다.", "stage": "reverse_qa", "kind": "answer"},
]


def test_pair_questions_only_main_and_follow_up():
    pairs = pair_questions(TURNS)
    assert pairs == [
        {"question": "안녕하세요, 자기소개 부탁드려요.", "answer": "저는 5년차 백엔드입니다.", "kind": "main"},
        {"question": "왜 Kafka를 쓰셨나요?", "answer": "처리량 때문입니다.", "kind": "follow_up"},
    ]


async def test_report_pairs_questions_with_answers():
    llm = FakeLLM(json_responses=[{
        "questions": [
            {"index": 1, "good": "g1", "improve": "i1", "better_direction": "b1"},
            {"index": 2, "good": "g2", "improve": "i2", "better_direction": "b2"},
        ],
        "overall": {"summary": "s", "strengths": ["a", "b", "c"], "improvements": ["x", "y", "z"], "next_topics": ["t"]},
    }])
    rep = await make_report(llm, {"job": {}}, TURNS)
    assert [q["question"] for q in rep["questions"]] == ["안녕하세요, 자기소개 부탁드려요.", "왜 Kafka를 쓰셨나요?"]
    assert rep["questions"][1]["answer"] == "처리량 때문입니다."
    assert rep["questions"][1]["good"] == "g2"
    assert rep["overall"]["strengths"] == ["a", "b", "c"]
    assert "처리량 때문입니다." in llm.json_calls[0][1]


async def test_report_fills_missing_feedback():
    llm = FakeLLM(json_responses=[{"questions": [{"index": 2, "good": "g2"}]}])
    rep = await make_report(llm, {}, TURNS)
    assert rep["questions"][0]["good"] == "" and rep["questions"][0]["better_direction"] == ""
    assert rep["questions"][1]["good"] == "g2"
    assert rep["overall"] == {"summary": "", "strengths": [], "improvements": [], "next_topics": []}


async def test_report_with_no_questions_skips_llm():
    llm = FakeLLM()
    rep = await make_report(llm, {}, [])
    assert rep["questions"] == [] and llm.json_calls == []


def test_pair_questions_repeat_keeps_pending():
    turns = [
        {"role": "interviewer", "text": "Q1", "stage": "intro", "kind": "main"},
        {"role": "interviewer", "text": "다시 말씀해 주시겠어요?", "stage": "intro", "kind": "repeat"},
        {"role": "candidate", "text": "A1", "stage": "intro", "kind": "answer"},
    ]
    assert pair_questions(turns) == [{"question": "Q1", "answer": "A1", "kind": "main"}]
