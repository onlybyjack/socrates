import { useEffect, useRef, useState } from "react";
import { openUrl } from "@tauri-apps/plugin-opener";
import { api, BASE } from "../api";
import type { Health } from "../types";

interface Props {
  onReady: () => void;
}

type StepState = "wait" | "active" | "done" | "blocked";

interface Step {
  key: string;
  label: string;
  state: StepState;
  detail?: string;
  action?: { label: string; run: () => void };
}

const POLL_MS = 1000;

async function open(url: string) {
  try {
    await openUrl(url);
  } catch {
    window.open(url, "_blank");
  }
}

function gb(bytes: number) {
  return (bytes / 1024 ** 3).toFixed(1);
}

/** Startup splash: brings the local engine up step by step, fixing what it can by itself. */
export function SplashScreen({ onReady }: Props) {
  const [health, setHealth] = useState<Health | null>(null);
  const [engineDown, setEngineDown] = useState(0); // consecutive failed polls
  const pullRequested = useRef(false);
  const readySent = useRef(false);

  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const h = await api.health();
        if (stop) return;
        setHealth(h);
        setEngineDown(0);
        if (h.ollama && !h.model_present && h.pull.status === "idle" && !pullRequested.current) {
          pullRequested.current = true;
          api.pullModel().catch(() => (pullRequested.current = false));
        }
      } catch {
        if (!stop) setEngineDown((n) => n + 1);
      }
      if (!stop) setTimeout(tick, POLL_MS);
    };
    tick();
    return () => {
      stop = true;
    };
  }, []);

  const h = health;
  const pulling = h?.pull.status === "pulling";
  const pullPct = h && h.pull.total ? h.pull.completed / h.pull.total : 0;

  const steps: Step[] = [
    {
      key: "engine",
      label: "면접 엔진 켜기",
      state: h ? "done" : engineDown > 40 ? "blocked" : "active",
      detail: !h && engineDown > 40 ? "엔진이 켜지지 않아요. 앱을 종료했다가 다시 열어 주세요." : undefined,
    },
    {
      key: "ollama",
      label: "Ollama 연결",
      state: !h ? "wait" : h.ollama ? "done" : "blocked",
      detail: h && !h.ollama ? "질문을 만드는 Ollama가 필요해요. 설치하고 실행하면 자동으로 이어져요." : undefined,
      action: h && !h.ollama ? { label: "Ollama 내려받기", run: () => open("https://ollama.com/download") } : undefined,
    },
    {
      key: "model",
      label: `질문 모델 준비 (${h?.model || "qwen3:8b"})`,
      state: !h || !h.ollama ? "wait" : h.model_present ? "done" : h.pull.status === "error" ? "blocked" : "active",
      detail:
        h && !h.model_present && h.ollama
          ? h.pull.status === "error"
            ? `내려받지 못했어요: ${h.pull.message}`
            : h.pull.total
              ? `내려받는 중 ${gb(h.pull.completed)} / ${gb(h.pull.total)}GB · 처음 한 번만 받아요`
              : "내려받을 준비 중…"
          : undefined,
      action:
        h?.pull.status === "error"
          ? {
              label: "다시 받기",
              run: () => {
                pullRequested.current = true;
                api.pullModel().catch(() => (pullRequested.current = false));
              },
            }
          : undefined,
    },
    {
      key: "voice",
      label: "면접관 목소리",
      state: !h ? "wait" : h.tts ? "done" : "blocked",
      detail: h && !h.tts ? "시스템 설정 → 손쉬운 사용 → 읽기 및 말하기 → 시스템 음성에서 한국어 ‘유나’를 내려받아 주세요." : undefined,
      action:
        h && !h.tts
          ? { label: "설정 열기", run: () => open("x-apple.systempreferences:com.apple.preference.universalaccess?SpokenContent") }
          : undefined,
    },
    {
      key: "stt",
      label: "음성 인식 준비",
      state: !h ? "wait" : h.stt_ready ? "done" : "active",
      detail: h && !h.stt_ready ? "처음 실행할 때는 음성 인식 모델(약 1.6GB)을 내려받아서 몇 분 걸릴 수 있어요." : undefined,
    },
  ];

  const done = steps.filter((s) => s.state === "done").length;
  const progress = Math.min(1, (done + (pulling ? pullPct * 0.9 : 0)) / steps.length);
  const allDone = done === steps.length;
  const current = steps.find((s) => s.state !== "done");

  useEffect(() => {
    if (allDone && !readySent.current) {
      readySent.current = true;
      const t = setTimeout(onReady, 500);
      return () => clearTimeout(t);
    }
  }, [allDone, onReady]);

  return (
    <div className="splash">
      <div className="splash-inner">
        <h1 className="splash-title">모의 면접</h1>
        <p className="splash-sub">이력서와 답변은 이 맥 밖으로 나가지 않아요.</p>

        <div className="splash-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)}>
          <span style={{ width: `${progress * 100}%` }} />
        </div>
        <p className="splash-now" aria-live="polite">
          {allDone ? "준비됐어요" : current ? `${current.label}${current.state === "blocked" ? "에 도움이 필요해요" : " 중…"}` : ""}
        </p>

        <ol className="splash-steps">
          {steps.map((s) => (
            <li key={s.key} className={s.state}>
              <span className="mark" aria-hidden>
                {s.state === "done" ? "✓" : s.state === "blocked" ? "!" : ""}
              </span>
              <div>
                <div className="label">{s.label}</div>
                {s.detail && <div className="detail">{s.detail}</div>}
                {s.action && (
                  <button className="btn" onClick={s.action.run}>
                    {s.action.label}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ol>
        {import.meta.env.DEV && !h && engineDown > 3 && (
          <p className="splash-dev">
            개발 모드: <code>cd backend && uv run python -m interview_agent</code> ({BASE})
          </p>
        )}
      </div>
    </div>
  );
}
