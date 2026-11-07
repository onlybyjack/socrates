import { Icon, Stepper } from "../ui";
import type { Prefs } from "../prefs";
import { useMic } from "../audio/useMic";
import { Meter, MicDenied, MicSelect } from "../components/MicParts";

interface Props {
  prefs: Prefs;
  onDone: (next: Prefs) => void;
}

/** First-run step: asks macOS for the microphone right away (native prompt), then lets the user pick a mic and see it working. */
export function MicCheckScreen({ prefs, onDone }: Props) {
  const mic = useMic(prefs.micId);

  const finish = (textMode: boolean) =>
    onDone({
      ...prefs,
      onboarded: true,
      textMode,
      micId: textMode ? prefs.micId : mic.micId,
      micLabel: textMode ? prefs.micLabel : mic.label,
    });

  return (
    <div className="screen">
      <Stepper now={0} />
      <main className="page">
        <div className="col w-md">
          <div className="head">
            <h1>마이크가 잘 들리는지 볼게요</h1>
            <p className="lede">아래 문장을 소리 내어 읽어 보세요. 소리가 또렷하게 들어오면 준비 끝이에요.</p>
          </div>

          <section className="card glass">
            {mic.access === "denied" ? (
              <MicDenied onRetry={mic.retry} />
            ) : (
              <div className="field">
                <label htmlFor="mic">마이크</label>
                <MicSelect id="mic" access={mic.access} devices={mic.devices} micId={mic.micId} onChoose={mic.choose} />
                <div style={{ marginTop: 6 }}>
                  <Meter levels={mic.levels} heard={mic.heard} />
                </div>
              </div>
            )}

            <div className="divider" />

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <span className="sub" style={{ fontSize: 14 }}>읽어 볼 문장</span>
              <p className="quote">“안녕하세요, 오늘 면접 잘 부탁드립니다.”</p>
              {mic.access === "ok" &&
                (mic.heard ? (
                  <div className="callout ok">
                    <span style={{ color: "var(--green-ink)" }}><Icon.check size={18} /></span>
                    <span><strong style={{ color: "var(--green-ink)" }}>잘 들려요</strong> · 목소리가 또렷하게 들어오고 있어요.</span>
                  </div>
                ) : (
                  <p className="sub" style={{ fontSize: 14 }}>아직 소리가 들리지 않아요. 문장을 읽어 보세요.</p>
                ))}
            </div>
          </section>

          <div className="between">
            <button className="btn" onClick={() => finish(true)}>
              채팅으로 답할게요
            </button>
            <button className="btn btn-primary btn-lg" style={{ minWidth: 160 }} disabled={mic.access !== "ok"} onClick={() => finish(false)}>
              다음
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
