import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { Health } from "../types";

interface Props {
  onReady: () => void;
}

export function HealthScreen({ onReady }: Props) {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  const check = useCallback(async () => {
    setError(null);
    try {
      const h = await api.health();
      setHealth(h);
      if (h.ollama && h.model_present && h.tts) onReady();
    } catch (e) {
      setError((e as Error).message);
    }
  }, [onReady]);

  useEffect(() => {
    check();
  }, [check]);

  const model = health?.model || "qwen3:8b";
  return (
    <>
      <div className="role-head">
        <h1>시작하기 전에 확인할게요</h1>
        <p className="lede">면접관 음성, 받아쓰기, 질문 생성이 모두 이 맥에서 돌아가요. 아래 항목이 준비되면 바로 시작할 수 있어요.</p>
      </div>
      {error && (
        <div className="notice">
          <p className="error">{error}</p>
          <p>
            <code>cd backend && uv run python -m interview_agent</code>
          </p>
        </div>
      )}
      {health && (
        <ul className="checks">
          <Check ok={health.ollama} label="Ollama 실행 중" fix={<code>brew install ollama && brew services start ollama</code>} />
          <Check ok={health.model_present} label={`모델 ${model} 준비됨`} fix={<code>ollama pull {model}</code>} />
          <Check ok={health.tts} label="한국어 음성(Yuna) 사용 가능" fix={<span>시스템 설정 → 손쉬운 사용 → 읽기 및 말하기에서 한국어 음성 Yuna를 내려받아 주세요.</span>} />
          <Check ok label={health.stt_ready ? "받아쓰기 모델 준비됨" : "받아쓰기 모델은 처음 답변할 때 준비돼요"} />
        </ul>
      )}
      <div className="actions">
        <button className="btn btn-primary" onClick={check}>
          다시 확인
        </button>
      </div>
    </>
  );
}

function Check({ ok, label, fix }: { ok: boolean; label: string; fix?: React.ReactNode }) {
  return (
    <li>
      <span className={ok ? "ok" : "no"} aria-label={ok ? "준비됨" : "준비 안 됨"}>
        {ok ? "✓" : "✕"}
      </span>
      <div>
        <div>{label}</div>
        {!ok && fix && <div className="hint">{fix}</div>}
      </div>
    </li>
  );
}
