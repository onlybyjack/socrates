import { useCallback, useState } from "react";
import type { Analysis } from "./types";
import { api } from "./api";
import { loadPrefs, savePrefs, type Prefs } from "./prefs";
import { BackContext, type MenuKey } from "./ui";
import { SplashScreen } from "./screens/Splash";
import { MicCheckScreen } from "./screens/MicCheck";
import { MaterialsScreen } from "./screens/Materials";
import { AnalyzingScreen } from "./screens/Analyzing";
import { DashboardScreen } from "./screens/Dashboard";
import { InterviewScreen } from "./screens/Interview";
import { ReportScreen } from "./screens/Report";
import { HistoryScreen } from "./screens/History";

export type Screen =
  | { name: "splash" }
  | { name: "mic" }
  | { name: "materials" }
  | { name: "analyzing"; sessionId: string }
  | { name: "dashboard"; sessionId: string; analysis: Analysis }
  | { name: "interview"; sessionId: string; analysis: Analysis }
  | { name: "report"; sessionId: string }
  | { name: "history" };

/** Never returned to with "back": loading/one-off steps. */
const PASS_THROUGH = new Set<Screen["name"]>(["splash", "mic", "analyzing", "interview"]);
/** Back button shows only on these (sub-pages). Top-level tabs (새 면접, 지난 면접) never show it. */
const SHOW_BACK = new Set<Screen["name"]>(["dashboard", "report"]);
/** Where back goes when there is no earlier page in this run. */
const BACK_FALLBACK: Partial<Record<Screen["name"], Screen>> = {
  dashboard: { name: "materials" },
  report: { name: "history" },
};

export default function App() {
  const [prefs, setPrefs] = useState<Prefs>(loadPrefs);
  // A small history stack so every screen can go back. Transitional screens are skipped on the way back.
  const [stack, setStack] = useState<Screen[]>([{ name: "splash" }]);
  const screen = stack[stack.length - 1];
  const go = useCallback((next: Screen) => setStack((st) => [...st, next].slice(-30)), []);
  const backIndex = (() => {
    for (let i = stack.length - 2; i >= 0; i--) if (!PASS_THROUGH.has(stack[i].name)) return i;
    return -1;
  })();
  const canBack = SHOW_BACK.has(screen.name);
  const back = () => {
    const fallback = BACK_FALLBACK[screen.name];
    if (backIndex >= 0) setStack((st) => st.slice(0, backIndex + 1));
    else if (fallback) setStack([fallback]);
  };
  const onboarding = !prefs.onboarded;

  const updatePrefs = (next: Prefs) => {
    setPrefs(next);
    savePrefs(next);
  };

  const menu = useCallback((k: MenuKey) => go(k === "new" ? { name: "materials" } : { name: "history" }), [go]);

  /** Same materials and analysis as a past session, fresh interview. */
  const practiceAgain = async (sessionId: string) => {
    const r = await api.retrySession(sessionId);
    go({ name: "dashboard", sessionId: r.session_id, analysis: r.analysis });
  };

  const body = (() => {
    switch (screen.name) {
      case "splash":
        return <SplashScreen onReady={() => go(prefs.onboarded ? { name: "materials" } : { name: "mic" })} />;
      case "mic":
        return (
          <MicCheckScreen
            prefs={prefs}
            onDone={(next) => {
              updatePrefs(next);
              go({ name: "materials" });
            }}
          />
        );
      case "materials":
        return (
          <MaterialsScreen
            onboarding={onboarding}
            onBack={onboarding ? () => go({ name: "mic" }) : undefined}
            onMenu={menu}
            onReady={(sessionId) => go({ name: "analyzing", sessionId })}
          />
        );
      case "analyzing":
        return (
          <AnalyzingScreen
            sessionId={screen.sessionId}
            onboarding={onboarding}
            onCancel={() => go({ name: "materials" })}
            onDone={(analysis) => go({ name: "dashboard", sessionId: screen.sessionId, analysis })}
          />
        );
      case "dashboard":
        return (
          <DashboardScreen
            sessionId={screen.sessionId}
            analysis={screen.analysis}
            prefs={prefs}
            onPrefs={updatePrefs}
            onMenu={menu}
            onOpenReport={(id) => go({ name: "report", sessionId: id })}
            onStart={() => go({ name: "interview", sessionId: screen.sessionId, analysis: screen.analysis })}
          />
        );
      case "interview":
        return (
          <InterviewScreen
            sessionId={screen.sessionId}
            analysis={screen.analysis}
            prefs={prefs}
            onFinished={() => go({ name: "report", sessionId: screen.sessionId })}
            onLeave={() => go({ name: "history" })}
          />
        );
      case "report":
        return <ReportScreen sessionId={screen.sessionId} onMenu={menu} onPracticeAgain={practiceAgain} />;
      case "history":
        return <HistoryScreen onMenu={menu} onOpen={(id) => go({ name: "report", sessionId: id })} onPracticeAgain={practiceAgain} />;
    }
  })();

  return (
    <>
      {/* Overlay title bar: lets the window be dragged from the top strip, behind the traffic lights. */}
      <div className="titlebar" data-tauri-drag-region />
      <BackContext.Provider value={canBack ? back : null}>{body}</BackContext.Provider>
    </>
  );
}
