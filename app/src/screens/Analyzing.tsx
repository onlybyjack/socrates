import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Analysis, Plan } from "../types";
import { Icon, Stepper } from "../ui";

interface Props {
  sessionId: string;
  onboarding: boolean;
  onDone: (analysis: Analysis, plan: Plan) => void;
  onCancel: () => void;
}

const STEPS = ["공고에서 원하는 사람 파악", "내 경험과 하나씩 맞춰 보기", "나에게 맞는 질문 순서 짜기"];
const STEP_MS = 9000;

/** Runs the analysis. The backend does it in one call, so the steps advance on a timer and the last one waits. */
export function AnalyzingScreen({ sessionId, onboarding, onDone, onCancel }: Props) {
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const cancelled = useRef(false);
  const done = useRef(onDone);
  done.current = onDone;

  useEffect(() => {
    cancelled.current = false;
    setError(null);
    setStep(0);
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), STEP_MS);
    api
      .analyze(sessionId)
      .then(({ analysis, plan }) => {
        if (cancelled.current) return;
        setStep(STEPS.length);
        setTimeout(() => !cancelled.current && done.current(analysis, plan), 400);
      })
      .catch((e) => !cancelled.current && setError((e as Error).message))
      .finally(() => clearInterval(timer));
    return () => {
      cancelled.current = true;
      clearInterval(timer);
    };
  }, [sessionId, attempt]);

  return (
    <div className="screen">
      {onboarding ? <Stepper now={2} /> : <div style={{ height: 52 }} />}
      <main className="page center" style={{ paddingBottom: 80 }}>
        <div className="col w-sm" style={{ gap: 28 }}>
          <div className="head">
            <h1>
              면접관이 내 이력서를
              <br />
              읽고 있어요
            </h1>
            <p className="lede">보통 30초쯤 걸려요.</p>
          </div>

          <ol className="steps glass" aria-live="polite">
            {STEPS.map((label, i) => {
              const state = error ? (i < step ? "done" : "") : i < step ? "done" : i === step ? "now" : "";
              return (
                <li key={label} className={state}>
                  <span className="mark">{state === "done" && <Icon.check />}</span>
                  {label}
                </li>
              );
            })}
          </ol>

          {error ? (
            <>
              <div className="callout err">
                <span>{error}</span>
              </div>
              <div className="between">
                <button className="btn" onClick={onCancel}>
                  자료 고치기
                </button>
                <button className="btn btn-primary" onClick={() => setAttempt((n) => n + 1)}>
                  다시 시도
                </button>
              </div>
            </>
          ) : (
            <button
              className="btn"
              style={{ alignSelf: "center" }}
              onClick={() => {
                cancelled.current = true;
                onCancel();
              }}
            >
              취소하고 자료 고치기
            </button>
          )}
        </div>
      </main>
    </div>
  );
}
