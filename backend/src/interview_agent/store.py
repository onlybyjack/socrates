"""SQLite persistence for sessions and interview turns."""

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

_JSON_FIELDS = ("analysis", "plan", "report")
_TEXT_FIELDS = ("job_text",)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    source_text TEXT NOT NULL,
    job_url TEXT,
    job_text TEXT,
    analysis TEXT,
    plan TEXT,
    report TEXT
);
CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    created_at TEXT NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    stage TEXT NOT NULL,
    kind TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, db_path: Path):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)

    def create_session(self, source_text: str, job_url: str | None, job_text: str | None) -> str:
        sid = uuid.uuid4().hex
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO sessions (id, created_at, source_text, job_url, job_text) VALUES (?,?,?,?,?)",
                (sid, _now(), source_text, job_url, job_text),
            )
        return sid

    def clone_session(self, session_id: str) -> str | None:
        """New session with the same materials, analysis and plan (no turns, no report)."""
        sid = uuid.uuid4().hex
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO sessions (id, created_at, source_text, job_url, job_text, analysis, plan) "
                "SELECT ?, ?, source_text, job_url, job_text, analysis, plan FROM sessions WHERE id=?",
                (sid, _now(), session_id),
            )
        return sid if cur.rowcount else None

    def get_session(self, session_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        for f in _JSON_FIELDS:
            d[f] = json.loads(d[f]) if d[f] else None
        return d

    def list_sessions(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, created_at, analysis, plan IS NOT NULL AS has_plan, report IS NOT NULL AS has_report "
                "FROM sessions ORDER BY created_at DESC"
            ).fetchall()
        out = []
        for r in rows:
            job = (json.loads(r["analysis"]) if r["analysis"] else {}).get("job", {}) or {}
            out.append(
                {
                    "id": r["id"],
                    "created_at": r["created_at"],
                    "company": job.get("company", ""),
                    "role": job.get("role", ""),
                    "has_report": bool(r["has_report"]),
                    "has_analysis": bool(r["analysis"]) and bool(r["has_plan"]),
                }
            )
        return out

    def update_session(self, session_id: str, **fields) -> None:
        sets, vals = [], []
        for k, v in fields.items():
            if k in _JSON_FIELDS:
                v = json.dumps(v, ensure_ascii=False) if v is not None else None
            elif k not in _TEXT_FIELDS:
                raise ValueError(f"unknown field: {k}")
            sets.append(f"{k}=?")
            vals.append(v)
        if not sets:
            return
        with self._lock, self._conn:
            self._conn.execute(f"UPDATE sessions SET {', '.join(sets)} WHERE id=?", (*vals, session_id))

    def add_turn(self, session_id: str, role: str, text: str, stage: str, kind: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO turns (session_id, created_at, role, text, stage, kind) VALUES (?,?,?,?,?,?)",
                (session_id, _now(), role, text, stage, kind),
            )

    def get_turns(self, session_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, text, stage, kind, created_at FROM turns WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]
