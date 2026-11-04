"""Text-mode interview in the terminal (for development and smoke tests).

Usage:
  uv run python -m interview_agent.cli --resume resume.pdf [--resume more.md] (--job-url URL | --job-file job.txt)
  Add --answers answers.txt to feed answers non-interactively (one per line).
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from .analysis import analyze, make_plan
from .config import get_settings
from .ingest import combine_sources, extract_text, fetch_job_posting
from .interview import Orchestrator
from .llm import OllamaLLM
from .report import make_report


async def _say(agen) -> str:
    t0, first, parts = time.perf_counter(), None, []
    print("\n🧑‍💼 면접관: ", end="", flush=True)
    async for chunk in agen:
        if first is None:
            first = time.perf_counter() - t0
        parts.append(chunk)
        print(chunk, end="", flush=True)
    print(f"\n   (첫 토큰 {first or 0:.1f}s, 전체 {time.perf_counter() - t0:.1f}s)")
    return "".join(parts)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="append", required=True)
    ap.add_argument("--job-url")
    ap.add_argument("--job-file")
    ap.add_argument("--answers")
    args = ap.parse_args()

    s = get_settings()
    llm = OllamaLLM(s.ollama_url, s.llm_model)
    source = combine_sources([(Path(p).name, extract_text(p, Path(p).read_bytes())) for p in args.resume])
    if args.job_file:
        job = Path(args.job_file).read_text()
    else:
        job = await fetch_job_posting(args.job_url) or ""
        if not job:
            sys.exit("공고 본문을 가져오지 못했어요. --job-file로 텍스트를 넣어주세요.")

    t0 = time.perf_counter()
    analysis = await analyze(llm, source, job)
    plan = await make_plan(llm, analysis)
    print(f"[분석 {time.perf_counter() - t0:.1f}s]")
    print(json.dumps({"analysis": analysis, "plan": plan}, ensure_ascii=False, indent=2))

    scripted = Path(args.answers).read_text().splitlines() if args.answers else None
    orch = Orchestrator(llm, analysis, plan)
    turns = []
    q = await _say(orch.opening())
    turns.append({"role": "interviewer", "text": q, "stage": orch.stage, "kind": orch.last_kind})
    while not orch.finished:
        if scripted is not None:
            if not scripted:
                break
            ans = scripted.pop(0)
            print(f"\n🙋 나: {ans}")
        else:
            ans = input("\n🙋 나: ")
            if ans.strip() == "/end":
                q = await _say(orch.end_early())
                turns.append({"role": "interviewer", "text": q, "stage": orch.stage, "kind": orch.last_kind})
                break
        stage_before = orch.stage
        turns.append({"role": "candidate", "text": ans, "stage": stage_before, "kind": "answer"})
        q = await _say(orch.respond(ans))
        turns.append({"role": "interviewer", "text": q, "stage": orch.stage, "kind": orch.last_kind})

    print("\n[리포트 생성 중...]")
    report = await make_report(llm, analysis, turns)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
