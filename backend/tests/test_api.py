import pytest
from fastapi.testclient import TestClient

from fakes import FakeLLM, FakeSTT, FakeTTS
from interview_agent.api import create_app
from interview_agent.llm import LLMUnavailable
from interview_agent.store import Store

ANALYSIS_JSON = {"job": {"company": "키코", "role": "백엔드"}, "candidate": {}, "match": {}}
PLAN_JSON = {"experience": [{"topic": "e", "intent": "i"}] * 3, "technical": [{"topic": "t", "intent": "i"}] * 2}


class DownLLM(FakeLLM):
    async def chat_json(self, system, user):
        raise LLMUnavailable("down")

    async def check(self):
        return {"ok": False, "model_present": False}


def make_client(tmp_path, llm=None, stt=None):
    store = Store(tmp_path / "t.db")
    app = create_app(llm or FakeLLM(), stt or FakeSTT(), FakeTTS(), store)
    return TestClient(app), store


def ready_session(store) -> str:
    sid = store.create_session("이력서", None, "공고")
    store.update_session(sid, analysis=ANALYSIS_JSON, plan=PLAN_JSON)
    return sid


def test_health_reports_components(tmp_path):
    c, _ = make_client(tmp_path, llm=DownLLM())
    body = c.get("/api/health").json()
    assert body["ollama"] is False and body["model_present"] is False
    assert body["tts"] is True and body["stt"] is True


def test_create_session_rejects_all_empty(tmp_path):
    c, _ = make_client(tmp_path)
    r = c.post("/api/sessions", files=[("files", ("a.txt", b"   ", "text/plain"))], data={"job_text": "공고"})
    assert r.status_code == 400
    assert "a.txt" in r.json()["detail"]


def test_create_session_unsupported_file(tmp_path):
    c, _ = make_client(tmp_path)
    r = c.post("/api/sessions", files=[("files", ("a.png", b"x", "image/png"))])
    assert r.status_code == 400


def test_create_session_reads_links_with_files(tmp_path, monkeypatch):
    seen = []

    async def fake_fetch(url):
        seen.append(url)
        return "깃허브 프로필: 결제 서버 오픈소스 기여" if "github" in url else None

    monkeypatch.setattr("interview_agent.api.fetch_link", fake_fetch)
    c, store = make_client(tmp_path)
    r = c.post(
        "/api/sessions",
        files=[("files", ("a.txt", "이력서 내용".encode(), "text/plain"))],
        data={"job_text": "공고", "links": ["https://github.com/me", "https://broken.example"]},
    )
    body = r.json()
    assert r.status_code == 200
    assert seen == ["https://github.com/me", "https://broken.example"]
    assert body["links"] == [{"url": "https://github.com/me", "chars": 22}, {"url": "https://broken.example", "chars": 0}]
    src = store.get_session(body["session_id"])["source_text"]
    assert "### 파일: a.txt" in src and "### 링크: https://github.com/me" in src and "broken" not in src


def test_create_session_links_only(tmp_path, monkeypatch):
    async def fake_fetch(url):
        return "포트폴리오 본문입니다"

    monkeypatch.setattr("interview_agent.api.fetch_link", fake_fetch)
    c, _ = make_client(tmp_path)
    r = c.post("/api/sessions", data={"job_text": "공고", "links": ["https://me.dev"]})
    assert r.status_code == 200


def test_create_session_needs_a_source_and_valid_links(tmp_path, monkeypatch):
    async def none(url):
        return None

    monkeypatch.setattr("interview_agent.api.fetch_link", none)
    c, _ = make_client(tmp_path)
    assert c.post("/api/sessions", data={"job_text": "공고"}).status_code == 400
    assert c.post("/api/sessions", data={"job_text": "공고", "links": ["ftp://x"]}).status_code == 400
    r = c.post("/api/sessions", data={"job_text": "공고", "links": ["https://dead.example"]})
    assert r.status_code == 400 and "링크" in r.json()["detail"]


def test_create_session_with_job_text(tmp_path):
    c, store = make_client(tmp_path)
    r = c.post(
        "/api/sessions",
        files=[("files", ("a.txt", "이력서 내용".encode(), "text/plain")), ("files", ("b.md", b"", "text/plain"))],
        data={"job_text": "공고 본문"},
    )
    body = r.json()
    assert r.status_code == 200
    assert body["files"] == [{"name": "a.txt", "chars": 6}, {"name": "b.md", "chars": 0}]
    assert body["job_text_ok"] is True
    assert store.get_session(body["session_id"])["job_text"] == "공고 본문"


