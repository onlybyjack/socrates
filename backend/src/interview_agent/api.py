"""FastAPI app: REST for setup/analysis/history, WebSocket for the live interview."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .analysis import analyze, make_plan
from .ingest import UnsupportedFile, combine_sources, extract_text, fetch_job_posting, fetch_link
from .interview import Orchestrator
from .llm import LLM, LLMError, LLMUnavailable
from .report import make_report
from .sentences import SentenceSplitter
from .store import Store
from .terms import confirm_note, fix_terms
from .stt import STT, vocabulary_hint, vocabulary_terms
from .tts import TTSEngine

log = logging.getLogger("interview_agent")

LLM_DOWN = "면접관 모델이 아직 준비되지 않았어요. 앱을 다시 열어 첫 실행 준비를 마쳐 주세요."


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

    pull_state: dict = {"status": "idle", "completed": 0, "total": 0, "message": ""}
    pull_tasks: set[asyncio.Task] = set()
    tts_tasks: set[asyncio.Task] = set()

    # Feedback is built in the background; the UI polls its status. Only running/failed jobs are kept.
    report_jobs: dict[str, dict] = {}
    report_tasks: set[asyncio.Task] = set()

    def _start_report(sid: str) -> dict:
        job = report_jobs.get(sid)
        if job and job["status"] == "running":
            return job
        report_jobs[sid] = {"status": "running", "message": ""}

        async def run() -> None:
            try:
                s = store.get_session(sid) or {}
                rep = await make_report(llm, s.get("analysis") or {}, store.get_turns(sid))
                store.update_session(sid, report=rep)
                report_jobs.pop(sid, None)
            except LLMUnavailable:
                report_jobs[sid] = {"status": "error", "message": LLM_DOWN}
            except Exception as e:
                log.exception("report failed")
                report_jobs[sid] = {"status": "error", "message": f"피드백을 만들지 못했어요. 다시 시도해 주세요. ({e})"}

        t = asyncio.create_task(run())
        report_tasks.add(t)
        t.add_done_callback(report_tasks.discard)
        return report_jobs[sid]

    def _report_status(sid: str, has_report: bool) -> dict:
        job = report_jobs.get(sid)
        if job:
            return dict(job)
        return {"status": "done" if has_report else "none", "message": ""}

    def _ensure_tts() -> None:
        """Retry the voice model download/load in the background if startup warmup failed."""
        warm = getattr(tts, "warmup", None)
        if warm is None or tts.available() or tts_tasks:
            return

        async def run() -> None:
            try:
                await warm()
            except Exception:
                log.exception("TTS warmup failed")

        t = asyncio.create_task(run())
        tts_tasks.add(t)
        t.add_done_callback(tts_tasks.discard)

    async def _run_pull() -> None:
        def progress(status: str, done: int, total: int) -> None:
            pull_state.update(message=status)
            if total:
                pull_state.update(completed=done, total=total)

        try:
            await llm.pull(progress)
            pull_state.update(status="done")
        except Exception as e:
            log.exception("model pull failed")
            pull_state.update(status="error", message=str(e))

    def _session(sid: str) -> dict:
        s = store.get_session(sid)
        if s is None:
            raise HTTPException(404, "세션을 찾을 수 없어요.")
        return s

    # ---------------- REST ----------------
    @app.get("/api/health")
    async def health():
        chk = await llm.check() if hasattr(llm, "check") else {"ok": True, "model_present": True}
        _ensure_tts()
        return {
            "llm": chk["ok"],
            "model_present": chk["model_present"],
            "model": getattr(llm, "model", ""),
            "stt": True,
            "stt_ready": getattr(stt, "ready", True),
            "tts": tts.available(),
            "pull": dict(pull_state),
        }

    @app.post("/api/model/pull")
    async def pull_model():
        if pull_state["status"] == "pulling":
            return dict(pull_state)
        chk = await llm.check()
        if chk["model_present"]:
            pull_state.update(status="done")
            return dict(pull_state)
        pull_state.update(status="pulling", completed=0, total=0, message="")
        task = asyncio.create_task(_run_pull())
        pull_tasks.add(task)
        task.add_done_callback(pull_tasks.discard)
        return dict(pull_state)

    @app.post("/api/sessions")
    async def create_session(
        files: list[UploadFile] = File([]),
        links: list[str] = Form([]),
        job_url: str | None = Form(None),
        job_text: str | None = Form(None),
    ):
        links = [u.strip() for u in links if u.strip()]
        if not files and not links:
            raise HTTPException(400, "이력서 파일이나 내 자료 링크를 하나 이상 넣어 주세요.")
        for u in links:
            if not u.startswith(("http://", "https://")):
                raise HTTPException(400, f"링크는 http:// 또는 https://로 시작해야 해요: {u}")
        items = []
        for f in files:
            try:
                items.append((f.filename or "file", extract_text(f.filename or "", await f.read())))
            except UnsupportedFile as e:
                raise HTTPException(400, str(e))
            except Exception as e:  # corrupt PDF etc.
                raise HTTPException(400, f"{f.filename} 파일을 읽지 못했어요: {e}")
        link_texts = await asyncio.gather(*(fetch_link(u) for u in links))
        link_items = [(u, t or "") for u, t in zip(links, link_texts)]
        if files and not any(t.strip() for _, t in items) and not any(t for _, t in link_items):
            names = ", ".join(n for n, _ in items)
            raise HTTPException(
                400, f"올린 파일({names})에서 텍스트를 찾지 못했어요. 스캔 이미지 PDF라면 텍스트가 있는 PDF나 TXT로 올려주세요."
            )
        if not files and not any(t for _, t in link_items):
            raise HTTPException(400, "넣어 주신 링크에서 내용을 읽지 못했어요. 이력서 파일을 올려 주세요.")
        job = (job_text or "").strip() or None
        if job is None and job_url:
            job = await fetch_job_posting(job_url)
        sid = store.create_session(combine_sources(items + link_items), job_url, job)
        return {
            "session_id": sid,
            "files": [{"name": n, "chars": len(t)} for n, t in items],
            "links": [{"url": u, "chars": len(t)} for u, t in link_items],
            "job_text_ok": job is not None,
            "job_chars": len(job or ""),
        }

    @app.post("/api/sessions/{sid}/retry")
    async def retry_session(sid: str):
        """Practice again with the same materials: skips re-analysis."""
        s = _session(sid)
        if not s["analysis"] or not s["plan"]:
            raise HTTPException(409, "분석이 끝나지 않은 면접이에요. 새 면접으로 시작해 주세요.")
        new_id = store.clone_session(sid)
        return {"session_id": new_id, "analysis": s["analysis"], "plan": s["plan"]}

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
            raise HTTPException(503, LLM_DOWN)
        except LLMError as e:
            raise HTTPException(502, f"분석 결과를 만들지 못했어요. 다시 시도해 주세요. ({e})")
        except ValueError as e:
            raise HTTPException(400, str(e))
        store.update_session(sid, analysis=analysis, plan=plan)
        return {"analysis": analysis, "plan": plan}

    @app.get("/api/sessions")
    async def list_sessions():
        return [{**r, "report_status": _report_status(r["id"], r["has_report"])["status"]} for r in store.list_sessions()]

    @app.get("/api/sessions/{sid}")
    async def get_session(sid: str):
        s = _session(sid)
        s.pop("source_text", None)
        return {**s, "turns": store.get_turns(sid), "report_status": _report_status(sid, s["report"] is not None)}

    @app.post("/api/sessions/{sid}/report", status_code=202)
    async def build_report(sid: str):
        """Starts (or joins) building feedback in the background. Poll /report/status."""
        _session(sid)
        return dict(_start_report(sid))

    @app.get("/api/sessions/{sid}/report/status")
    async def report_status(sid: str):
        s = _session(sid)
        return _report_status(sid, s["report"] is not None)

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
        voice = tts.voice_for(sid)  # random interviewer (male/female) per session
        confirmed_terms: set[str] = set()
        hint = vocabulary_hint(s["analysis"])
        vocab = vocabulary_terms(s["analysis"])  # helps Whisper spell tech terms (Gemini, FastAPI...)
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
                        audio, mime = await tts.synthesize(sentence, voice)
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
                # Feedback builds in the background; the report screen shows its progress.
                _start_report(sid)
                await send_json({"type": "finished", "session_id": sid})

        async def handle_answer(text: str, spoken: bool = False) -> None:
            text = text.strip()
            note = preface = ""
            if text and spoken:
                # STT writes tech names by sound ("센터리"); fix them before anyone reads the answer.
                text, fixes = await fix_terms(llm, text, vocab)
                preface, note = confirm_note(fixes, confirmed_terms)
            if text:
                await send_json({"type": "transcript", "role": "candidate", "text": text})
                store.add_turn(sid, "candidate", text, orch.stage, "answer")
            await run_turn(orch.respond(text, note, preface))

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
                            heard = await stt.transcribe(msg["bytes"], hint)
                        except Exception as e:
                            log.exception("STT failed")
                            await send_json({"type": "error", "message": f"받아쓰기에 실패했어요. 다시 말하거나 답변을 입력해 주세요. ({e})"})
                            continue
                        await handle_answer(heard, spoken=True)
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
                    await send_json({"type": "error", "message": LLM_DOWN})
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
