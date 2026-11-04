import io

import httpx
import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from interview_agent.ingest import (
    UnsupportedFile,
    combine_sources,
    extract_text,
    fetch_job_posting,
)


def _pdf_with_text(text: str) -> bytes:
    w = PdfWriter()
    page = w.add_blank_page(width=300, height=200)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): w._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode())
    page[NameObject("/Contents")] = w._add_object(stream)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _blank_pdf() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=300, height=200)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_txt_utf8_and_cp949_fallback():
    assert extract_text("a.txt", "안녕".encode("utf-8")) == "안녕"
    assert extract_text("b.md", "경력기술서".encode("cp949")) == "경력기술서"


def test_pdf_text():
    assert "Hello" in extract_text("resume.PDF", _pdf_with_text("Hello"))


def test_image_only_pdf_returns_empty():
    assert extract_text("scan.pdf", _blank_pdf()) == ""


def test_unsupported_raises():
    with pytest.raises(UnsupportedFile):
        extract_text("photo.png", b"\x89PNG")


def _client(html: str, status: int = 200) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(status, text=html, headers={"content-type": "text/html"}))
    )


async def test_fetch_job_posting_short_returns_none():
    assert await fetch_job_posting("https://x.test/j", _client("<html><body><p>짧음</p></body></html>")) is None


async def test_fetch_job_posting_http_error_returns_none():
    assert await fetch_job_posting("https://x.test/j", _client("nope", 404)) is None


async def test_fetch_job_posting_extracts():
    para = "백엔드 개발자를 모집합니다. Python과 FastAPI 경험이 필요하며 대용량 트래픽 처리 경험을 우대합니다. " * 6
    html = f"<html><head><title>채용</title></head><body><nav>메뉴</nav><article><h1>백엔드 개발자</h1><p>{para}</p><p>{para}</p></article></body></html>"
    text = await fetch_job_posting("https://x.test/j", _client(html))
    assert text is not None and "FastAPI" in text


def test_combine_skips_empty():
    out = combine_sources([("a.pdf", "이력"), ("b.pdf", "  "), ("c.md", "포트폴리오")])
    assert out == "### 파일: a.pdf\n이력\n\n### 파일: c.md\n포트폴리오"
