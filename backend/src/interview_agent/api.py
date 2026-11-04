"""FastAPI app: REST for setup/analysis/history, WebSocket for the live interview."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .analysis import analyze, make_plan
from .ingest import UnsupportedFile, combine_sources, extract_text, fetch_job_posting
from .interview import Orchestrator
from .llm import LLM, LLMError, LLMUnavailable
from .report import make_report
from .sentences import SentenceSplitter
from .store import Store
from .stt import STT
from .tts import TTSEngine

log = logging.getLogger("interview_agent")

OLLAMA_DOWN = "Ollama에 연결할 수 없거나 모델이 없어요. Ollama를 실행하고 모델을 받아주세요 (ollama pull qwen3:8b)."


class JobText(BaseModel):
    text: str


def create_app(llm: LLM, stt: STT, tts: TTSEngine, store: Store) -> FastAPI:
    app = FastAPI(title="interview-agent")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["tauri://localhost", "http://tauri.localhost", "http://localhost:1420"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _session(sid: str) -> dict:
        s = store.get_session(sid)
        if s is None:
            raise HTTPException(404, "세션을 찾을 수 없어요.")
        return s

    # ---------------- REST ----------------
    @app.get("/api/health")
    async def health():
        chk = await llm.check() if hasattr(llm, "check") else {"ok": True, "model_present": True}
        return {
            "ollama": chk["ok"],
            "model_present": chk["model_present"],
            "model": getattr(llm, "model", ""),
            "stt": True,
            "stt_ready": getattr(stt, "ready", True),
            "tts": tts.available(),
        }

    @app.post("/api/sessions")
    async def create_session(
        files: list[UploadFile] = File(...),
        job_url: str | None = Form(None),
        job_text: str | None = Form(None),
    ):
        items = []
        for f in files:
            try:
                items.append((f.filename or "file", extract_text(f.filename or "", await f.read())))
            except UnsupportedFile as e:
                raise HTTPException(400, str(e))
            except Exception as e:  # corrupt PDF etc.
                raise HTTPException(400, f"{f.filename} 파일을 읽지 못했어요: {e}")
        if not any(t.strip() for _, t in items):
            names = ", ".join(n for n, _ in items)
            raise HTTPException(
                400, f"올린 파일({names})에서 텍스트를 찾지 못했어요. 스캔 이미지 PDF라면 텍스트가 있는 PDF나 TXT로 올려주세요."
            )
        job = (job_text or "").strip() or None
        if job is None and job_url:
            job = await fetch_job_posting(job_url)
        sid = store.create_session(combine_sources(items), job_url, job)
        return {
            "session_id": sid,
            "files": [{"name": n, "chars": len(t)} for n, t in items],
            "job_text_ok": job is not None,
            "job_chars": len(job or ""),
        }

    @app.post("/api/sessions/{sid}/job_text")
    async def set_job_text(sid: str, body: JobText):
        _session(sid)
        if not body.text.strip():
            raise HTTPException(400, "공고 텍스트가 비어 있어요.")
        store.update_session(sid, job_text=body.text.strip())
        return {"ok": True}

    @app.post("/api/sessions/{sid}/analyze")
    async def analyze_session(sid: str):
        s = _session(sid)
        if not (s["job_text"] or "").strip():
            raise HTTPException(409, "공고 텍스트가 없어요. 공고를 붙여넣어 주세요.")
        try:
            analysis = await analyze(llm, s["source_text"], s["job_text"])
            plan = await make_plan(llm, analysis)
        except LLMUnavailable:
            raise HTTPException(503, OLLAMA_DOWN)
        except LLMError as e:
            raise HTTPException(502, f"분석 결과를 만들지 못했어요. 다시 시도해 주세요. ({e})")
        except ValueError as e:
            raise HTTPException(400, str(e))
        store.update_session(sid, analysis=analysis, plan=plan)
        return {"analysis": analysis, "plan": plan}

    @app.get("/api/sessions")
    async def list_sessions():
        return store.list_sessions()

    @app.get("/api/sessions/{sid}")
    async def get_session(sid: str):
        s = _session(sid)
        s.pop("source_text", None)
        return {**s, "turns": store.get_turns(sid)}

    @app.post("/api/sessions/{sid}/report")
    async def build_report(sid: str):
        s = _session(sid)
        try:
            rep = await make_report(llm, s["analysis"] or {}, store.get_turns(sid))
        except LLMUnavailable:
            raise HTTPException(503, OLLAMA_DOWN)
        except LLMError as e:
            raise HTTPException(502, f"리포트를 만들지 못했어요. ({e})")
        store.update_session(sid, report=rep)
        return rep

    # ---------------- WebSocket ----------------
    @app.websocket("/ws/interview/{sid}")
    async def interview_ws(ws: WebSocket, sid: str):
        await ws.accept()
        s = store.get_session(sid)
        if not s or not s["analysis"] or not s["plan"]:
            await ws.send_json({"type": "error", "message": "먼저 분석을 완료해 주세요."})
            await ws.close()
            return
        orch = Orchestrator(llm, s["analysis"], s["plan"])
        send_lock = asyncio.Lock()

        async def send_json(obj: dict) -> None:
            async with send_lock:
                await ws.send_json(obj)

        async def run_turn(agen: AsyncIterator[str]) -> None:
            await send_json({"type": "state", "stage": orch.stage, "speaking": True})
            sentences: asyncio.Queue[str | None] = asyncio.Queue()

            async def tts_worker() -> None:
                seq = 0
                while (sentence := await sentences.get()) is not None:
                    try:
                        audio, mime = await tts.synthesize(sentence)
                    except Exception as e:  # keep the interview going with subtitles only
                        log.warning("TTS failed: %s", e)
                        continue
                    async with send_lock:
                        await ws.send_json({"type": "audio", "seq": seq, "mime": mime, "text": sentence})
                        await ws.send_bytes(audio)
                    seq += 1

            worker = asyncio.create_task(tts_worker())
            splitter, parts = SentenceSplitter(), []
            try:
                async for chunk in agen:
                    parts.append(chunk)
                    await send_json({"type": "question_text_delta", "text": chunk})
                    for sentence in splitter.feed(chunk):
                        sentences.put_nowait(sentence)
                for sentence in splitter.flush():
                    sentences.put_nowait(sentence)
            finally:
                sentences.put_nowait(None)
                await worker
            text = "".join(parts).strip()
            if text:
                store.add_turn(sid, "interviewer", text, orch.stage, orch.last_kind)
            await send_json({"type": "turn_done", "stage": orch.stage, "finished": orch.finished, "text": text})
            if orch.finished:
                await send_json({"type": "reporting"})
                try:
                    rep = await make_report(llm, s["analysis"], store.get_turns(sid))
                    store.update_session(sid, report=rep)
                except Exception as e:  # never leave the UI waiting on "reporting"
                    log.exception("report failed")
                    await send_json({"type": "error", "message": f"피드백을 만들지 못했어요. 기록 화면에서 다시 만들 수 있어요. ({e})"})
                await send_json({"type": "finished", "session_id": sid})

        async def handle_answer(text: str) -> None:
            text = text.strip()
            if text:
                await send_json({"type": "transcript", "role": "candidate", "text": text})
                store.add_turn(sid, "candidate", text, orch.stage, "answer")
            await run_turn(orch.respond(text))

        try:
            while True:
                msg = await ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                try:
                    if msg.get("bytes") is not None:
                        if orch.finished:
                            continue
                        await send_json({"type": "state", "stage": orch.stage, "transcribing": True})
                        try:
                            heard = await stt.transcribe(msg["bytes"])
                        except Exception as e:
                            log.exception("STT failed")
                            await send_json({"type": "error", "message": f"받아쓰기에 실패했어요. 다시 말하거나 답변을 입력해 주세요. ({e})"})
                            continue
                        await handle_answer(heard)
                        continue
                    data = json.loads(msg.get("text") or "{}")
                    kind = data.get("type")
                    if kind == "start" and not orch.history:
                        await run_turn(orch.opening())
                    elif kind == "text_answer" and not orch.finished:
                        await handle_answer(str(data.get("text", "")))
                    elif kind == "end_interview" and not orch.finished:
                        await run_turn(orch.end_early())
                except LLMUnavailable:
                    await send_json({"type": "error", "message": OLLAMA_DOWN})
                except LLMError as e:
                    await send_json({"type": "error", "message": f"면접관 응답을 만들지 못했어요: {e}"})
                except WebSocketDisconnect:
                    raise
                except Exception as e:  # keep the interview alive; the UI returns to listening
                    log.exception("interview turn failed")
                    await send_json({"type": "error", "message": f"문제가 생겼어요. 다시 답변해 주세요. ({e})"})
        except (WebSocketDisconnect, RuntimeError) as e:
            if isinstance(e, RuntimeError) and "disconnect" not in str(e).lower():
                raise

    return app
