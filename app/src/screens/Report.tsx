import { useEffect, useState } from "react";
import { api } from "../api";
import type { Report, ReportJob, SessionDetail } from "../types";
import { Icon, Menubar, type MenuKey } from "../ui";

interface Props {
  sessionId: string;
  onPracticeAgain?: (sessionId: string) => Promise<void>;
  onMenu: (k: MenuKey) => void;
}

const minutes = (s: SessionDetail) => {
  const times = s.turns.map((t) => new Date(t.created_at).getTime()).filter((n) => !Number.isNaN(n));
  if (times.length < 2) return null;
  return Math.max(1, Math.round((Math.max(...times) - Math.min(...times)) / 60000));
};

export function ReportScreen({ sessionId, onPracticeAgain, onMenu }: Props) {
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [job, setJob] = useState<ReportJob>({ status: "none", message: "" });
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(0);
  const [seconds, setSeconds] = useState(0);
  const busy = job.status === "running";

  const load = () =>
    api
      .getSession(sessionId)
      .then((s) => {
        setSession(s);
        setReport(s.report);
        setJob(s.report_status ?? { status: s.report ? "done" : "none", message: "" });
      })
      .catch((e) => setError(e.message));

  useEffect(() => {
    load();
  }, [sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  // While feedback builds in the background, poll its status; reload the session when it is done.
  useEffect(() => {
    if (!busy) return;
    setSeconds(0);
    const tick = window.setInterval(() => setSeconds((n) => n + 1), 1000);
    const poll = window.setInterval(() => {
      api
        .reportStatus(sessionId)
        .then((st) => {
          if (st.status === "running") return;
          if (st.status === "done") load();
          else setJob({ status: st.status ?? "none", message: st.message ?? "" });
        })
        .catch(() => {});
    }, 2000);
    return () => {
      window.clearInterval(tick);
      window.clearInterval(poll);
    };
  }, [busy, sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  const rebuild = async () => {
    setError(null);
    try {
      setJob(await api.buildReport(sessionId));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const role = session?.analysis?.job;
  const answered = session?.turns.some((t) => t.role === "candidate");
  const mins = session ? minutes(session) : null;
  const when = session ? new Date(session.created_at).toLocaleString("ko-KR", { month: "long", day: "numeric", hour: "numeric", minute: "2-digit" }) : "";

  return (
    <div className="screen">
      <Menubar onGo={onMenu} />
      <main className="page">
        <div className="col" style={{ maxWidth: 880, gap: 28 }}>
          {!session ? (
            error ? <div className="callout err">{error}</div> : <p className="sub">불러오는 중…</p>
          ) : (
            <>
              <div className="head">
                <span className="sub" style={{ fontSize: 15 }}>
                  {[role?.company || "회사 정보 없음", when, mins && `${mins}분`, report && `질문 ${report.questions.length}개`].filter(Boolean).join(" · ")}
                </span>
                <h1 style={{ fontSize: 30 }}>{role?.role || "모의 면접"} 면접 피드백</h1>
              </div>

              {busy && (
                <section className="card glass report-progress" aria-live="polite">
                  <span className="spinner" aria-hidden />
                  <div>
                    <strong>{report ? "피드백을 다시 만들고 있어요" : "피드백을 만들고 있어요"}</strong>
                    <p className="sub">
                      답변을 하나씩 읽고 있어요 · {seconds}초 지남. 보통 1분 안팎 걸리고, 다른 화면으로 가도 계속 만들어요.
                    </p>
                  </div>
                </section>
              )}
              {job.status === "error" && (
                <div className="callout err">
                  <span>{job.message}</span>
                  <button className="btn" onClick={rebuild}>다시 만들기</button>
                </div>
              )}

              {busy && !report ? null : !report || report.questions.length === 0 ? (
                <section className="card glass">
                  <p>{report ? "답변한 질문이 없어서 피드백을 만들지 못했어요." : "아직 피드백이 없어요."}</p>
                  {answered && (
                    <div>
                      <button className="btn btn-primary" onClick={rebuild} disabled={busy}>
                        피드백 만들기
                      </button>
                    </div>
                  )}
                </section>
              ) : (
                <>
                  {report.overall.summary && (
                    <section className="card glass" style={{ padding: "24px 26px", gap: 12 }}>
                      <h2 className="muted" style={{ fontSize: 15, fontWeight: 600 }}>한 줄 정리</h2>
                      <p className="summary selectable">{report.overall.summary}</p>
                    </section>
                  )}

                  <section className="two">
                    <div className="card glass" style={{ padding: 22, gap: 12 }}>
                      <h2 className="row" style={{ gap: 8, fontSize: 16 }}><span className="pip" style={{ background: "var(--green-ink)" }} />잘한 점</h2>
                      {report.overall.strengths.length > 0 ? (
                        <ul className="bullets selectable">{report.overall.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
                      ) : (
                        <p className="sub">이번 답변에서는 근거 있는 잘한 점을 찾지 못했어요.</p>
                      )}
                    </div>
                    <div className="card glass" style={{ padding: 22, gap: 12 }}>
                      <h2 className="row" style={{ gap: 8, fontSize: 16 }}><span className="pip" style={{ background: "var(--orange)" }} />고칠 점</h2>
                      <ul className="bullets selectable">{report.overall.improvements.map((s, i) => <li key={i}>{s}</li>)}</ul>
                    </div>
                  </section>

                  {report.overall.next_topics.length > 0 && (
                    <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                      <h2 style={{ fontSize: 16 }}>다음에 연습할 주제</h2>
                      <div className="topic-chips">{report.overall.next_topics.map((t, i) => <span key={i}>{t}</span>)}</div>
                    </section>
                  )}

                  <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                    <div className="between" style={{ alignItems: "baseline" }}>
                      <h2 style={{ fontSize: 20 }}>질문별 피드백</h2>
                      <span className="sub" style={{ fontSize: 14 }}>눌러서 펼치기</span>
                    </div>
                    <ol className="qa">
                      {report.questions.map((q, i) => {
                        const isOpen = open === i;
                        return (
                          <li key={i} className={`glass ${isOpen ? "open" : ""}`}>
                            <button className="q" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? -1 : i)}>
                              <span className="n">{i + 1}</span>
                              <span className="t">{q.question}</span>
                              <Icon.chevron />
                            </button>
                            {isOpen && (
                              <div className="a">
                                {q.answer && <p className="mine sunk">내 답변 · {q.answer}</p>}
                                <dl>
                                  {q.good && (<><dt style={{ color: "var(--green-ink)" }}>잘한 점</dt><dd>{q.good}</dd></>)}
                                  {q.improve && (<><dt style={{ color: "#C2410C" }}>아쉬운 점</dt><dd>{q.improve}</dd></>)}
                                  {q.better_direction && (<><dt style={{ color: "var(--blue-deep)" }}>이렇게 답해 보세요</dt><dd>{q.better_direction}</dd></>)}
                                </dl>
                              </div>
                            )}
                          </li>
                        );
                      })}
                    </ol>
                  </section>

                  <div className="row" style={{ justifyContent: "flex-end" }}>
                    <button className="btn" onClick={rebuild} disabled={busy}>
                      {busy ? "피드백 다시 만드는 중…" : "피드백 다시 만들기"}
                    </button>
                    {onPracticeAgain && session.analysis && (
                      <button
                        className="btn btn-primary"
                        disabled={busy}
                        onClick={() => onPracticeAgain(sessionId).catch((e) => setError((e as Error).message))}
                      >
                        같은 자료로 다시 면접
                      </button>
                    )}
                  </div>
                </>
              )}
              {error && <div className="callout err">{error}</div>}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
