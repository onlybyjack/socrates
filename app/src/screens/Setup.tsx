import { useRef, useState } from "react";
import { api } from "../api";
import type { Analysis, CreateSessionResult, Plan } from "../types";

interface Props {
  onAnalyzed: (sessionId: string, analysis: Analysis, plan: Plan) => void;
}

const ACCEPT = ".pdf,.txt,.md";

export function SetupScreen({ onAnalyzed }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [over, setOver] = useState(false);
  const [jobUrl, setJobUrl] = useState("");
  const [jobText, setJobText] = useState("");
  const [needPaste, setNeedPaste] = useState(false);
  const [session, setSession] = useState<CreateSessionResult | null>(null);
  const [busy, setBusy] = useState<null | "upload" | "analyze">(null);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    const ok = Array.from(list).filter((f) => /\.(pdf|txt|md)$/i.test(f.name));
    setFiles((prev) => [...prev, ...ok.filter((f) => !prev.some((p) => p.name === f.name))]);
    setSession(null);
  };

  const runAnalyze = async (sessionId: string) => {
    setBusy("analyze");
    const { analysis, plan } = await api.analyze(sessionId);
    onAnalyzed(sessionId, analysis, plan);
  };

  const submit = async () => {
    setError(null);
    try {
      let s = session;
      if (!s) {
        setBusy("upload");
        s = await api.createSession(files, jobUrl.trim() || undefined, jobText.trim() || undefined);
        setSession(s);
      } else if (jobText.trim()) {
        await api.setJobText(s.session_id, jobText.trim());
        s = { ...s, job_text_ok: true };
        setSession(s);
      }
      if (!s.job_text_ok) {
        setNeedPaste(true);
        setBusy(null);
        return;
      }
      await runAnalyze(s.session_id);
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  };

  const chars = (name: string) => session?.files.find((f) => f.name === name)?.chars;
  const hasJob = jobUrl.trim() !== "" || jobText.trim() !== "";
  const canSubmit = files.length > 0 && hasJob && busy === null && (!needPaste || jobText.trim() !== "");

  return (
    <>
      <div className="role-head">
        <h1>어떤 면접을 준비하나요?</h1>
        <p className="lede">
          이력서와 지원할 공고를 넣으면, 공고가 요구하는 것과 내 경험을 비교해서 그 직무의 시니어 면접관처럼 질문해요. 파일은 이 맥 밖으로
          나가지 않아요.
        </p>
      </div>

      <div className="steps">
        <section className="step">
          <div>
            <h2>이력서와 관련 자료</h2>
            <div
              className={`drop ${over ? "over" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setOver(true);
              }}
              onDragLeave={() => setOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setOver(false);
                addFiles(e.dataTransfer.files);
              }}
            >
              <p>이력서, 경력기술서, 포트폴리오 파일을 여기로 끌어오세요.</p>
              <p className="hint">PDF, TXT, MD · 여러 개 가능</p>
              <button className="btn" onClick={() => input.current?.click()}>
                파일 고르기
              </button>
              <input ref={input} type="file" accept={ACCEPT} multiple hidden onChange={(e) => addFiles(e.target.files)} />
            </div>
            {files.length > 0 && (
              <ul className="files">
                {files.map((f) => {
                  const c = chars(f.name);
                  return (
                    <li key={f.name}>
                      <span>{f.name}</span>
                      <span className="meta">
                        {c === undefined ? `${Math.ceil(f.size / 1024)}KB` : c === 0 ? <span className="error">텍스트 없음 · 스캔 이미지일 수 있어요</span> : `${c.toLocaleString()}자`}
                        <button
                          className="btn btn-ghost"
                          aria-label={`${f.name} 빼기`}
                          onClick={() => {
                            setFiles((prev) => prev.filter((p) => p !== f));
                            setSession(null);
                          }}
                        >
                          빼기
                        </button>
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>

        <section className="step">
          <div>
            <h2>지원할 공고</h2>
            <div className="field">
              <label htmlFor="job-url">공고 링크</label>
              <input
                id="job-url"
                type="url"
                placeholder="https://"
                value={jobUrl}
                onChange={(e) => {
                  setJobUrl(e.target.value);
                  setSession(null);
                  setNeedPaste(false);
                }}
              />
              <span className="hint">공고 페이지를 가져오는 이 요청만 인터넷을 써요.</span>
            </div>
            {needPaste && (
              <p className="notice">이 링크에서 공고 내용을 읽지 못했어요. 공고 내용을 아래에 붙여넣어 주세요.</p>
            )}
            <div className="field">
              <label htmlFor="job-text">공고 내용 붙여넣기 {needPaste ? "" : "(링크 대신 써도 돼요)"}</label>
              <textarea id="job-text" value={jobText} onChange={(e) => setJobText(e.target.value)} />
            </div>
          </div>
        </section>
      </div>

      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button className="btn btn-primary" disabled={!canSubmit} onClick={submit}>
          {busy === "upload" ? "자료 읽는 중…" : busy === "analyze" ? "공고와 이력서 비교하는 중…" : "분석하기"}
        </button>
        {busy === "analyze" && <span className="hint">30초 정도 걸려요.</span>}
      </div>
    </>
  );
}
