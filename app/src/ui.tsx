import { useEffect, useRef, type ReactNode, createContext, useContext } from "react";

/* ---------------- icons (stroke, currentColor) ---------------- */
const S = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round" } as const;
export const Icon = {
  check: (p: { size?: number }) => (
    <svg width={p.size ?? 14} height={p.size ?? 14} viewBox="0 0 24 24" {...S} strokeWidth={2.6} aria-hidden>
      <path d="M5 12.5l4.5 4.5L19 7" />
    </svg>
  ),
  warn: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" {...S} stroke="#A15C00" aria-hidden>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.5v5.5M12 16.5v.5" />
    </svg>
  ),
  mic: (p: { size?: number }) => (
    <svg width={p.size ?? 22} height={p.size ?? 22} viewBox="0 0 24 24" {...S} strokeWidth={1.9} aria-hidden>
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  ),
  micOff: () => (
    <svg width="22" height="22" viewBox="0 0 24 24" {...S} strokeWidth={1.9} aria-hidden>
      <path d="M9 9v2a3 3 0 0 0 5.1 2.1M15 10V6a3 3 0 0 0-5.7-1.3M5 11a7 7 0 0 0 11.4 5.4M19 11a7 7 0 0 1-.6 2.8M12 18v3M3 3l18 18" />
    </svg>
  ),
  upload: () => (
    <svg width="28" height="28" viewBox="0 0 24 24" {...S} strokeWidth={1.8} stroke="#1C6EF2" aria-hidden>
      <path d="M12 16V4M7 9l5-5 5 5" />
      <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
    </svg>
  ),
  close: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" {...S} aria-hidden>
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  ),
  chevron: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" {...S} aria-hidden>
      <path d="M6 9l6 6 6-6" />
    </svg>
  ),
  right: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" {...S} stroke="#8B95A1" aria-hidden>
      <path d="M9 6l6 6-6 6" />
    </svg>
  ),
  lock: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" {...S} aria-hidden>
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </svg>
  ),
  download: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" {...S} aria-hidden>
      <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />
    </svg>
  ),
  video: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" {...S} aria-hidden>
      <path d="M15 10l5-3v10l-5-3" />
      <rect x="3" y="6" width="12" height="12" rx="2.5" />
    </svg>
  ),
};

/* ---------------- the interviewer orb ---------------- */
export type OrbPhase = "speaking" | "listening" | "thinking" | "idle";

const PALETTE: Record<OrbPhase, { base: string; blobs: string[]; glow: string }> = {
  speaking: { base: "#1C6EF2", blobs: ["#4CB6FF", "#7C5CFF", "#22D3EE", "#2F6BFF"], glow: "28,110,242" },
  listening: { base: "#0FA968", blobs: ["#34D399", "#22D3EE", "#A3E635", "#14B8A6"], glow: "15,169,104" },
  thinking: { base: "#94A3B8", blobs: ["#C7D2FE", "#A5B4FC", "#BAE6FD", "#CBD5E1"], glow: "100,116,139" },
  idle: { base: "#5B8DEF", blobs: ["#9CCBFF", "#A5B4FC", "#7DD3FC", "#6E9CFF"], glow: "28,110,242" },
};
const OFFSETS = [["-10%", "-6%"], ["30%", "-12%"], ["-4%", "34%"], ["26%", "28%"]];
const SPEEDS = [7, 9, 11, 13];

