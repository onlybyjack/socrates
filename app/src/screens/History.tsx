import { useEffect, useState } from "react";
import { api } from "../api";
import type { SessionSummary } from "../types";

interface Props {
  onOpen: (sessionId: string) => void;
}

export function HistoryScreen({ onOpen }: Props) {
  const [rows, setRows] = useState<SessionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listSessions().then(setRows).catch((e) => setError(e.message));
  }, []);

  return (
    <>
      <h1>지난 면접</h1>
      {error && <p className="error">{error}</p>}
      {rows && rows.length === 0 && <p className="lede">아직 연습한 면접이 없어요. 새 면접에서 이력서와 공고를 넣고 시작해 보세요.</p>}
      {rows && rows.length > 0 && (
        <ul className="list">
          {rows.map((r) => (
            <li key={r.id}>
              <button onClick={() => onOpen(r.id)}>
                <span>
                  {r.company || "회사 정보 없음"} {r.role && `· ${r.role}`}
                  {!r.has_report && <span className="hint"> (피드백 없음)</span>}
                </span>
                <span className="date">{new Date(r.created_at).toLocaleDateString("ko-KR")}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
