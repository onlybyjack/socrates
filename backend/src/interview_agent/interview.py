"""Interview state machine: stages, main questions, follow-ups."""

import json
import re
from collections.abc import AsyncIterator

from . import prompts
from .llm import LLM, LLMError

STAGES = ["intro", "motivation", "experience", "technical", "closing"]
_MAIN_COUNTS = {"intro": 1, "motivation": 1, "experience": 3, "technical": 2}
_TAG_RE = re.compile(r"^\s*\[(FOLLOW_UP|NEXT)\]\s*")


class TagStripper:
    """Removes the leading [FOLLOW_UP]/[NEXT] tag from a token stream."""

    _DECIDE_AT = 20

    def __init__(self) -> None:
        self._buf = ""
        self._decided = False
        self._started = False  # has any non-whitespace text been emitted
        self.tag: str | None = None

    def feed(self, delta: str) -> str:
        if self._decided:
            if not self._started:
                delta = delta.lstrip()
                self._started = bool(delta)
            return delta
        self._buf += delta
        if "\n" not in self._buf and len(self._buf) < self._DECIDE_AT:
            if not _TAG_RE.match(self._buf):
                return ""
        return self._decide()

    def flush(self) -> str:
        return "" if self._decided else self._decide()

    def _decide(self) -> str:
        self._decided = True
        m = _TAG_RE.match(self._buf)
        out = self._buf[m.end():] if m else self._buf
        if m:
            self.tag = m.group(1)
        out = out.lstrip()
        self._started = bool(out)
        self._buf = ""
        return out


class Orchestrator:
    def __init__(self, llm: LLM, analysis: dict, plan: dict, max_follow_ups: int = 2):
        self.llm = llm
        self.analysis = analysis
        self.plan = plan
        self.max_follow_ups = max_follow_ups
        self.stage = "intro"
        self.main_index = 0  # number of main questions asked in the current stage
        self.follow_ups = 0
        self.finished = False
        self.last_kind = "other"
        self.history: list[dict] = []
        job = analysis.get("job", {}) or {}
        self._company = job.get("company") or "지원한 회사"
        self._role = job.get("role") or "지원 직무"
        self._system = prompts.INTERVIEWER_SYSTEM.format(
            company=self._company,
            role=self._role,
            analysis=json.dumps(analysis, ensure_ascii=False),
        )

    # ---- public API -------------------------------------------------
    async def opening(self) -> AsyncIterator[str]:
        self.stage, self.main_index, self.follow_ups = "intro", 1, 0
        self.last_kind = "main"
        async for chunk in self._speak(prompts.OPENING_INSTRUCTION.format(company=self._company, role=self._role)):
            yield chunk

    async def respond(self, answer: str, note: str = "", preface: str = "") -> AsyncIterator[str]:
        """`note`: extra memo for this turn only. `preface`: words said before the model's reply
        (e.g. "Sentry 말씀하신 거군요.")."""
        if self.finished:
            return
        if not answer.strip():
            self.last_kind = "repeat"
            yield prompts.REPEAT_PROMPT
            return
        self.history.append({"role": "user", "content": answer.strip()})

        can_follow = self.follow_ups < self.max_follow_ups
        next_stage, next_index = self._next_target()
        next_desc = self._describe(next_stage, next_index)
        if can_follow:
            instruction = prompts.DECIDE_INSTRUCTION.format(
                stage_name=prompts.STAGE_NAMES[self.stage],
                topic=self._current_topic(),
                rule=f"이 주제의 꼬리 질문은 {self.follow_ups}/{self.max_follow_ups}번 했습니다.",
                next_desc=next_desc,
            )
        else:
            instruction = prompts.FORCE_NEXT_INSTRUCTION.format(next_desc=next_desc)

        if note:
            instruction = f"{instruction}\n\n{note}"
        stripper = TagStripper()
        async for chunk in self._speak(instruction, stripper, preface):
            yield chunk

        if can_follow and stripper.tag == "FOLLOW_UP":
            self.follow_ups += 1
            self.last_kind = "follow_up"
        else:
            self.stage, self.main_index, self.follow_ups = next_stage, next_index, 0
            # No reverse Q&A: the model cannot state real facts about the company, so after the
            # last technical question the interviewer just thanks the candidate and ends.
            self.last_kind = "other" if next_stage == "closing" else "main"
            if next_stage == "closing":
                self.finished = True

    async def end_early(self) -> AsyncIterator[str]:
        self.stage = "closing"
        self.last_kind = "other"
        async for chunk in self._speak(prompts.CLOSING_INSTRUCTION):
            yield chunk
        self.finished = True

    # ---- internals --------------------------------------------------
    def _next_target(self) -> tuple[str, int]:
        if self.main_index < _MAIN_COUNTS.get(self.stage, 0):
            return self.stage, self.main_index + 1
        nxt = STAGES[STAGES.index(self.stage) + 1]
        return nxt, 1

    def _topic(self, stage: str, index: int) -> dict:
        items = self.plan.get(stage) or []
        if 1 <= index <= len(items):
            return items[index - 1]
        return {"topic": prompts.STAGE_NAMES.get(stage, stage), "intent": ""}

    def _current_topic(self) -> str:
        if self.stage in ("experience", "technical"):
            return self._topic(self.stage, self.main_index)["topic"]
        return prompts.STAGE_NAMES[self.stage]

    def _describe(self, stage: str, index: int) -> str:
        desc = prompts.NEXT_DESC[stage]
        if stage in ("experience", "technical"):
            t = self._topic(stage, index)
            desc = desc.format(topic=t["topic"], intent=t.get("intent", ""))
        return desc

    def _messages(self, instruction: str) -> list[dict]:
        msgs = [{"role": "system", "content": self._system}] + [dict(m) for m in self.history]
        if msgs[-1]["role"] == "user":
            msgs[-1]["content"] = f"{msgs[-1]['content']}\n\n{instruction}"
        else:
            msgs.append({"role": "user", "content": instruction})
        return msgs

    async def _speak(self, instruction: str, stripper: TagStripper | None = None, preface: str = "") -> AsyncIterator[str]:
        stripper = stripper or TagStripper()
        said = []
        if preface:
            said.append(preface)
            yield preface
        async for delta in self.llm.stream_chat(self._messages(instruction)):
            out = stripper.feed(delta)
            if out:
                said.append(out)
                yield out
        tail = stripper.flush()
        if tail:
            said.append(tail)
            yield tail
        text = "".join(said).strip()
        if not text:
            # Raise before the caller advances any state, so a planned question is never skipped.
            raise LLMError("면접관 응답이 비어 있어요.")
        self.history.append({"role": "assistant", "content": text})
