import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { AudioQueue } from "../audio/player";
import { Recorder, type MicState } from "../audio/recorder";
import type { Analysis, ServerEvent, Stage } from "../types";
import { STAGES } from "../types";
import { Icon, Orb, type OrbPhase } from "../ui";
import type { Prefs } from "../prefs";

interface Props {
  sessionId: string;
  analysis: Analysis;
  prefs: Prefs;
  onFinished: () => void;
  onLeave: () => void;
}

type Phase = "connecting" | "speaking" | "listening" | "thinking" | "reporting";

interface Msg {
  who: "ai" | "me";
  text: string;
  stage: Stage;
}

const STATUS: Record<Phase, string> = {
  connecting: "면접관을 부르는 중",
  speaking: "면접관이 말하는 중",
  listening: "듣고 있어요",
  thinking: "답변을 정리하는 중",
  reporting: "피드백을 만드는 중",
};

const SHOWN_STAGES = STAGES.filter((s) => s.key !== "closing");
const label = (stage: Stage) => STAGES.find((s) => s.key === stage)?.label ?? "";
const mmss = (sec: number) => `${String(Math.floor(sec / 60)).padStart(2, "0")}:${String(sec % 60).padStart(2, "0")}`;
const MIC_DENIED = "마이크를 쓸 수 없어요. 시스템 설정에서 마이크를 허용하거나, 아래 입력칸에 답변을 입력하세요.";