/** Siri-like gradient orb. Its scale follows `getLevel()` (0..1) every frame while speaking/listening. */
export function Orb({ phase, size = 140, getLevel, still = false }: { phase: OrbPhase; size?: number; getLevel?: () => number; still?: boolean }) {
  const el = useRef<HTMLDivElement>(null);
  const core = useRef<HTMLDivElement>(null);
  const p = PALETTE[phase];
  const live = phase === "speaking" || phase === "listening";

  // Always alive: a slow breath, plus voice-driven swell, glow and color when speaking/listening.
  useEffect(() => {
    if (still) {
      if (el.current) {
        el.current.style.transform = "";
        el.current.style.boxShadow = `0 ${size * 0.08}px ${size * 0.24}px rgba(${p.glow},0.22)`;
      }
      if (core.current) core.current.style.filter = "";
      return;
    }
    let raf = 0;
    let smooth = 0;
    const period = phase === "thinking" ? 520 : phase === "idle" ? 1100 : 850;
    const tick = (t: number) => {
      const target = live && getLevel ? Math.min(1, getLevel() * 1.4) : 0;
      // Rise fast, fall slowly, like a real voice envelope.
      smooth += (target - smooth) * (target > smooth ? 0.4 : 0.1);
      const node = el.current;
      if (node) {
        const breathe = Math.sin(t / period) * (phase === "thinking" ? 0.035 : 0.022);
        node.style.setProperty("--lv", smooth.toFixed(3));
        node.style.transform = `scale(${(1 + breathe + smooth * 0.2).toFixed(4)})`;
        // Filter goes on the inner disc: in WebKit a filter on the rounded, overflow-hidden element un-clips it (square orb).
        if (core.current) core.current.style.filter = `saturate(${(1 + smooth * 0.7).toFixed(3)}) brightness(${(1 + smooth * 0.12).toFixed(3)})`;
        node.style.boxShadow = `0 ${size * 0.08}px ${size * (0.24 + smooth * 0.5)}px rgba(${p.glow},${(0.26 + smooth * 0.4).toFixed(3)})`;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [live, getLevel, phase, size, p.glow, still]);

  const blur = Math.max(6, size * 0.11);
  return (
    <div ref={el} className="orb" style={{ width: size, height: size }} aria-hidden>
      <div ref={core} className="orb-core" style={{ background: p.base }}>
      {p.blobs.map((c, i) => (
        <span
          key={i}
          className="blob"
          style={{
            left: OFFSETS[i][0],
            top: OFFSETS[i][1],
            background: c,
            filter: `blur(${blur}px)`,
            animationDuration: `${phase === "thinking" ? SPEEDS[i] * 2 : SPEEDS[i] * (live ? 0.7 : 1)}s, ${SPEEDS[i] * 0.6}s`,
            animationPlayState: still ? "paused" : "running",
            animationDirection: i % 2 ? "reverse, alternate" : "normal, alternate",
          }}
        />
      ))}
      <span className="sheen" />
      <span className="shine" />
      <span className="rim" />
      </div>
    </div>
  );
}

/* ---------------- onboarding stepper ---------------- */
const STEPS = ["마이크", "자료", "면접 준비"];
export function Stepper({ now }: { now: 0 | 1 | 2 }) {
  return (
    <header className="topbar">
      <ol className="stepper" aria-label={`준비 단계, ${now + 1}단계 ${STEPS[now]}`}>
        {STEPS.map((s, i) => (
          <li key={s} className={i < now ? "done" : i === now ? "now" : ""}>
            {i < now && <Icon.check />}
            {i === now && <span className="dot" />}
            {s}
          </li>
        ))}
      </ol>
    </header>
  );
}

/* ---------------- app menu (after onboarding) ---------------- */
export type MenuKey = "new" | "history";
/** App-level "back" (history stack), shown left of the menu when there is somewhere to go back to. */
export const BackContext = createContext<(() => void) | null>(null);

export function Menubar({ current, onGo }: { current?: MenuKey; onGo: (k: MenuKey) => void }) {
  const back = useContext(BackContext);
  const items: [MenuKey, string][] = [
    ["new", "새 면접"],
    ["history", "지난 면접"],
  ];
  return (
    <div className="menurow">
      {back && (
        <button className="back-btn glass" onClick={back} aria-label="뒤로" title="뒤로">
          <Icon.chevron />
        </button>
      )}
    <nav className="menubar glass" aria-label="메뉴">
      {items.map(([k, label]) => (
        <button key={k} aria-current={current === k ? "page" : undefined} onClick={() => onGo(k)}>
          {label}
        </button>
      ))}
    </nav>
    </div>
  );
}

export function Screen({ children, top }: { children: ReactNode; top?: ReactNode }) {
  return (
    <div className="screen">
      {top}
      {children}
    </div>
  );
}
