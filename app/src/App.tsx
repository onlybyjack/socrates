import { useReducer } from "react";
import type { Analysis, Plan } from "./types";
import { HealthScreen } from "./screens/Health";
import { SetupScreen } from "./screens/Setup";
import { AnalysisScreen } from "./screens/Analysis";
import { InterviewScreen } from "./screens/Interview";
import { ReportScreen } from "./screens/Report";
import { HistoryScreen } from "./screens/History";

export type Screen =
  | { name: "health" }
  | { name: "setup" }
  | { name: "analysis"; sessionId: string; analysis: Analysis; plan: Plan }
  | { name: "interview"; sessionId: string; analysis: Analysis }
  | { name: "report"; sessionId: string }
  | { name: "history" };

function reducer(_: Screen, next: Screen): Screen {
  return next;
}

export default function App() {
  const [screen, go] = useReducer(reducer, { name: "health" });

  if (screen.name === "interview") {
    return (
      <InterviewScreen
        sessionId={screen.sessionId}
        analysis={screen.analysis}
        onFinished={() => go({ name: "report", sessionId: screen.sessionId })}
        onLeave={() => go({ name: "setup" })}
      />
    );
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          모의 면접<small>내 맥에서만 돌아가요</small>
        </div>
        <nav className="actions">
          <button className="btn btn-ghost" onClick={() => go({ name: "setup" })}>
            새 면접
          </button>
          <button className="btn btn-ghost" onClick={() => go({ name: "history" })}>
            지난 면접
          </button>
        </nav>
      </header>
      <main className="page">
        {screen.name === "health" && <HealthScreen onReady={() => go({ name: "setup" })} />}
        {screen.name === "setup" && (
          <SetupScreen onAnalyzed={(sessionId, analysis, plan) => go({ name: "analysis", sessionId, analysis, plan })} />
        )}
        {screen.name === "analysis" && (
          <AnalysisScreen
            analysis={screen.analysis}
            plan={screen.plan}
            onStart={() => go({ name: "interview", sessionId: screen.sessionId, analysis: screen.analysis })}
          />
        )}
        {screen.name === "report" && <ReportScreen sessionId={screen.sessionId} />}
        {screen.name === "history" && <HistoryScreen onOpen={(sessionId) => go({ name: "report", sessionId })} />}
      </main>
    </div>
  );
}
