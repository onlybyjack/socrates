import { useEffect, useState } from "react";
import { api } from "../api";
import type { Report, SessionDetail } from "../types";

interface Props {
  sessionId: string;
}

export function ReportScreen({ sessionId }: Props) {
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getSession(sessionId)
      .then((s) => {
        setSession(s);
        setReport(s.report);
      })
      .catch((e) => setError(e.message));
  }, [sessionId]);

  const rebuild = async () => {
    setBusy(true);
    setError(null);
    try {
      setReport(await api.buildReport(sessionId));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (error && !session) return <p className="error">{error}</p>;
  if (!session) return <p className="hint">불러오는 중…</p>;

  const job = session.analysis?.job;
  const date = new Date(session.created_at).toLocaleString("ko-KR", { dateStyle: "long", timeStyle: "short" });

  return (
    <>
      <div className="role-head">
        <span className="company">
          {job?.company || "회사 정보 없음"} · {date}
        </span>
        <h1>{job?.role || "모의 면접"} 피드백</h1>
      </div>

      {!report || report.questions.length === 0 ? (
        <div className="notice">
          <p>{report ? "답변한 질문이 없어서 피드백을 만들지 못했어요." : "아직 피드백이 없어요."}</p>
          {session.turns.some((t) => t.role === "candidate") && (
            <button className="btn btn-primary" style={{ marginTop: 10 }} onClick={rebuild} disabled={busy}>
              {busy ? "피드백 만드는 중…" : "피드백 만들기"}
            </button>
          )}
        </div>
      ) : (
        <>
          <section className="overall">
            {report.overall.summary && <p className="summary">{report.overall.summary}</p>}
            <div className="two">
              <div>
                <h2 style={{ color: "var(--good)" }}>잘한 점</h2>
                <ul>
                  {report.overall.strengths.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h2 style={{ color: "var(--danger)" }}>고칠 점</h2>
                <ul>
                  {report.overall.improvements.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
            </div>
            {report.overall.next_topics.length > 0 && (
              <div>
                <h3>다음에 연습할 주제</h3>
                <p className="lede">{report.overall.next_topics.join(", ")}</p>
              </div>
            )}
          </section>

          <section>
            <h2 style={{ marginBottom: 8 }}>질문별 피드백</h2>
            <div className="qa">
              {report.questions.map((q, i) => (
                <details key={i} open={i === 0}>
                  <summary>
                    <span>{q.question}</span>
                  </summary>
                  <div className="body">
                    <p className="answer">{q.answer}</p>
                    <dl>
                      {q.good && (
                        <>
                          <dt>잘한 점</dt>
                          <dd>{q.good}</dd>
                        </>
                      )}
                      {q.improve && (
                        <>
                          <dt>아쉬운 점</dt>
                          <dd>{q.improve}</dd>
                        </>
                      )}
                      {q.better_direction && (
                        <>
                          <dt>이렇게 답해 보세요</dt>
                          <dd>{q.better_direction}</dd>
                        </>
                      )}
                    </dl>
                  </div>
                </details>
              ))}
            </div>
          </section>
          <div className="actions">
            <button className="btn" onClick={rebuild} disabled={busy}>
              {busy ? "피드백 다시 만드는 중…" : "피드백 다시 만들기"}
            </button>
          </div>
        </>
      )}
      {error && <p className="error">{error}</p>}
    </>
  );
}
