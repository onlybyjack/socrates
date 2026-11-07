"""End-to-end smoke test against a running backend, with real models.

Uploads the fictional fixtures, analyzes, then plays two spoken answers (synthesized with Supertonic)
over the interview WebSocket, ends the interview and checks the report.

  uv run python scripts/e2e_smoke.py [--base http://127.0.0.1:8765]
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx
import websockets

from interview_agent.tts import SupertonicTTS

FIX = Path(__file__).parent / "fixtures"
ANSWERS = [
    "안녕하세요. 오년차 백엔드 개발자 김민준입니다. 주문과 결제 서비스를 담당했습니다.",
    "결제 도메인을 더 깊게 경험하고 싶어서 지원했습니다.",
]


_tts = SupertonicTTS()


async def speak(text: str) -> bytes:
    audio, _ = await _tts.synthesize(text, "M3")
    return audio


async def main(base: str) -> None:
    async with httpx.AsyncClient(timeout=300) as c:
        r = await c.post(
            f"{base}/api/sessions",
            files=[("files", ("resume.md", (FIX / "resume.md").read_bytes()))],
            data={"job_text": (FIX / "job.txt").read_text()},
        )
        r.raise_for_status()
        sid = r.json()["session_id"]
        t = time.perf_counter()
        r = await c.post(f"{base}/api/sessions/{sid}/analyze")
        print(f"analyze {r.status_code} {time.perf_counter() - t:.1f}s")
        r.raise_for_status()

    ws_url = base.replace("http", "ws") + f"/ws/interview/{sid}"
    async with websockets.connect(ws_url, max_size=None) as ws:
        await ws.send(json.dumps({"type": "start"}))
        for i in range(len(ANSWERS) + 1):
            t0, first_audio, clips = time.perf_counter(), None, 0
            while True:
                m = await ws.recv()
                if isinstance(m, bytes):
                    clips += 1
                    first_audio = first_audio or time.perf_counter() - t0
                    continue
                d = json.loads(m)
                if d["type"] == "transcript":
                    print(f"  STT: {d['text']}")
                elif d["type"] == "error":
                    raise SystemExit(f"error: {d['message']}")
                elif d["type"] == "turn_done":
                    print(f"Q{i} [{d['stage']}] {d['text']}")
                    print(f"   clips={clips} first_audio={first_audio or 0:.2f}s total={time.perf_counter() - t0:.2f}s")
                    break
            if i < len(ANSWERS):
                await ws.send(await speak(ANSWERS[i]))
        await ws.send(json.dumps({"type": "end_interview"}))
        while True:
            m = await ws.recv()
            if not isinstance(m, bytes) and json.loads(m)["type"] == "finished":
                break

    # Feedback is built in the background after the interview ends.
    async with httpx.AsyncClient() as c:
        t = time.perf_counter()
        while (st := (await c.get(f"{base}/api/sessions/{sid}/report/status")).json())["status"] == "running":
            await asyncio.sleep(1)
        print(f"report: {st['status']} after {time.perf_counter() - t:.1f}s {st.get('message', '')}")
        rep = (await c.get(f"{base}/api/sessions/{sid}")).json()["report"]
    assert rep and rep["questions"], "report missing"
    print(f"report: {len(rep['questions'])} questions | {rep['overall']['summary'][:100]}")
    print("OK")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    asyncio.run(main(ap.parse_args().base))
