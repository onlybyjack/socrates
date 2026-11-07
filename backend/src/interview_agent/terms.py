"""Fix tech names that STT wrote phonetically ("센터리" -> "Sentry") before the interviewer reads the answer."""

import logging
import re

from . import prompts
from .llm import LLM

log = logging.getLogger("interview_agent")
_HANGUL = re.compile(r"[가-힣]")
_LATIN = re.compile(r"[A-Za-z]")


async def fix_terms(llm: LLM, text: str, vocabulary: list[str] | None = None) -> tuple[str, list[dict]]:
    """Returns (corrected text, fixes). `vocabulary`: likely terms (from the resume/job) to match against.
    Never raises: on any failure the answer passes through unchanged."""
    if not _HANGUL.search(text):
        return text, []
    user = text
    if vocabulary:
        user = f"Terms this candidate is likely to mention: {', '.join(vocabulary[:60])}\n\nAnswer:\n{text}"
    try:
        raw = await llm.chat_json(prompts.TERM_FIX_SYSTEM, user)
    except Exception as e:
        log.warning("term fix failed: %s", e)
        return text, []
    fixes, seen = [], set()
    for f in raw.get("fixes") or []:
        if not isinstance(f, dict):
            continue
        heard, meant = str(f.get("heard") or "").strip(), str(f.get("meant") or "").strip()
        # Only Hangul -> Latin name swaps of words that really appear; anything else is the model guessing.
        if not heard or heard in seen or heard not in text or not _HANGUL.search(heard):
            continue
        if not _LATIN.search(meant) or len(meant) > 40:
            continue
        seen.add(heard)
        fixes.append({"heard": heard, "meant": meant, "odd": bool(f.get("odd"))})
    out = text
    for f in sorted(fixes, key=lambda f: -len(f["heard"])):
        out = out.replace(f["heard"], f["meant"])
    return out, fixes


def confirm_note(fixes: list[dict], already: set[str]) -> tuple[str, str]:
    """(what the interviewer says first, memo for the model). At most one per turn, only for odd
    spellings, never the same term twice."""
    for f in fixes:
        if f["odd"] and f["meant"].lower() not in already:
            already.add(f["meant"].lower())
            return prompts.TERM_CONFIRM_SAY.format(meant=f["meant"]), prompts.TERM_CONFIRM_NOTE.format(meant=f["meant"])
    return "", ""
