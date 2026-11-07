import { useEffect, useRef, useState } from "react";
import { openUrl } from "@tauri-apps/plugin-opener";
import { api, BASE } from "../api";
import { Icon } from "../ui";
import type { Health } from "../types";

interface Props {
  onReady: () => void;
}

/** What the user sees: one plain status line, never the internal component list. */
interface Status {
  title: string;
  note?: string;
  /** Set only when the user has to do something themselves. */
  action?: { label: string; run: () => void };
  blocked?: boolean;
}

const POLL_MS = 1000;
const ENGINE_GIVE_UP = 40; // ~40s of failed polls

async function open(url: string) {
  try {
    await openUrl(url);
  } catch {
    window.open(url, "_blank");
  }
}

const gb = (bytes: number) => (bytes / 1024 ** 3).toFixed(1);

/** Startup splash: brings everything up on its own and only asks the user for help when it must. */
export function SplashScreen({ onReady }: Props) {
  const [health, setHealth] = useState<Health | null>(null);
  const [engineDown, setEngineDown] = useState(0);
  const pullRequested = useRef(false);
  const readySent = useRef(false);

  const requestPull = () => {
    pullRequested.current = true;
    api.pullModel().catch(() => (pullRequested.current = false));
  };

  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const h = await api.health();
        if (stop) return;
        setHealth(h);
        setEngineDown(0);
        if (h.ollama && !h.model_present && h.pull.status === "idle" && !pullRequested.current) requestPull();
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

  // Rough weights: the first-run download dominates the wait.
  const parts = [!!h, !!h?.ollama, !!h?.model_present, !!h?.tts, !!h?.stt_ready];
  const done = parts.filter(Boolean).length;
  const allDone = done === parts.length;
  const progress = Math.min(1, (done + (pulling ? pullPct * 0.95 : 0)) / parts.length);

  let status: Status;
  if (!h) {
    status =
      engineDown > ENGINE_GIVE_UP
        ? { title: "앱이 제대로 켜지지 않았어요", note: "앱을 완전히 종료했다가 다시 열어 주세요.", blocked: true }
        : { title: "면접실을 여는 중이에요" };
  } else if (!h.ollama) {
    status = {
      title: "면접관을 움직일 무료 프로그램이 필요해요",
      note: "아래 버튼으로 내려받아 설치하고 실행하면, 이 화면이 알아서 이어서 준비해요.",
      action: { label: "설치 프로그램 받기", run: () => open("https://ollama.com/download") },
      blocked: true,
    };
  } else if (!h.model_present) {
    status =
      h.pull.status === "error"
        ? {
            title: "면접관을 준비하다 멈췄어요",
            note: "인터넷 연결을 확인하고 다시 시도해 주세요.",
            action: { label: "다시 시도", run: requestPull },
            blocked: true,
          }
        : {
            title: "면접관을 처음 준비하고 있어요",
            note: h.pull.total
              ? `처음 한 번만 받아요 · ${gb(h.pull.completed)} / ${gb(h.pull.total)}GB`
              : "처음 한 번만 받아요. 다음부터는 몇 초면 켜져요.",
          };
  } else if (!h.tts) {
    status = { title: "면접관 목소리를 준비하고 있어요", note: "처음 한 번만 받아요. 다음부터는 몇 초면 켜져요." };
  } else if (!h.stt_ready) {
    status = { title: "내 답변을 알아들을 준비를 하고 있어요", note: "처음 한 번만 몇 분 걸릴 수 있어요." };
  } else {
    status = { title: "준비됐어요" };
  }

  useEffect(() => {
    if (allDone && !readySent.current) {
      readySent.current = true;
      const t = setTimeout(onReady, 500);
      return () => clearTimeout(t);
    }
  }, [allDone, onReady]);

  return (
    <div className="screen">
      <main className="page center">
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: "100%" }}>
          <section className="splash-card glass" aria-live="polite">
            <div className={`title ${status.blocked ? "blocked" : ""}`}>
              <span>{status.title}</span>
              {!status.blocked && <span className="pct num">{Math.round(progress * 100)}%</span>}
            </div>
            <div
              className={`bar ${status.blocked ? "paused" : ""}`}
              role="progressbar"
              aria-label="준비 진행률"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(progress * 100)}
            >
              <span style={{ width: `${Math.max(progress, 0.03) * 100}%` }} />
            </div>
            {status.note && <p className="muted" style={{ fontSize: 14 }}>{status.note}</p>}
            {status.action && (
              <div style={{ marginTop: 8 }}>
                <button className="btn btn-primary" onClick={status.action.run}>
                  {status.action.label}
                </button>
              </div>
            )}
            {import.meta.env.DEV && !h && engineDown > 3 && (
              <p className="sub small">
                개발 모드: <code>cd backend && uv run python -m interview_agent</code> ({BASE})
              </p>
            )}
          </section>
          <p className="privacy">
            <Icon.lock />
            이력서와 답변은 밖으로 나가지 않아요
          </p>
        </div>
      </main>
    </div>
  );
}
