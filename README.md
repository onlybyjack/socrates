# Interview Agent — 로컬 모의 면접

이력서와 지원할 공고를 넣으면, 화면 속 면접관이 **영상통화처럼 음성으로** 질문하고, 내 음성 답변을 듣고, 그 직무에서 20년 일한 시니어처럼 꼬리 질문으로 파고드는 모의 면접 앱입니다. 끝나면 질문별 피드백과 전체 리포트를 줍니다.

**모든 처리는 내 맥 안에서** 합니다. 이력서, 답변 음성, 대화 기록은 밖으로 나가지 않습니다. 인터넷을 쓰는 요청은 공고 링크를 가져오는 것 하나뿐입니다.

## 요구 사항

- Apple Silicon 맥, 메모리 16GB 이상
- [Ollama](https://ollama.com) + `qwen3:8b` 모델 (약 5GB)
- Python 3.12+, [uv](https://docs.astral.sh/uv/)
- Node 20+, pnpm, Rust (Tauri 빌드용)
- macOS 한국어 음성 **Yuna** (시스템 설정 → 손쉬운 사용 → 읽기 및 말하기)

## 실행 (개발 모드)

```bash
# 1. Ollama와 모델
brew install ollama && brew services start ollama
ollama pull qwen3:8b

# 2. 백엔드 (127.0.0.1:8765)
cd backend
uv sync
uv run python -m interview_agent

# 3. 앱 (다른 터미널)
cd app
pnpm install
pnpm tauri dev
```

받아쓰기 모델(whisper-large-v3-turbo, 약 1.6GB)은 백엔드를 처음 켤 때 자동으로 내려받습니다.

### 터미널에서 텍스트로만 면접해 보기

```bash
cd backend
uv run python -m interview_agent.cli --resume ~/resume.pdf --job-url https://...
# 또는 --job-file job.txt, 답변 중 /end 입력 시 종료
```

## 구조

```
┌──────────── Tauri 2 앱 (React + TypeScript) ─────────────┐
│ 준비 · 분석 · 면접(three.js 아바타, VAD) · 리포트 · 기록   │
│ 마이크 → 브라우저 VAD(silero) → 답변 WAV                   │
│ 면접관 음성 재생 → 음량으로 입 모양                         │
└──────────────┬───────── REST + WebSocket ────────────────┘
               ▼
┌──────────── Python 백엔드 (FastAPI) ──────────────────────┐
│ ingest   PDF/TXT/MD, 공고 URL(trafilatura)                │
│ analysis 공고↔이력서 강점/갭/파고들 지점, 면접 계획         │
│ interview 단계 상태 머신 + 꼬리 질문 (LLM 스트리밍)         │
│ stt      mlx-whisper   tts  macOS say (엔진 교체 가능)     │
│ report   질문별 피드백   store SQLite                       │
└──────────────┬────────────────────────────────────────────┘
               ▼
        Ollama (qwen3:8b)
```

한 턴의 흐름: 답변 종료(무음 감지 또는 "답변 완료") → STT → LLM이 첫 줄에 `[FOLLOW_UP]`/`[NEXT]`를 정하며 스트리밍 → 문장 단위로 TTS → 바로 재생. M5 Pro 기준 답변 종료부터 첫 음성까지 약 1–2.5초입니다.

면접 순서: 자기소개 → 지원 동기 → 경력·경험(3) → 직무·기술(2) → 역질문 → 마무리. 메인 질문마다 꼬리 질문은 최대 2번입니다.

## 설정 (환경 변수)

| 변수 | 기본값 |
|---|---|
| `IA_LLM_MODEL` | `qwen3:8b` |
| `IA_OLLAMA_URL` | `http://localhost:11434` |
| `IA_STT_MODEL` | `mlx-community/whisper-large-v3-turbo` |
| `IA_TTS_VOICE` | `Yuna` |
| `IA_DATA_DIR` | `~/Library/Application Support/interview-agent` |
| `IA_PORT` | `8765` |

## 아바타

기본 면접관은 에셋 없이 three.js 코드로 그립니다(라이선스 걱정 없음). 면접 화면의 "아바타 바꾸기"로 직접 가진 `.vrm` 파일을 불러올 수 있습니다.

## 테스트

```bash
cd backend && uv run pytest
```

## 로드맵

- Python 백엔드를 Tauri sidecar로 묶어 `.app` 하나로 배포
- 오픈소스 한국어 TTS 엔진 추가 (`TTSEngine` 인터페이스)
- 8B 모델 LoRA 튜닝으로 "시니어처럼 파고드는 질문" 개선 (설계 문서 §10)

설계: [`docs/superpowers/specs/2026-11-04-local-mock-interview-design.md`](docs/superpowers/specs/2026-11-04-local-mock-interview-design.md)
