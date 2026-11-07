import { useEffect, useState } from "react";
import { api } from "../api";
import type { SessionSummary } from "../types";
import { Icon, Menubar, type MenuKey } from "../ui";

interface Props {
  onOpen: (sessionId: string) => void;
  onMenu: (k: MenuKey) => void;
  onPracticeAgain: (sessionId: string) => Promise<void>;
}

export function HistoryScreen({ onOpen, onMenu, onPracticeAgain }: Props) {
  const [starting, setStarting] = useState<string | null>(null);
  const again = (id: string) => {
    setStarting(id);
    onPracticeAgain(id).catch((e) => {
      setError((e as Error).message);
      setStarting(null);
    });
  };
  const [rows, setRows] = useState<SessionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [onlyDone, setOnlyDone] = useState(false);

  useEffect(() => {
    api.listSessions().then(setRows).catch((e) => setError(e.message));
  }, []);

  // Keep "피드백 만드는 중" rows fresh until they finish.
  const making = (rows ?? []).some((r) => r.report_status === "running");
  useEffect(() => {
    if (!making) return;
    const id = window.setInterval(() => api.listSessions().then(setRows).catch(() => {}), 3000);
    return () => window.clearInterval(id);
  }, [making]);

  const shown = (rows ?? []).filter((r) => !onlyDone || r.has_report);

  return (
    <div className="screen">
      <Menubar current="history" onGo={onMenu} />
      <main className="page">
        <div className="col" style={{ maxWidth: 880 }}>
          <div className="between" style={{ alignItems: "flex-end" }}>
            <div className="head">
              <h1 style={{ fontSize: 30 }}>지난 면접</h1>
              {rows && <p className="lede">연습한 면접 {rows.length}번 · 모두 이 맥에만 저장돼 있어요</p>}
            </div>
            {rows && rows.length > 0 && (
              <div className="seg sunk" role="tablist" aria-label="보기">
                <button role="tab" aria-selected={!onlyDone} onClick={() => setOnlyDone(false)}>전체</button>
                <button role="tab" aria-selected={onlyDone} onClick={() => setOnlyDone(true)}>피드백 있음</button>
              </div>
            )}
          </div>

          {error && <div className="callout err">{error}</div>}
          {!rows && !error && <p className="sub">불러오는 중…</p>}

          {rows && rows.length === 0 && (
            <div className="empty">
              <p style={{ fontSize: 17, fontWeight: 600 }}>아직 연습한 면접이 없어요</p>
              <p className="muted">이력서와 공고를 넣으면 첫 면접을 시작할 수 있어요.</p>
              <button className="btn btn-primary" onClick={() => onMenu("new")}>새 면접 시작</button>
            </div>
          )}

          {shown.length > 0 && (
            <ul className="hist glass">
              {shown.map((r) => (
                <li key={r.id}>
                  <button className="open" onClick={() => onOpen(r.id)}>
                    <span className="avatar">{(r.company || "?").slice(0, 1)}</span>
                    <span className="who">
                      <strong>{[r.company || "회사 정보 없음", r.role].filter(Boolean).join(" · ")}</strong>
                      <span>{new Date(r.created_at).toLocaleDateString("ko-KR", { month: "long", day: "numeric" })}</span>
                    </span>
                    {r.report_status === "running" ? (
                      <span className="tag making"><span className="spinner sm" aria-hidden />피드백 만드는 중</span>
                    ) : r.report_status === "error" ? (
                      <span className="tag warn">피드백 실패</span>
                    ) : (
                      <span className={`tag ${r.has_report ? "" : "grey"}`}>{r.has_report ? "피드백 보기" : "피드백 없음"}</span>
                    )}
                    <Icon.right />
                  </button>
                  {r.has_analysis && (
                    <button className="btn again" disabled={starting !== null} onClick={() => again(r.id)}>
                      {starting === r.id ? "준비 중…" : "다시 면접"}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}