export function InterviewScreen({ sessionId, analysis, prefs, onFinished, onLeave }: Props) {
  const [phase, setPhase] = useState<Phase>("connecting");
  const [stage, setStage] = useState<Stage>("intro");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [mic, setMic] = useState<MicState>("off");
  const [micOk, setMicOk] = useState(false);
  const [muted, setMuted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lost, setLost] = useState(false);
  const [typed, setTyped] = useState("");
  const [elapsed, setElapsed] = useState(0);

  const ws = useRef<WebSocket | null>(null);
  const queue = useRef<AudioQueue | null>(null);
  const recorder = useRef<Recorder | null>(null);
  const micReady = useRef(false);
  const mutedRef = useRef(false);
  const stageRef = useRef<Stage>("intro");
  const leaving = useRef(false);
  const turnDone = useRef(false);
  const finished = useRef(false);
  const newTurn = useRef(true);
  // Subtitles follow the voice: each sentence appears while its audio plays.
  const [aiPending, setAiPending] = useState(false);
  const sentenceTexts = useRef<string[]>([]);
  const turnClips = useRef(0);
  const finalText = useRef<string | null>(null);
  const revealTimers = useRef<number[]>([]);
  const chatEnd = useRef<HTMLDivElement>(null);
  const onFinishedRef = useRef(onFinished);
  onFinishedRef.current = onFinished;
  mutedRef.current = muted;
  stageRef.current = stage;

  const startListening = useCallback(() => {
    if (finished.current) return;
    setPhase("listening");
    if (!micReady.current || mutedRef.current) return;
    // getUserMedia runs here (not at init), so a denied permission surfaces now.
    recorder.current?.start().catch(() => {
      micReady.current = false;
      setMicOk(false);
      setError(MIC_DENIED);
    });
  }, []);

  /** Puts text into the current interviewer bubble, opening a new bubble at the start of a turn. */
  const appendAi = useCallback((text: string, replace = false) => {
    if (newTurn.current) {
      newTurn.current = false;
      setAiPending(false);
      setMsgs((l) => [...l, { who: "ai", text, stage: stageRef.current }]);
      return;
    }
    setMsgs((l) => {
      const last = l[l.length - 1];
      if (last?.who !== "ai") return [...l, { who: "ai", text, stage: stageRef.current }];
      const next = replace ? text : last.text ? `${last.text} ${text}` : text;
      return [...l.slice(0, -1), { ...last, text: next }];
    });
  }, []);

  /** Types `sentence` out over the length of its audio clip. */
  const revealSentence = useCallback(
    (sentence: string, seconds: number) => {
      const chars = Array.from(sentence);
      if (!seconds || chars.length < 2) return appendAi(sentence);
      appendAi("");
      const total = seconds * 1000 * 0.9;
      const step = Math.max(25, total / chars.length);
      const per = Math.max(1, Math.round((chars.length * step) / total));
      let i = 0;
      const id = window.setInterval(() => {
        const piece = chars.slice(i, i + per).join("");
        i += per;
        setMsgs((l) => {
          const last = l[l.length - 1];
          return last?.who === "ai" ? [...l.slice(0, -1), { ...last, text: last.text + piece }] : l;
        });
        if (i >= chars.length) window.clearInterval(id);
      }, step);
      revealTimers.current.push(id);
    },
    [appendAi],
  );

  /** Snap the bubble to the exact final text (spacing, anything without audio). */
  const settleText = useCallback(() => {
    const text = finalText.current;
    finalText.current = null;
    revealTimers.current.forEach((id) => window.clearInterval(id));
    revealTimers.current = [];
    setStreaming(false);
    if (text) appendAi(text, true);
    else setAiPending(false);
  }, [appendAi]);

  // When the turn text is complete and all audio has played, hand the floor to the candidate.
  const maybeListen = useCallback(() => {
    if (turnDone.current && !queue.current?.isPlaying) {
      settleText();
      turnDone.current = false;
      startListening();
    }
  }, [startListening, settleText]);

  useEffect(() => {
    const q = new AudioQueue();
    queue.current = q;
    q.onIdle(maybeListen);

    const rec = new Recorder();
    recorder.current = rec;
    rec.onState = setMic;
    rec.onAnswer = (wav) => {
      setPhase("thinking");
      if (wav) ws.current?.send(wav);
      else ws.current?.send(JSON.stringify({ type: "text_answer", text: "" }));
    };
    if (!prefs.textMode) {
      rec
        .init(prefs.micId)
        .then(() => {
          micReady.current = true;
          setMicOk(true);
        })
        .catch(() => setError(MIC_DENIED));
    }

    const sock = api.openInterview(sessionId);
    ws.current = sock;
    sock.onopen = () => sock.send(JSON.stringify({ type: "start" }));
    sock.onclose = () => {
      if (leaving.current) return;
      // Interview already over (e.g. report failed and the socket dropped): the report screen can rebuild feedback.
      if (finished.current) return onFinishedRef.current();
      setLost(true);
      setError("면접관과 연결이 끊겼어요. 지금까지의 대화는 저장돼 있어요. 지난 면접에서 피드백을 확인할 수 있어요.");
    };
    sock.onmessage = (ev) => {
      if (ev.data instanceof ArrayBuffer) {
        const sentence = sentenceTexts.current.shift() ?? "";
        q.enqueue(ev.data, (seconds) => revealSentence(sentence, seconds));
        return;
      }
      const m = JSON.parse(ev.data) as ServerEvent;
      switch (m.type) {
        case "state":
          setStage(m.stage);
          if (m.transcribing) setPhase("thinking");
          if (m.speaking) {
            setPhase("speaking");
            rec.pause();
            newTurn.current = true;
            sentenceTexts.current = [];
            turnClips.current = 0;
            finalText.current = null;
            setAiPending(true);
          }
          break;
        case "question_text_delta":
          // Text arrives before its voice; it is shown when the matching audio plays (see "audio").
          setStreaming(true);
          break;
        case "audio":
          sentenceTexts.current.push(m.text);
          turnClips.current++;
          break;
        case "transcript":
          setMsgs((l) => [...l, { who: "me", text: m.text, stage: stageRef.current }]);
          break;
        case "turn_done":
          setStage(m.stage);
          stageRef.current = m.stage;
          finalText.current = m.text || null;
          // No voice this turn (speech failed): show the text right away.
          if (turnClips.current === 0) settleText();
          if (m.finished) finished.current = true;
          turnDone.current = true;
          maybeListen();
          break;
        case "reporting":
          setPhase("reporting");
          break;
        case "finished": {
          // Feedback builds in the background now, so leave as soon as the closing words have been heard.
          finished.current = true;
          const go = () => {
            settleText();
            onFinishedRef.current();
          };
          if (q.isPlaying) q.onIdle(go);
          else go();
          break;
        }
        case "error":
          setError(m.message);
          setStreaming(false);
          turnDone.current = true;
          maybeListen();
          break;
      }
    };

    return () => {
      leaving.current = true;
      finished.current = true;
      sock.close();
      revealTimers.current.forEach((id) => window.clearInterval(id));
      rec.destroy();
      q.close();
    };
  }, [sessionId, maybeListen, revealSentence, settleText, prefs.textMode, prefs.micId]);

  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ block: "end" });
  }, [msgs, phase, error]);

  const useVoice = micOk && !muted;

  const sendTyped = useCallback(() => {
    const text = typed.trim();
    if (!text || phase !== "listening") return;
    recorder.current?.pause();
    setPhase("thinking");
    setError(null);
    ws.current?.send(JSON.stringify({ type: "text_answer", text }));
    setTyped("");
  }, [typed, phase]);

  const finishAnswer = useCallback(() => {
    if (phase !== "listening") return;
    setError(null);
    if (useVoice) recorder.current?.forceEnd();
    else sendTyped();
  }, [phase, useVoice, sendTyped]);

  // Space = 답변 완료 (ignored while typing or when a button has focus)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== "Space" || e.repeat) return;
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "BUTTON") return;
      e.preventDefault();
      finishAnswer();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [finishAnswer]);

  const toggleMute = () => {
    const next = !muted;
    setMuted(next);
    if (next) recorder.current?.pause();
    else if (phase === "listening" && micReady.current) recorder.current?.start().catch(() => setError(MIC_DENIED));
  };

  const endInterview = () => {
    if (finished.current) return;
    recorder.current?.pause();
    setPhase("thinking");
    ws.current?.send(JSON.stringify({ type: "end_interview" }));
  };

  // The interviewer's voice drives the avatar next to its bubble; the dock orb only reacts to *my* voice.
  const voiceLevel = useCallback(() => queue.current?.level() ?? 0, []);
  const micLevel = useCallback(() => recorder.current?.level() ?? 0, []);
  const orbPhase: OrbPhase = phase === "listening" ? "listening" : phase === "thinking" ? "thinking" : "idle";
  const lastAi = msgs.reduce((at, m, i) => (m.who === "ai" ? i : at), -1);
  const stageIdx = SHOWN_STAGES.findIndex((s) => s.key === stage);
  const status =
    phase === "listening" && !useVoice ? "답변을 입력해 주세요" : phase === "listening" && mic === "speaking" ? "말하는 중" : STATUS[phase];
  const lastIsMe = msgs[msgs.length - 1]?.who === "me";

  return (
    <div className="room">
      <header className="room-top glass">
        <div className="room-title">
          <strong>{analysis.job.company || "모의 면접"}</strong>
          <span>{analysis.job.role}</span>
        </div>
        <ol className="progress" aria-label={`면접 단계: ${label(stage)} 진행 중`}>
          {SHOWN_STAGES.map((s, i) => (
            <li key={s.key} className={i === stageIdx ? "now" : ""}>
              <span className="track">
                <span style={{ width: stageIdx < 0 || i < stageIdx ? "100%" : i === stageIdx ? "50%" : "0%" }} />
              </span>
              {s.label}
            </li>
          ))}
        </ol>
        <div className="row" style={{ gap: 12 }}>
          <span className="clock" aria-label="경과 시간">{mmss(elapsed)}</span>
          {lost ? (
            <button className="btn btn-danger" onClick={onLeave}>나가기</button>
          ) : (
            <button className="btn btn-danger" onClick={endInterview} disabled={phase === "reporting"}>
              면접 끝내기
            </button>
          )}
        </div>
      </header>

      <div className="chat-wrap">
        <ol className="chat" aria-label="대화" aria-live="polite">
          {msgs.map((m, i) =>
            m.who === "ai" ? (
              <li key={i} className="msg ai">
                <span className="avatar-orb">
                  <Orb
                    size={44}
                    phase={i === lastAi && phase === "speaking" ? "speaking" : "idle"}
                    getLevel={i === lastAi && phase === "speaking" ? voiceLevel : undefined}
                    still={i !== lastAi}
                  />
                </span>
                <div className="stack">
                  <div className="bubble">
                    {m.text}
                    {streaming && i === msgs.length - 1 && <span className="caret" style={{ color: "var(--blue)" }} />}
                  </div>
                  {(i === 0 || msgs[i - 2]?.stage !== m.stage) && label(m.stage) && (
                    <div className="chips">
                      <span className="chip">{label(m.stage)}</span>
                    </div>
                  )}
                </div>
              </li>
            ) : (
              <li key={i} className="msg me">
                <div className="bubble">{m.text}</div>
              </li>
            ),
          )}
          {phase === "listening" && useVoice && (
            <li className="msg me live">
              <div className="bubble">
                {mic === "speaking" ? "말하는 중" : "편하게 말씀하세요"}
                <span className="caret" />
              </div>
            </li>
          )}
          {(((phase === "thinking" || phase === "connecting") && (lastIsMe || msgs.length === 0)) || phase === "reporting" || (phase === "speaking" && aiPending)) && (
            <li className="msg ai">
              <span className="avatar-orb">
                <Orb size={44} phase="thinking" />
              </span>
              <div className="bubble" aria-label={phase === "reporting" ? "피드백을 만드는 중" : "면접관이 생각하는 중"}>
                <span className="typing">
                  <span />
                  <span />
                  <span />
                </span>
              </div>
            </li>
          )}
          {error && (
            <li className="notice" role="alert">
              {error}
            </li>
          )}
          <div ref={chatEnd} />
        </ol>
      </div>

      <footer className="dock glass">
        {phase !== "speaking" && (
          <div className="live">
            <Orb phase={orbPhase} size={44} getLevel={phase === "listening" ? micLevel : undefined} />
            <span>{status}</span>
          </div>
        )}
        {useVoice ? (
          <>
            <button className="btn btn-round" aria-label="마이크 끄기" onClick={toggleMute}>
              <Icon.mic />
            </button>
            <button
              className="btn btn-primary"
              style={{ minHeight: 52, padding: "0 26px", fontSize: 16 }}
              onClick={finishAnswer}
              disabled={phase !== "listening"}
            >
              답변 완료 <kbd>Space</kbd>
            </button>
          </>
        ) : (
          <div className="typed">
            {micOk && (
              <button className="btn btn-round off" aria-label="마이크 켜기" onClick={toggleMute}>
                <Icon.micOff />
              </button>
            )}
            <label htmlFor="typed" className="sr-only">답변 입력</label>
            <input
              id="typed"
              type="text"
              placeholder={phase === "listening" ? "답변을 입력하고 Enter" : "면접관 질문이 끝나면 입력할 수 있어요"}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && sendTyped()}
              disabled={phase !== "listening"}
            />
            <button className="btn btn-primary" style={{ minHeight: 52 }} onClick={sendTyped} disabled={phase !== "listening" || !typed.trim()}>
              보내기
            </button>
          </div>
        )}
      </footer>
    </div>
  );
}
