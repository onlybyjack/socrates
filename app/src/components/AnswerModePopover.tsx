import { useEffect, useRef } from "react";
import type { Prefs } from "../prefs";
import { useMic } from "../audio/useMic";
import { Meter, MicDenied, MicSelect } from "./MicParts";

interface Props {
  prefs: Prefs;
  onChange: (next: Prefs) => void;
  onClose: () => void;
}

/** Floating panel above the start bar: voice or chat, which mic, and a live level check. Changes apply right away. */
export function AnswerModePopover({ prefs, onChange, onClose }: Props) {
  const voice = !prefs.textMode;
  const mic = useMic(prefs.micId, voice);
  const box = useRef<HTMLDivElement>(null);

  // Keep the chosen mic in prefs as soon as it is known or changed.
  useEffect(() => {
    if (voice && mic.access === "ok" && mic.micId && (mic.micId !== prefs.micId || (mic.label && mic.label !== prefs.micLabel))) {
      onChange({ ...prefs, micId: mic.micId, micLabel: mic.label ?? prefs.micLabel });
    }
  }, [voice, mic.access, mic.micId, mic.label]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    const onDown = (e: PointerEvent) => {
      const t = e.target as HTMLElement;
      if (!box.current?.contains(t) && !t.closest("[data-answer-toggle]")) onClose();
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", onDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onDown);
    };
  }, [onClose]);

  return (
    <div ref={box} className="answer-pop glass" role="dialog" aria-label="답변 방식">
      <div className="seg sunk" role="tablist" aria-label="답변 방식">
        <button role="tab" aria-selected={voice} onClick={() => onChange({ ...prefs, textMode: false })}>말로 답하기</button>
        <button role="tab" aria-selected={!voice} onClick={() => onChange({ ...prefs, textMode: true })}>채팅으로 답하기</button>
      </div>
      {voice ? (
        mic.access === "denied" ? (
          <MicDenied onRetry={mic.retry} />
        ) : (
          <>
            <MicSelect id="pop-mic" access={mic.access} devices={mic.devices} micId={mic.micId} onChoose={mic.choose} />
            <Meter levels={mic.levels} heard={mic.heard} />
            <p className="sub small">{mic.heard ? "잘 들려요." : "말해 보면 막대가 움직여요."}</p>
          </>
        )
      ) : (
        <p className="sub small">면접관 질문은 그대로 들리고, 답은 입력창에 써서 보내요.</p>
      )}
    </div>
  );
}
