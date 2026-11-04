import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { AudioQueue } from "../audio/player";
import { Recorder, type MicState } from "../audio/recorder";
import { Avatar } from "../avatar/Avatar";
import type { Analysis, ServerEvent, Stage } from "../types";
import { STAGES } from "../types";

interface Props {
  sessionId: string;
  analysis: Analysis;
  onFinished: () => void;
  onLeave: () => void;
}

type Phase = "connecting" | "speaking" | "listening" | "thinking" | "reporting";

interface LogLine {
  who: "interviewer" | "me";
  text: string;
}

const STATUS: Record<Phase, string> = {
  connecting: "면접관을 부르는 중…",
  speaking: "면접관이 말하는 중",
  listening: "듣고 있어요",
  thinking: "답변을 정리하는 중…",
  reporting: "피드백을 만드는 중…",
};

export function InterviewScreen({ sessionId, analysis, onFinished, onLeave }: Props) {
  const [phase, setPhase] = useState<Phase>("connecting");
  const [stage, setStage] = useState<Stage>("intro");
  const [subtitle, setSubtitle] = useState("");
  const [myLine, setMyLine] = useState("");
  const [log, setLog] = useState<LogLine[]>([]);
  const [mic, setMic] = useState<MicState>("off");
  const [micError, setMicError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [vrmUrl, setVrmUrl] = useState<string>();

  const ws = useRef<WebSocket | null>(null);
  const queue = useRef<AudioQueue | null>(null);
  const recorder = useRef<Recorder | null>(null);
  const micReady = useRef(false);
  const turnDone = useRef(false);
  const finished = useRef(false);
  const newTurn = useRef(true);
  const orb = useRef<HTMLDivElement>(null);
  const onFinishedRef = useRef(onFinished);
  onFinishedRef.current = onFinished;

  const startListening = useCallback(() => {
    if (finished.current) return;
    setPhase("listening");
    if (micReady.current) recorder.current?.start();
  }, []);

  // When the turn text is complete and all audio has played, hand the floor to the candidate.
  const maybeListen = useCallback(() => {
    if (turnDone.current && !queue.current?.isPlaying) {
      turnDone.current = false;
      startListening();
    }
  }, [startListening]);

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
    rec
      .init()
      .then(() => (micReady.current = true))
      .catch(() => setMicError("마이크를 쓸 수 없어요. 시스템 설정에서 마이크 권한을 허용하거나, 아래 입력칸에 답변을 입력하세요."));

    const sock = api.openInterview(sessionId);
    ws.current = sock;
    sock.onopen = () => sock.send(JSON.stringify({ type: "start" }));
    sock.onclose = () => {
      if (!finished.current) setError("백엔드와 연결이 끊겼어요. 백엔드가 실행 중인지 확인해 주세요.");
    };
    sock.onmessage = (ev) => {
      if (ev.data instanceof ArrayBuffer) {
        q.enqueue(ev.data);
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
          }
          break;
        case "question_text_delta":
          if (newTurn.current) {
            newTurn.current = false;
            setSubtitle("");
            setMyLine("");
          }
          setSubtitle((s) => s + m.text);
          break;
        case "transcript":
          setMyLine(m.text);
          setLog((l) => [...l, { who: "me", text: m.text }]);
          break;
        case "turn_done":
          setStage(m.stage);
          if (m.text) setLog((l) => [...l, { who: "interviewer", text: m.text }]);
          if (m.finished) finished.current = true;
          turnDone.current = true;
          maybeListen();
          break;
        case "reporting":
          setPhase("reporting");
          break;
        case "finished":
          finished.current = true;
          onFinishedRef.current();
          break;
        case "error":
          setError(m.message);
          turnDone.current = true;
          maybeListen();
          break;
      }
    };

    return () => {
      finished.current = true;
      sock.close();
      rec.destroy();
      q.close();
    };
  }, [sessionId, maybeListen]);

  // Mic orb glow follows the candidate's voice.
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const lv = recorder.current?.level() ?? 0;
      if (orb.current) orb.current.style.boxShadow = `0 0 0 ${4 + lv * 26}px rgba(69,184,156,${0.15 + lv * 0.35})`;
      raf = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(raf);
  }, []);

  const getLevel = useCallback(() => queue.current?.level() ?? 0, []);
  const onVrmError = useCallback((msg: string) => setError(msg), []);

  const finishAnswer = () => {
    if (phase !== "listening") return;
    if (micReady.current) recorder.current?.forceEnd();
    else if (typed.trim()) sendTyped();
  };

  const sendTyped = () => {
    if (!typed.trim() || phase !== "listening") return;
    recorder.current?.pause();
    setPhase("thinking");
    ws.current?.send(JSON.stringify({ type: "text_answer", text: typed.trim() }));
    setTyped("");
  };

  const endInterview = () => {
    if (finished.current) return;
    recorder.current?.pause();
    setPhase("thinking");
    ws.current?.send(JSON.stringify({ type: "end_interview" }));
  };

  const stageIdx = STAGES.findIndex((s) => s.key === stage);
  const tileClass = phase === "speaking" ? "speaking" : phase === "listening" ? "listening" : "";

  return (
    <div className="room">
      <header className="room-top">
        <div className="room-title">
          {analysis.job.company || "모의 면접"}
          <small>{analysis.job.role}</small>
        </div>
        <div className="progress" aria-label="면접 단계">
          {STAGES.map((s, i) => (
            <span key={s.key} className={i < stageIdx ? "done" : i === stageIdx ? "now" : ""}>
              {s.label}
            </span>
          ))}
        </div>
        <label className="btn btn-ghost" style={{ color: "var(--room-muted)" }}>
          아바타 바꾸기
          <input
            type="file"
            accept=".vrm"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) setVrmUrl(URL.createObjectURL(f));
            }}
          />
        </label>
      </header>

      <div className="stage-area">
        <div className={`tile ${tileClass}`}>
          <Avatar getLevel={getLevel} speaking={phase === "speaking"} vrmUrl={vrmUrl} onVrmError={onVrmError} />
          <span className="tile-name">면접관</span>
        </div>
        <aside className="side">
          <div className={`tile self-tile ${phase === "listening" ? "listening" : ""}`}>
            <div className="mic-orb" ref={orb} aria-hidden>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <rect x="9" y="3" width="6" height="11" rx="3" />
                <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
              </svg>
            </div>
            <span className="tile-name">나 · {mic === "speaking" ? "말하는 중" : mic === "waiting" ? "듣는 중" : "대기"}</span>
          </div>
          <div className="log" aria-label="대화 기록">
            {log.map((l, i) => (
              <div key={i}>
                <div className={`who ${l.who === "me" ? "me" : ""}`}>{l.who === "me" ? "나" : "면접관"}</div>
                <div>{l.text}</div>
              </div>
            ))}
          </div>
        </aside>
      </div>

      <div className="subtitle" aria-live="polite">
        {subtitle || (phase === "connecting" ? "" : " ")}
        {myLine && phase === "thinking" && <div className="me">{myLine}</div>}
        {error && <div className="error" style={{ fontSize: 14 }}>{error}</div>}
        {micError && <div className="error" style={{ fontSize: 14 }}>{micError}</div>}
      </div>

      <div className="controls">
        <span className="status-pill">{STATUS[phase]}</span>
        {(micError || !micReady.current) && (
          <div className="typing">
            <input
              type="text"
              placeholder="답변 입력"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && sendTyped()}
              disabled={phase !== "listening"}
            />
          </div>
        )}
        <button className="btn btn-listen" onClick={finishAnswer} disabled={phase !== "listening"}>
          답변 완료
        </button>
        <button className="btn btn-end" onClick={endInterview} disabled={phase === "reporting"}>
          면접 종료
        </button>
        {error && (
          <button className="btn" onClick={onLeave}>
            나가기
          </button>
        )}
      </div>
    </div>
  );
}
