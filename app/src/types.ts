export type Stage = "intro" | "motivation" | "experience" | "technical" | "reverse_qa" | "closing";

export const STAGES: { key: Stage; label: string }[] = [
  { key: "intro", label: "자기소개" },
  { key: "motivation", label: "지원 동기" },
  { key: "experience", label: "경력·경험" },
  { key: "technical", label: "직무·기술" },
  { key: "reverse_qa", label: "역질문" },
  { key: "closing", label: "마무리" },
];

export interface Health {
  ollama: boolean;
  model_present: boolean;
  model: string;
  stt: boolean;
  stt_ready: boolean;
  tts: boolean;
}

export interface Point {
  point: string;
  evidence: string;
}

export interface Analysis {
  job: { company: string; role: string; required: string[]; preferred: string[]; duties: string[] };
  candidate: { summary: string; experiences: string[]; skills: string[] };
  match: { strengths: Point[]; gaps: Point[]; probes: { topic: string; why: string }[] };
}

export interface Topic {
  topic: string;
  intent: string;
}

export interface Plan {
  experience: Topic[];
  technical: Topic[];
}

export interface CreateSessionResult {
  session_id: string;
  files: { name: string; chars: number }[];
  job_text_ok: boolean;
  job_chars: number;
}

export interface Report {
  questions: { question: string; answer: string; good: string; improve: string; better_direction: string }[];
  overall: { summary: string; strengths: string[]; improvements: string[]; next_topics: string[] };
}

export interface Turn {
  role: "interviewer" | "candidate";
  text: string;
  stage: Stage;
  kind: string;
  created_at: string;
}

export interface SessionDetail {
  id: string;
  created_at: string;
  job_url: string | null;
  analysis: Analysis | null;
  plan: Plan | null;
  report: Report | null;
  turns: Turn[];
}

export interface SessionSummary {
  id: string;
  created_at: string;
  company: string;
  role: string;
  has_report: boolean;
}

export type ServerEvent =
  | { type: "state"; stage: Stage; speaking?: boolean; transcribing?: boolean }
  | { type: "question_text_delta"; text: string }
  | { type: "audio"; seq: number; mime: string; text: string }
  | { type: "transcript"; role: "candidate"; text: string }
  | { type: "turn_done"; stage: Stage; finished: boolean; text: string }
  | { type: "reporting" }
  | { type: "finished"; session_id: string }
  | { type: "error"; message: string };
