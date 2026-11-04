import type { Analysis, Plan } from "../types";
import { STAGES } from "../types";

interface Props {
  analysis: Analysis;
  plan: Plan;
  onStart: () => void;
}

export function AnalysisScreen({ analysis, plan, onStart }: Props) {
  const { job, match } = analysis;
  const topicsFor = (key: string) =>
    key === "experience" ? plan.experience : key === "technical" ? plan.technical : [];
  const fixed: Record<string, string> = {
    intro: "1분 자기소개",
    motivation: "왜 이 회사, 왜 이 직무인지",
    reverse_qa: "회사와 직무에 대해 궁금한 점을 물어보세요",
    closing: "마무리 인사",
  };

  return (
    <>
      <div className="role-head">
        <span className="company">{job.company || "회사 정보 없음"}</span>
        <h1>{job.role || "지원 직무"}</h1>
        {analysis.candidate.summary && <p className="lede">{analysis.candidate.summary}</p>}
      </div>

      <div className="columns">
        <section className="col strengths">
          <h2>강점</h2>
          <PointList items={match.strengths.map((s) => [s.point, s.evidence])} empty="찾은 강점이 없어요." />
        </section>
        <section className="col gaps">
          <h2>비어 보이는 곳</h2>
          <PointList items={match.gaps.map((s) => [s.point, s.evidence])} empty="눈에 띄는 갭이 없어요." />
        </section>
        <section className="col probes">
          <h2>파고들 지점</h2>
          <PointList items={match.probes.map((s) => [s.topic, s.why])} empty="없어요." />
        </section>
      </div>

      <section>
        <h2 style={{ marginBottom: 8 }}>면접 순서</h2>
        <ol className="timeline">
          {STAGES.map((s) => (
            <li key={s.key}>
              <span className="stage">{s.label}</span>
              <div className="topics">
                {fixed[s.key] && <span>{fixed[s.key]}</span>}
                {topicsFor(s.key).map((t, i) => (
                  <div key={i}>
                    <div>{t.topic}</div>
                    {t.intent && <div className="intent">{t.intent}</div>}
                  </div>
                ))}
              </div>
            </li>
          ))}
        </ol>
      </section>

      <div className="actions">
        <button className="btn btn-primary" onClick={onStart}>
          면접 시작
        </button>
        <span className="hint">마이크를 쓸 수 있는 조용한 곳에서 시작하세요. 15~25분 정도 걸려요.</span>
      </div>
    </>
  );
}

function PointList({ items, empty }: { items: [string, string][]; empty: string }) {
  if (items.length === 0) return <p className="hint">{empty}</p>;
  return (
    <ul>
      {items.map(([a, b], i) => (
        <li key={i}>
          <strong>{a}</strong>
          {b && <span>{b}</span>}
        </li>
      ))}
    </ul>
  );
}
