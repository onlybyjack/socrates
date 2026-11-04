import type { Analysis, CreateSessionResult, Health, Plan, Report, SessionDetail, SessionSummary } from "./types";

export const BASE = "http://127.0.0.1:8765";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, init);
  } catch {
    throw new ApiError(0, "백엔드에 연결할 수 없어요. 터미널에서 백엔드를 실행했는지 확인해 주세요.");
  }
  if (!res.ok) {
    let detail = `요청이 실패했어요 (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request<Health>("/api/health"),
  createSession: (files: File[], jobUrl?: string, jobText?: string) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    if (jobUrl) fd.append("job_url", jobUrl);
    if (jobText) fd.append("job_text", jobText);
    return request<CreateSessionResult>("/api/sessions", { method: "POST", body: fd });
  },
  setJobText: (id: string, text: string) => request<{ ok: true }>(`/api/sessions/${id}/job_text`, json({ text })),
  analyze: (id: string) => request<{ analysis: Analysis; plan: Plan }>(`/api/sessions/${id}/analyze`, { method: "POST" }),
  listSessions: () => request<SessionSummary[]>("/api/sessions"),
  getSession: (id: string) => request<SessionDetail>(`/api/sessions/${id}`),
  buildReport: (id: string) => request<Report>(`/api/sessions/${id}/report`, { method: "POST" }),
  openInterview: (id: string) => {
    const ws = new WebSocket(BASE.replace("http", "ws") + `/ws/interview/${id}`);
    ws.binaryType = "arraybuffer";
    return ws;
  },
};