def test_set_job_text_then_analyze(tmp_path):
    llm = FakeLLM(json_responses=[ANALYSIS_JSON, PLAN_JSON])
    c, store = make_client(tmp_path, llm=llm)
    sid = store.create_session("이력서", None, None)
    assert c.post(f"/api/sessions/{sid}/analyze").status_code == 409
    assert c.post(f"/api/sessions/{sid}/job_text", json={"text": "공고"}).status_code == 200
    r = c.post(f"/api/sessions/{sid}/analyze")
    assert r.status_code == 200
    assert r.json()["analysis"]["job"]["company"] == "키코"
    assert len(r.json()["plan"]["experience"]) == 3


def test_analyze_503_when_llm_down(tmp_path):
    c, store = make_client(tmp_path, llm=DownLLM())
    sid = store.create_session("이력서", None, "공고")
    r = c.post(f"/api/sessions/{sid}/analyze")
    assert r.status_code == 503
    assert "Ollama" in r.json()["detail"]


def test_unknown_session_404(tmp_path):
    c, _ = make_client(tmp_path)
    assert c.get("/api/sessions/nope").status_code == 404


def _drain_turn(ws) -> list:
    """Receive messages until turn_done; returns the list (bytes for binary frames)."""
    msgs = []
    while True:
        m = ws.receive()
        if m.get("bytes") is not None:
            msgs.append(m["bytes"])
            continue
        import json

        data = json.loads(m["text"])
        msgs.append(data)
        if data["type"] in ("turn_done", "error"):
            return msgs


def test_ws_turn_sends_text_audio_done(tmp_path):
    llm = FakeLLM(stream_responses=["[NEXT]\n안녕하세요. 자기소개 부탁드립니다.", "[FOLLOW_UP]\n왜요?"])
    c, store = make_client(tmp_path, llm=llm, stt=FakeSTT(["저는 개발자입니다."]))
    sid = ready_session(store)
    with c.websocket_connect(f"/ws/interview/{sid}") as ws:
        ws.send_json({"type": "start"})
        msgs = _drain_turn(ws)
        types = [m["type"] if isinstance(m, dict) else "bytes" for m in msgs]
        assert types[0] == "state"
        assert "question_text_delta" in types
        audio_meta = [m for m in msgs if isinstance(m, dict) and m["type"] == "audio"]
        assert [a["seq"] for a in audio_meta] == [0, 1]
        # every audio meta is immediately followed by its bytes
        for i, m in enumerate(msgs):
            if isinstance(m, dict) and m["type"] == "audio":
                assert isinstance(msgs[i + 1], bytes)
        done = msgs[-1]
        assert done == {"type": "turn_done", "stage": "intro", "finished": False, "text": "안녕하세요. 자기소개 부탁드립니다."}

        ws.send_bytes(b"RIFFfake")
        msgs = _drain_turn(ws)
        assert {"type": "transcript", "role": "candidate", "text": "저는 개발자입니다."} in msgs
        assert msgs[-1]["text"] == "왜요?"
    turns = store.get_turns(sid)
    assert [(t["role"], t["kind"]) for t in turns] == [
        ("interviewer", "main"), ("candidate", "answer"), ("interviewer", "follow_up")
    ]


def test_ws_empty_stt_repeat_prompt(tmp_path):
    c, store = make_client(tmp_path, stt=FakeSTT([""]))
    sid = ready_session(store)
    with c.websocket_connect(f"/ws/interview/{sid}") as ws:
        ws.send_json({"type": "start"})
        _drain_turn(ws)
        ws.send_bytes(b"RIFF")
        msgs = _drain_turn(ws)
        assert msgs[-1]["text"] == "죄송해요, 잘 못 들었어요. 다시 한 번 말씀해 주시겠어요?"
    assert [t["role"] for t in store.get_turns(sid)] == ["interviewer", "interviewer"]


def test_ws_end_interview_generates_report(tmp_path):
    llm = FakeLLM(
        json_responses=[{"overall": {"summary": "총평"}}],
        stream_responses=["[NEXT]\n자기소개 부탁드립니다.", "[NEXT]\n수고하셨습니다."],
    )
    c, store = make_client(tmp_path, llm=llm, stt=FakeSTT(["답변"]))
    sid = ready_session(store)
    with c.websocket_connect(f"/ws/interview/{sid}") as ws:
        ws.send_json({"type": "start"})
        _drain_turn(ws)
        ws.send_json({"type": "text_answer", "text": "저는 개발자입니다."})
        _drain_turn(ws)
        ws.send_json({"type": "end_interview"})
        msgs = _drain_turn(ws)
        assert msgs[-1]["finished"] is True
        while True:
            m = ws.receive_json()
            if m["type"] == "finished":
                break
    assert _wait_report(c, sid)["status"] == "done"
    rep = store.get_session(sid)["report"]
    assert rep["overall"]["summary"] == "총평"
    assert rep["questions"][0]["answer"] == "저는 개발자입니다."


def _wait_report(c, sid):
    import time

    for _ in range(200):
        body = c.get(f"/api/sessions/{sid}/report/status").json()
        if body["status"] != "running":
            return body
        time.sleep(0.01)
    raise AssertionError(body)


