import { useRef, useState } from "react";
import { api } from "../api";
import type { CreateSessionResult } from "../types";
import { Icon, Menubar, Stepper, type MenuKey } from "../ui";

interface Props {
  onboarding: boolean;
  onReady: (sessionId: string) => void;
  onBack?: () => void;
  onMenu: (k: MenuKey) => void;
}

const ACCEPT = ".pdf,.txt,.md";
const ext = (name: string) => name.split(".").pop()?.toUpperCase() ?? "";

/** Accepts "github.com/me" too; returns null when it can't be a web link. */
function toUrl(raw: string): string | null {
  const v = raw.trim();
  if (!v) return null;
  try {
    const u = new URL(/^https?:\/\//i.test(v) ? v : `https://${v}`);
    return u.hostname.includes(".") ? u.toString() : null;
  } catch {
    return null;
  }
}

export function MaterialsScreen({ onboarding, onReady, onBack, onMenu }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [over, setOver] = useState(false);
  const [links, setLinks] = useState<string[]>([]);
  const [linkDraft, setLinkDraft] = useState("");
  const [linkError, setLinkError] = useState(false);
  const [jobUrl, setJobUrl] = useState("");
  const [jobText, setJobText] = useState("");
  const [paste, setPaste] = useState(false);
  const [session, setSession] = useState<CreateSessionResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    const ok = Array.from(list).filter((f) => /\.(pdf|txt|md)$/i.test(f.name));
    setFiles((prev) => [...prev, ...ok.filter((f) => !prev.some((p) => p.name === f.name))]);
    setSession(null);
  };

  const addLink = () => {
    const url = toUrl(linkDraft);
    if (!url) {
      setLinkError(true);
      return;
    }
    setLinks((prev) => (prev.includes(url) ? prev : [...prev, url]));
    setLinkDraft("");
    setLinkError(false);
    setSession(null);
  };

  const submit = async () => {
    setError(null);
    setBusy(true);
    try {
      let s = session;
      if (!s) {
        s = await api.createSession(files, links, paste ? undefined : toUrl(jobUrl) ?? (jobUrl.trim() || undefined), paste ? jobText.trim() : undefined);
        setSession(s);
      } else if (paste && jobText.trim()) {
        await api.setJobText(s.session_id, jobText.trim());
        s = { ...s, job_text_ok: true };
        setSession(s);
      }
      if (!s.job_text_ok) {
        setPaste(true);
        return;
      }
      onReady(s.session_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const chars = (name: string) => session?.files.find((f) => f.name === name)?.chars;
  const linkChars = (url: string) => session?.links.find((l) => l.url === url)?.chars;
  const hasJob = paste ? jobText.trim() !== "" : jobUrl.trim() !== "";
  const canSubmit = (files.length > 0 || links.length > 0) && hasJob && !busy;

  return (
    <div className="screen">
      {onboarding ? <Stepper now={1} /> : <Menubar current="new" onGo={onMenu} />}
      <main className="page">
        <div className="col w-lg">
          <div className="head">
            <h1>나와 지원할 곳을 알려 주세요</h1>
            <p className="lede">자료가 많을수록 질문이 구체적이에요. 이력서와 공고는 꼭 필요해요.</p>
          </div>

          <div className="split">
            <section className="card glass">
              <h2>내 자료</h2>
              <button
                type="button"
                className={`drop ${over ? "over" : ""}`}
                onClick={() => input.current?.click()}
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
                <Icon.upload />
                <strong style={{ fontWeight: 600 }}>이력서·경력기술서·포트폴리오를 끌어오거나 눌러서 고르세요</strong>
                <span className="sub small">여러 개 올려도 돼요</span>
              </button>
              <input ref={input} type="file" accept={ACCEPT} multiple hidden onChange={(e) => addFiles(e.target.files)} />

              {files.length > 0 && (
                <ul className="files">
                  {files.map((f) => {
                    const c = chars(f.name);
                    return (
                      <li key={f.name} className={`sunk ${c === 0 ? "warn" : ""}`}>
                        <span className="ext">{ext(f.name)}</span>
                        <span className="name">{f.name}</span>
                        <span className="meta">
                          {c === undefined ? `${Math.ceil(f.size / 1024)}KB` : c === 0 ? "글자를 못 읽었어요 · 이미지 PDF" : `${c.toLocaleString()}자 읽음`}
                        </span>
                        <button
                          className="icon-btn"
                          aria-label={`${f.name} 빼기`}
                          onClick={() => {
                            setFiles((prev) => prev.filter((p) => p !== f));
                            setSession(null);
                          }}
                        >
                          <Icon.close />
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}

              <div className="field">
                <label htmlFor="my-link">링크 추가</label>
                <div className="link-row">
                  <input
                    id="my-link"
                    type="url"
                    placeholder="GitHub · 블로그 · 포트폴리오 주소"
                    value={linkDraft}
                    aria-invalid={linkError}
                    onChange={(e) => {
                      setLinkDraft(e.target.value);
                      setLinkError(false);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.nativeEvent.isComposing) {
                        e.preventDefault();
                        addLink();
                      }
                    }}
                  />
                  <button className="btn" onClick={addLink} disabled={!linkDraft.trim()}>
                    추가
                  </button>
                </div>
                {linkError && <span className="field-err">주소를 다시 확인해 주세요. 예: https://github.com/내아이디</span>}
              </div>

              {links.length > 0 && (
                <ul className="files">
                  {links.map((url) => {
                    const c = linkChars(url);
                    return (
                      <li key={url} className={`sunk ${c === 0 ? "warn" : ""}`}>
                        <span className="ext url">URL</span>
                        <span className="name">{url.replace(/^https?:\/\//, "").replace(/\/$/, "")}</span>
                        <span className="meta">{c === undefined ? "" : c === 0 ? "내용을 못 읽었어요" : `${c.toLocaleString()}자 읽음`}</span>
                        <button
                          className="icon-btn"
                          aria-label={`${url} 빼기`}
                          onClick={() => {
                            setLinks((prev) => prev.filter((p) => p !== url));
                            setSession(null);
                          }}
                        >
                          <Icon.close />
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <section className="card glass">
              <h2>지원할 공고</h2>
              {!paste ? (
                <div className="field">
                  <label htmlFor="job-url">공고 링크</label>
                  <input
                    id="job-url"
                    type="url"
                    placeholder="채용 공고 주소를 붙여넣어 주세요"
                    value={jobUrl}
                    onChange={(e) => {
                      setJobUrl(e.target.value);
                      setSession(null);
                    }}
                  />
                  <button className="linkish" style={{ alignSelf: "flex-start" }} onClick={() => setPaste(true)}>
                    링크 대신 공고 내용을 붙여넣기
                  </button>
                </div>
              ) : (
                <div className="field">
                  {session && !session.job_text_ok && (
                    <div className="callout warn" style={{ fontSize: 14 }}>
                      <Icon.warn />
                      <span>이 링크에서는 공고를 읽지 못했어요. 공고 내용을 복사해서 붙여넣어 주세요.</span>
                    </div>
                  )}
                  <label htmlFor="job-text">공고 내용</label>
                  <textarea
                    id="job-text"
                    placeholder="자격 요건, 우대 사항, 하는 일을 포함해 붙여넣어 주세요"
                    value={jobText}
                    onChange={(e) => setJobText(e.target.value)}
                  />
                  <button className="linkish" style={{ alignSelf: "flex-start" }} onClick={() => setPaste(false)}>
                    링크로 입력하기
                  </button>
                </div>
              )}
              <p className="sub small" style={{ marginTop: "auto", lineHeight: 1.6 }}>
                링크는 페이지 내용을 가져올 때만 인터넷을 써요. 분석과 면접은 모두 이 맥에서 해요.
              </p>
            </section>
          </div>

          {error && (
            <div className="callout err">
              <span>{error}</span>
            </div>
          )}

          <div className="between">
            {onBack ? (
              <button className="btn" onClick={onBack}>
                이전
              </button>
            ) : (
              <span />
            )}
            <button className="btn btn-primary btn-lg" disabled={!canSubmit} onClick={submit}>
              {busy ? "자료 읽는 중…" : "분석 시작"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
