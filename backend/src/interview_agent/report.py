"""Post-interview feedback report."""

import json

from . import prompts
from .llm import LLM

_EMPTY_OVERALL = {"summary": "", "strengths": [], "improvements": [], "next_topics": []}


def pair_questions(turns: list[dict]) -> list[dict]:
    """Pair each main/follow-up interviewer turn with the candidate answer that follows it."""
    pairs: list[dict] = []
    pending: dict | None = None
    for t in turns:
        if t["role"] == "interviewer":
            if t["kind"] == "repeat":  # "please say that again" keeps the open question open
                continue
            pending = (
                {"question": t["text"], "answer": "", "kind": t["kind"]}
                if t["kind"] in ("main", "follow_up")
                else None
            )
        elif t["role"] == "candidate" and pending is not None:
            pending["answer"] = t["text"]
            pairs.append(pending)
            pending = None
    return pairs


def _str(v) -> str:
    return v if isinstance(v, str) else ""


def _strs(v) -> list[str]:
    return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


async def make_report(llm: LLM, analysis: dict, turns: list[dict]) -> dict:
    pairs = pair_questions(turns)
    if not pairs:
        return {"questions": [], "overall": dict(_EMPTY_OVERALL)}
    transcript = "\n\n".join(
        f"[{i}] 질문: {p['question']}\n답변: {p['answer']}" for i, p in enumerate(pairs, start=1)
    )
    user = f"[면접 준비 분석]\n{json.dumps(analysis, ensure_ascii=False)}\n\n[면접 기록]\n{transcript}"
    raw = await llm.chat_json(prompts.REPORT_SYSTEM, user)

    by_index = {}
    for q in raw.get("questions") or []:
        if isinstance(q, dict) and isinstance(q.get("index"), int):
            by_index[q["index"]] = q
    questions = []
    for i, p in enumerate(pairs, start=1):
        fb = by_index.get(i, {})
        questions.append(
            {
                "question": p["question"],
                "answer": p["answer"],
                "good": _str(fb.get("good")),
                "improve": _str(fb.get("improve")),
                "better_direction": _str(fb.get("better_direction")),
            }
        )
    ov = raw.get("overall") if isinstance(raw.get("overall"), dict) else {}
    overall = {
        "summary": _str(ov.get("summary")),
        "strengths": _strs(ov.get("strengths")),
        "improvements": _strs(ov.get("improvements")),
        "next_topics": _strs(ov.get("next_topics")),
    }
    return {"questions": questions, "overall": overall}
