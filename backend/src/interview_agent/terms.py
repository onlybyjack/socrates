"""Fix tech names that STT wrote phonetically ("센터리" -> "Sentry") before the interviewer reads the answer."""

import logging
import re

from . import prompts
from .llm import LLM

log = logging.getLogger("interview_agent")
_HANGUL = re.compile(r"[가-힣]")
_MAX_NAMES = 80
# The model sometimes includes the particle ("지에이포로"); a name never ends in these, so keep them in the text.
_PARTICLES = ("으로", "에서", "로", "를", "을")


def _strip_particle(heard: str) -> str:
    for p in _PARTICLES:
        if heard.endswith(p) and len(heard) > len(p) + 1:
            return heard[: -len(p)]
    return heard


async def fix_terms(llm: LLM, text: str, vocabulary: list[str] | None = None) -> tuple[str, list[dict]]:
    """Returns (corrected text, fixes). Only names from `vocabulary` (the candidate's own materials and
    the job posting) can be restored, so it works the same for any profession and never invents names.
    Never raises: on any failure the answer passes through unchanged."""
    if not vocabulary or not _HANGUL.search(text):
        return text, []
    allowed = {v.lower(): v for v in vocabulary}
    user = f"Names list: {', '.join(vocabulary[:_MAX_NAMES])}\n\nAnswer:\n{text}"
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
        heard = _strip_particle(heard)
        # Only Hangul -> Latin name swaps of words that really appear; anything else is the model guessing.
        if not heard or heard in seen or heard not in text or not _HANGUL.search(heard):
            continue
        if meant.lower() not in allowed:
            continue
        meant = allowed[meant.lower()]
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
