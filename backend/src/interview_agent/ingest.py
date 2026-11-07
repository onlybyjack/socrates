"""Extract text from uploaded files and job posting URLs."""

import io

import httpx
import trafilatura
from pypdf import PdfReader

MIN_JOB_CHARS = 200
MIN_LINK_CHARS = 50
_UA = "interview-agent/0.1 (local mock interview app)"


class UnsupportedFile(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages).strip()
    if name.endswith((".txt", ".md")):
        for enc in ("utf-8", "cp949"):
            try:
                return data.decode(enc).strip()
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace").strip()
    raise UnsupportedFile(f"지원하지 않는 파일 형식이에요: {filename} (PDF, TXT, MD만 가능해요)")


async def fetch_job_posting(url: str, client: httpx.AsyncClient | None = None) -> str | None:
    return await fetch_page(url, MIN_JOB_CHARS, client)


async def fetch_link(url: str, client: httpx.AsyncClient | None = None) -> str | None:
    """A user's own page (GitHub, blog, portfolio). Shorter pages are still useful context."""
    return await fetch_page(url, MIN_LINK_CHARS, client)


async def fetch_page(url: str, min_chars: int, client: httpx.AsyncClient | None = None) -> str | None:
    own = client is None
    client = client or httpx.AsyncClient(timeout=15, follow_redirects=True, headers={"User-Agent": _UA})
    try:
        resp = await client.get(url)
        if resp.status_code >= 400:
            return None
        text = trafilatura.extract(resp.text, include_comments=False, include_tables=True) or ""
    except httpx.HTTPError:
        return None
    finally:
        if own:
            await client.aclose()
    text = text.strip()
    return text if len(text) >= min_chars else None


def combine_sources(items: list[tuple[str, str]]) -> str:
    """items: (name, text); names that are URLs are labelled as links."""
    def label(name: str) -> str:
        return f"링크: {name}" if name.startswith(("http://", "https://")) else f"파일: {name}"

    return "\n\n".join(f"### {label(name)}\n{text.strip()}" for name, text in items if text.strip())
