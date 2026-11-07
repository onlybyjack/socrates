import { useEffect, useState } from "react";
import { AnswerModePopover } from "../components/AnswerModePopover";
import { api } from "../api";
import type { Analysis, SessionSummary } from "../types";
import { Icon, Menubar, type MenuKey } from "../ui";
import type { Prefs } from "../prefs";

interface Props {
  sessionId: string;
  analysis: Analysis;
  prefs: Prefs;
  onPrefs: (next: Prefs) => void;
  onStart: () => void;
  onOpenReport: (sessionId: string) => void;
  onMenu: (k: MenuKey) => void;
}

interface InsightProps {
  color: string;
  title: string;
  items: [string, string][];
  empty: string;
}

/** One wide card per category; each point reads left (what) → right (why/evidence). */
function Insight({ color, title, items, empty }: InsightProps) {
  return (
    <section className="card glass insight">
      <h2>
        <span className="pip" style={{ background: color }} />
        {title} <span className="n">{items.length}</span>
      </h2>
      {items.length === 0 ? (
        <p className="sub">{empty}</p>
      ) : (
        <ul className="points">
          {items.map(([a, b], i) => (
            <li key={i}>
              <strong>{a}</strong>
              {b && <span>{b}</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

const date = (iso: string) => new Date(iso).toLocaleDateString("ko-KR", { month: "long", day: "numeric" });

export function DashboardScreen({ sessionId, analysis, prefs, onPrefs, onStart, onOpenReport, onMenu }: Props) {
  const [modeOpen, setModeOpen] = useState(false);
  const { job, match, candidate } = analysis;
  const answerMode = prefs.textMode ? "채팅으로 답해요" : `${prefs.micLabel || "기본 마이크"}로 답해요`;
  const [past, setPast] = useState<SessionSummary[]>([]);

  useEffect(() => {
    api
      .listSessions()
      .then((rows) => setPast(rows.filter((r) => r.id !== sessionId && r.has_report && r.company === job.company && r.role === job.role).slice(0, 3)))
      .catch(() => setPast([]));
  }, [sessionId, job.company, job.role]);

  return (
    <div className="screen">
      <Menubar onGo={onMenu} />
      <main className="page">
        <div className="dash">
          <div className="dash-main">
            <div className="head dash-head">
              <span className="sub" style={{ fontSize: 15 }}>{job.company || "회사 정보 없음"}</span>
              <h1 style={{ fontSize: 32 }}>{job.role || "지원 직무"}</h1>
              {candidate.summary && <p className="lede">{candidate.summary}</p>}
              {past.length > 0 && (
                <div className="past">
                  <span className="sub">이 공고로 연습한 기록</span>
                  {past.map((r) => (
                    <button key={r.id} className="btn past-chip" onClick={() => onOpenReport(r.id)}>
                      {date(r.created_at)} 피드백
                      <Icon.right />
                    </button>
                  ))}
                </div>
              )}
            </div>
            <Insight color="var(--green-ink)" title="강점" items={match.strengths.map((s) => [s.point, s.evidence])} empty="찾은 강점이 없어요." />
            <Insight color="var(--orange)" title="비어 보이는 곳" items={match.gaps.map((s) => [s.point, s.evidence])} empty="눈에 띄는 빈 곳이 없어요." />
            <Insight color="var(--blue)" title="파고들 지점" items={match.probes.map((s) => [s.topic, s.why])} empty="없어요." />
          </div>

        </div>
      </main>

      {/* Outside the dock: a nested backdrop-filter is ignored by WebKit, which made the panel see-through. */}
      {modeOpen && <AnswerModePopover prefs={prefs} onChange={onPrefs} onClose={() => setModeOpen(false)} />}
      <footer className="dock glass start-dock">
        <button
          className="btn btn-round"
          data-answer-toggle
          aria-expanded={modeOpen}
          onClick={() => setModeOpen((v) => !v)}
          title={`${answerMode} · 눌러서 바꾸기`}
          aria-label={`답변 방식: ${answerMode}. 바꾸기`}
        >
          {prefs.textMode ? <Icon.micOff /> : <Icon.mic size={20} />}
        </button>
        <button className="btn btn-primary" onClick={onStart} title="조용한 곳에서 시작하세요. 중간에 언제든 끝낼 수 있어요.">
          <Icon.video />
          면접 시작
        </button>
      </footer>
    </div>
  );
}
