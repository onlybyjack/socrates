"""Resume ↔ job posting analysis and interview plan."""

import json

from . import prompts
from .llm import LLM

PLAN_COUNTS = {"experience": 3, "technical": 2}
_MAX_SOURCE_CHARS = 24000
_MAX_JOB_CHARS = 12000


def _list(v) -> list:
    return v if isinstance(v, list) else []


def _dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def _normalize(raw: dict) -> dict:
    job, cand, match = _dict(raw.get("job")), _dict(raw.get("candidate")), _dict(raw.get("match"))
    return {
        "job": {
            "company": str(job.get("company") or ""),
            "role": str(job.get("role") or ""),
            "required": _list(job.get("required")),
            "preferred": _list(job.get("preferred")),
            "duties": _list(job.get("duties")),
        },
        "candidate": {
            "summary": str(cand.get("summary") or ""),
            "experiences": _list(cand.get("experiences")),
            "skills": _list(cand.get("skills")),
        },
        "match": {
            "strengths": _list(match.get("strengths")),
            "gaps": _list(match.get("gaps")),
            "probes": _list(match.get("probes")),
        },
    }


async def analyze(llm: LLM, source_text: str, job_text: str) -> dict:
    if not source_text.strip():
        raise ValueError("이력서에서 텍스트를 찾지 못했어요. 스캔한 이미지 PDF라면 텍스트가 있는 PDF나 TXT로 올려주세요.")
    if not job_text.strip():
        raise ValueError("채용 공고 내용이 비어 있어요. 공고 텍스트를 붙여넣어 주세요.")
    user = prompts.ANALYSIS_USER.format(
        job_text=job_text[:_MAX_JOB_CHARS], source_text=source_text[:_MAX_SOURCE_CHARS]
    )
    return _normalize(await llm.chat_json(prompts.ANALYSIS_SYSTEM, user))


def _topics(items, fallback: list[dict], n: int) -> list[dict]:
    out = []
    for it in _list(items):
        if isinstance(it, dict) and str(it.get("topic") or "").strip():
            out.append({"topic": str(it["topic"]), "intent": str(it.get("intent") or "")})
    for fb in fallback:
        if len(out) >= n:
            break
        out.append(fb)
    return out[:n]


async def make_plan(llm: LLM, analysis: dict) -> dict:
    raw = await llm.chat_json(prompts.PLAN_SYSTEM, json.dumps(analysis, ensure_ascii=False))
    match = _dict(analysis.get("match"))
    probes = [
        {"topic": str(p.get("topic")), "intent": str(p.get("why") or "")}
        for p in _list(match.get("probes"))
        if isinstance(p, dict) and p.get("topic")
    ]
    gaps = [
        {"topic": str(g.get("point")), "intent": "공고 요구 역량 검증"}
        for g in _list(match.get("gaps"))
        if isinstance(g, dict) and g.get("point")
    ]
    exp_fb = probes + [{"topic": "가장 자신 있는 프로젝트", "intent": "역할과 의사결정 깊이 확인"}] * 3
    tech_fb = gaps + [{"topic": "직무 핵심 역량", "intent": "공고 요구 역량 검증"}] * 2
    return {
        "experience": _topics(raw.get("experience"), exp_fb, PLAN_COUNTS["experience"]),
        "technical": _topics(raw.get("technical"), tech_fb, PLAN_COUNTS["technical"]),
    }