def test_report_builds_in_background(tmp_path):
    llm = FakeLLM(json_responses=[{"overall": {"summary": "총평"}}])
    c, store = make_client(tmp_path, llm=llm)
    sid = ready_session(store)
    store.add_turn(sid, "interviewer", "자기소개 부탁드려요.", "intro", "main")
    store.add_turn(sid, "candidate", "저는 백엔드 개발자입니다.", "intro", "answer")
    assert c.get(f"/api/sessions/{sid}/report/status").json()["status"] == "none"
    r = c.post(f"/api/sessions/{sid}/report")
    assert r.status_code == 202 and r.json()["status"] == "running"
    assert _wait_report(c, sid)["status"] == "done"
    assert c.get(f"/api/sessions/{sid}").json()["report"]["overall"]["summary"] == "총평"


def test_ws_not_analyzed_errors(tmp_path):
    c, store = make_client(tmp_path)
    sid = store.create_session("이력서", None, "공고")
    with c.websocket_connect(f"/ws/interview/{sid}") as ws:
        m = ws.receive_json()
        assert m["type"] == "error"


class BoomSTT(FakeSTT):
    async def transcribe(self, wav, hint=""):
        raise RuntimeError("mlx exploded")


class ReportBoomLLM(FakeLLM):
    async def chat_json(self, system, user):
        raise RuntimeError("unexpected")


def test_ws_stt_failure_sends_error_and_keeps_socket(tmp_path):
    c, store = make_client(tmp_path, stt=BoomSTT())
    sid = ready_session(store)
    with c.websocket_connect(f"/ws/interview/{sid}") as ws:
        ws.send_json({"type": "start"})
        _drain_turn(ws)
        ws.send_bytes(b"RIFF")
        msgs = _drain_turn(ws)
        assert msgs[-1]["type"] == "error"
        ws.send_json({"type": "text_answer", "text": "타이핑 답변"})
        msgs = _drain_turn(ws)
        assert msgs[-1]["type"] == "turn_done"


def test_ws_report_failure_still_finishes(tmp_path):
    llm = ReportBoomLLM(stream_responses=["[NEXT]\n자기소개 부탁드립니다.", "[NEXT]\n수고하셨습니다."])
    c, store = make_client(tmp_path, llm=llm)
    sid = ready_session(store)
    with c.websocket_connect(f"/ws/interview/{sid}") as ws:
        ws.send_json({"type": "start"})
        _drain_turn(ws)
        ws.send_json({"type": "text_answer", "text": "답변"})
        _drain_turn(ws)
        ws.send_json({"type": "end_interview"})
        _drain_turn(ws)
        while ws.receive_json()["type"] != "finished":
            pass
    st = _wait_report(c, sid)
    assert st["status"] == "error" and "unexpected" in st["message"]
    assert c.get("/api/sessions").json()[0]["report_status"] == "error"


def _wait_pull(c, want):
    import time

    for _ in range(100):
        body = c.get("/api/health").json()
        if body["pull"]["status"] == want:
            return body
        time.sleep(0.01)
    raise AssertionError(body)


def test_model_pull_runs_in_background_and_reports_progress(tmp_path):
    from fakes import PullingLLM

    llm = PullingLLM()
    c, _ = make_client(tmp_path, llm=llm)
    assert c.get("/api/health").json()["pull"]["status"] == "idle"
    r = c.post("/api/model/pull")
    assert r.status_code == 200
    body = _wait_pull(c, "done")
    assert body["model_present"] is True and body["pull"]["completed"] == 10
    c.post("/api/model/pull")  # already present → no second download
    assert llm.pulls == 1


def test_model_pull_failure_is_reported(tmp_path):
    from fakes import PullingLLM

    c, _ = make_client(tmp_path, llm=PullingLLM(fail=True))
    c.post("/api/model/pull")
    body = _wait_pull(c, "error")
    assert "disk full" in body["pull"]["message"]


def test_retry_copies_materials_and_analysis_without_turns(tmp_path):
    c, store = make_client(tmp_path)
    sid = ready_session(store)
    store.add_turn(sid, "interviewer", "질문", "intro", "question")
    store.update_session(sid, report={"summary": "x"})
    r = c.post(f"/api/sessions/{sid}/retry")
    assert r.status_code == 200
    new = r.json()["session_id"]
    assert new != sid and r.json()["analysis"] == ANALYSIS_JSON
    s = store.get_session(new)
    assert s["plan"] == PLAN_JSON and s["job_text"] == "공고" and s["source_text"] == "이력서"
    assert s["report"] is None and store.get_turns(new) == []


def test_retry_needs_analysis(tmp_path):
    c, store = make_client(tmp_path)
    sid = store.create_session("이력서", None, "공고")
    assert c.post(f"/api/sessions/{sid}/retry").status_code == 409
    assert c.post("/api/sessions/nope/retry").status_code == 404
