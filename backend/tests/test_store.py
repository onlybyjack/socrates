import time

from interview_agent.store import Store


def make_store(tmp_path):
    return Store(tmp_path / "t.db")


def test_session_roundtrip(tmp_path):
    s = make_store(tmp_path)
    sid = s.create_session("이력서 내용", "https://x.com/job", None)
    got = s.get_session(sid)
    assert got["source_text"] == "이력서 내용"
    assert got["job_url"] == "https://x.com/job"
    assert got["analysis"] is None
    assert s.get_session("nope") is None


def test_update_json_fields(tmp_path):
    s = make_store(tmp_path)
    sid = s.create_session("a", None, "공고")
    s.update_session(sid, analysis={"job": {"company": "키코"}}, job_text="새 공고")
    got = s.get_session(sid)
    assert got["analysis"] == {"job": {"company": "키코"}}
    assert got["job_text"] == "새 공고"


def test_turns_ordered(tmp_path):
    s = make_store(tmp_path)
    sid = s.create_session("a", None, None)
    s.add_turn(sid, "interviewer", "q1", "intro", "main")
    s.add_turn(sid, "candidate", "a1", "intro", "answer")
    s.add_turn(sid, "interviewer", "q2", "intro", "follow_up")
    turns = s.get_turns(sid)
    assert [t["text"] for t in turns] == ["q1", "a1", "q2"]
    assert turns[2]["kind"] == "follow_up"


def test_list_sessions_newest_first(tmp_path):
    s = make_store(tmp_path)
    a = s.create_session("a", None, None)
    time.sleep(0.01)
    b = s.create_session("b", None, None)
    s.update_session(b, analysis={"job": {"company": "C", "role": "R"}}, report={"x": 1})
    rows = s.list_sessions()
    assert [r["id"] for r in rows] == [b, a]
    assert rows[0]["company"] == "C" and rows[0]["role"] == "R"
    assert rows[0]["has_report"] is True and rows[1]["has_report"] is False
