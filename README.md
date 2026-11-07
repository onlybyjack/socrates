
# Socrates

**내 맥 안에서만 돌아가는 AI 모의 면접관**

이력서와 공고를 넣으면, 그 직무에서 20년 일한 면접관이 목소리로 묻고 끝까지 파고듭니다.

macOS (Apple Silicon) · 한국어 · 오프라인 · 무료


---

면접 준비를 혼자 하다 보면 정작 필요한 건 "내 이력서를 읽고, 내 답을 듣고, 애매한 부분을 다시 찌르는 사람"입니다. Socrates는 그 역할을 하는 데스크톱 앱입니다.

- 이력서와 지원할 공고를 넣으면 **내 이력서에서 파고들 지점**을 먼저 찾습니다.
- 면접관이 **목소리로** 질문하고, 나는 **말로** 답합니다. 채팅으로 답해도 됩니다.
- 답이 모호하면 "왜 그렇게 했는지, 다른 선택지는 왜 안 했는지, 본인 역할은 어디까지였는지" **꼬리 질문**으로 이어갑니다.
- 끝나면 질문마다 **아첨 없는 피드백**을 줍니다. 근거가 없으면 잘한 점도 비워 둡니다.

그리고 이 모든 것이 **내 맥 안에서만** 일어납니다. 이력서, 답변 음성, 대화 기록은 어디로도 보내지 않습니다. 계정도, 구독도, API 키도 필요 없습니다.

## 주요 기능

| | |
|---|---|
| 🎯 **이력서 × 공고 분석** | 공고가 원하는 사람과 내 경험을 맞춰 보고 강점, 비어 보이는 곳, 파고들 지점을 정리합니다. |
| 🎙 **음성 면접** | 면접관 자막이 목소리에 맞춰 나오고, 내 답은 말이 끝나면 알아서 받아 적습니다. |
| 🔎 **꼬리 질문** | 자기소개 → 지원 동기 → 경력·경험 → 직무·기술 순서로, 질문마다 최대 두 번 더 파고듭니다. |
| 🧠 **용어를 알아듣는 면접관** | 받아쓰기가 "센터리"라고 적어도 Sentry로 알아듣고, "Sentry 말씀하신 거군요."라고 짚고 넘어갑니다. |
| 📝 **냉정한 피드백** | 질문별 잘한 점, 아쉬운 점, 내 이력서의 경험을 짚은 "이렇게 답해 보세요"를 줍니다. |
| 🔁 **다시 면접** | 같은 이력서와 공고로 분석 없이 바로 다시 연습합니다. |
| 🔒 **완전 로컬** | 인터넷은 공고·링크를 가져올 때와 모델을 처음 받을 때만 씁니다. |

## 설치

### 필요한 것

- Apple Silicon 맥 (M1 이상), 메모리 **16GB 이상** 권장
- macOS 13 이상
- [Ollama](https://ollama.com/download): 로컬 LLM 실행기. 설치만 해 두면 모델은 앱이 받습니다.
- 디스크 여유 공간 약 8GB (모델: LLM 약 5GB, 받아쓰기 약 1.6GB, 목소리 약 400MB)

### 내려받기

1. GitHub **Releases**에서 최신 `Socrates_x.y.z_aarch64.dmg`를 받습니다.
2. `.dmg`를 열고 Socrates를 응용 프로그램 폴더로 옮깁니다.
3. 처음 열 때 "확인되지 않은 개발자" 경고가 뜨면, Socrates를 **오른쪽 클릭 → 열기**로 엽니다.
   경고가 계속되면 터미널에서 한 번 실행합니다.
   ```bash
   xattr -dr com.apple.quarantine /Applications/Socrates.app
   ```
   (아직 Apple 공증을 받지 않은 앱이라 생기는 경고입니다.)
4. 첫 실행 화면에서 모델을 알아서 내려받습니다. 인터넷 속도에 따라 몇 분 걸리고, 다음부터는 몇 초면 켜집니다.

## 사용법

1. **마이크 확인:** 권한을 허용하고 마이크를 고른 뒤 문장을 읽어 소리가 들어오는지 봅니다. 마이크 없이 채팅으로 해도 됩니다.
2. **자료 넣기:** 이력서·경력기술서·포트폴리오(PDF, TXT, MD), GitHub이나 블로그 링크, 지원할 공고의 링크나 본문을 넣습니다.
3. **면접 준비:** 분석 결과를 훑어보고 **면접 시작**을 누릅니다.
4. **면접:** 질문을 듣고 말로 답합니다. 잠깐 멈추면 답이 끝난 것으로 보고, 바로 넘기고 싶으면 **Space**를 누릅니다. 언제든 **면접 끝내기**로 마칠 수 있습니다.
5. **피드백:** 면접이 끝나면 피드백이 만들어집니다. 다른 화면에 가 있어도 계속 만듭니다.

조용한 곳에서, 실제 면접처럼 소리 내어 답할 때 가장 효과가 좋습니다.

## 개인정보

- 이력서, 공고, 답변 음성, 대화 기록, 피드백은 모두 내 맥에만 저장됩니다.
  - 기록: `~/Library/Application Support/interview-agent/interview.db`
  - 지우고 싶으면 이 폴더를 지우면 됩니다.
- 앱이 인터넷을 쓰는 경우는 세 가지뿐입니다: 내가 넣은 링크의 페이지를 가져올 때, 모델을 처음 내려받을 때, Ollama가 모델을 받을 때.
- 분석, 받아쓰기, 질문 생성, 목소리, 피드백은 모두 이 맥의 GPU·CPU에서 돌아갑니다.

## 작동 방식

```
┌──────────── 앱 (Tauri 2 · React · TypeScript) ──────────────┐
│ 마이크 → 음성 구간 감지(silero VAD) → 답변 음성               │
│ 면접관 음성 재생 → 문장별 자막                                 │
└──────────────┬──────────── WebSocket ─────────────────────────┘
               ▼
┌──────────── 로컬 백엔드 (Python · FastAPI) ───────────────────┐
│ 받아쓰기   mlx-whisper (내 자료의 기술 용어를 힌트로 사용)     │
│ 용어 교정  소리 나는 대로 적힌 기술 이름을 원래 이름으로        │
│ 면접 진행  단계 상태 머신 + 꼬리 질문 (LLM 스트리밍)            │
│ 목소리     Supertonic 3 (세션마다 남/여 면접관 무작위)          │
│ 피드백     질문별 평가 (백그라운드)        저장  SQLite         │
└──────────────┬────────────────────────────────────────────────┘
               ▼
        Ollama · qwen3:8b
```

답이 끝나면 받아쓰기 → 용어 교정 → LLM이 꼬리 질문을 할지 다음 주제로 갈지 정하며 말을 스트리밍 → 문장마다 바로 목소리로 바꿔 재생합니다. M 시리즈 맥에서 답이 끝난 뒤 첫 음성까지 보통 1~3초 걸립니다.

정해진 질문 목록을 읽는 게 아니라, 분석에서 뽑은 주제를 바탕으로 매번 내 답에 맞춰 다음 말을 새로 만듭니다.

## 알려진 한계

- 기본 모델이 8B라서 질문이 가끔 비슷하게 반복되거나 깊이가 아쉬울 수 있습니다.
- 피드백을 만드는 동안(GPU 사용) 새 면접을 시작하면 첫 질문이 늦게 나올 수 있습니다.
- 한국어 면접만 지원합니다.
- Intel 맥과 Windows는 지원하지 않습니다(받아쓰기가 Apple Silicon 전용입니다).

## 소스에서 빌드하기

필요한 것: Python 3.12+와 [uv](https://docs.astral.sh/uv/), Node 20+와 pnpm, Rust(rustup), Ollama

### 개발 모드

터미널 두 개를 씁니다. 개발 모드에서는 앱이 백엔드를 켜지 않습니다.

```bash
# 터미널 1: 백엔드 (127.0.0.1:8765)
cd backend
uv sync
uv run python -m interview_agent

# 터미널 2: 앱
cd app
pnpm install
pnpm tauri dev
```

- 화면 코드(`app/src`)는 저장하면 바로 반영됩니다. 백엔드는 바꾼 뒤 다시 켜야 합니다.
- 앱 창에서 오른쪽 클릭 → 검사(Inspect)로 개발자 도구를 엽니다.
- Homebrew로 rustup을 설치했다면 `export PATH="/opt/homebrew/opt/rustup/bin:$PATH"`가 필요할 수 있습니다.
- 8765 포트가 이미 쓰이고 있다면: `lsof -ti:8765 | xargs kill`

터미널에서 텍스트로만 면접해 볼 수도 있습니다.

```bash
cd backend
uv run python -m interview_agent.cli --resume ~/resume.pdf --job-url https://...
```

### 배포용 .dmg

```bash
./scripts/build-dmg.sh
# → app/src-tauri/target/release/bundle/dmg/*.dmg
```

백엔드를 PyInstaller로 묶어 앱 안에 넣습니다. 패키징한 앱은 백엔드를 스스로 켜고 끕니다. 로그: `~/Library/Logs/interview-agent/backend.log`

### 테스트

```bash
cd backend && uv run pytest
cd app && pnpm build
```

### 설정 (환경 변수)

| 변수 | 기본값 | |
|---|---|---|
| `IA_LLM_MODEL` | `qwen3:8b` | Ollama 모델 이름 |
| `IA_OLLAMA_URL` | `http://localhost:11434` | |
| `IA_STT_MODEL` | `mlx-community/whisper-large-v3-turbo` | |
| `IA_TTS_VOICES` | `M3,F2` | 세션마다 이 중에서 무작위 |
| `IA_DATA_DIR` | `~/Library/Application Support/interview-agent` | |
| `IA_PORT` | `8765` | |

### 프로젝트 구조

```
app/        Tauri 앱 (React · TypeScript), src-tauri/ 는 Rust 셸
backend/    FastAPI 백엔드, tests/, packaging/ (PyInstaller)
scripts/    .dmg 빌드 스크립트
```

## 기여하기

이슈와 PR 모두 환영합니다. 특히 이런 도움이 필요합니다.

- 더 날카로운 꼬리 질문을 위한 프롬프트 개선, 작은 모델 튜닝
- 직무별(프론트엔드, 데이터, 디자인, PM 등) 면접 흐름
- 다른 언어 지원

PR 전에 `cd backend && uv run pytest`와 `cd app && pnpm build`가 통과하는지 확인해 주세요.

## 로드맵

- [ ] 면접 길이 선택 (짧게 · 보통 · 길게)
- [ ] 피드백 생성 중에도 면접 질문을 먼저 처리
- [ ] 더 큰 모델 선택 (qwen3:14b 등)
- [ ] 마이크 확인에서 받아쓰기 미리보기, 면접관 목소리 들어보기
- [ ] Apple 공증

## 감사의 말

Socrates는 이 오픈소스 프로젝트들 위에 만들어졌습니다.

- [Qwen3](https://github.com/QwenLM/Qwen3) (Apache 2.0) · [Ollama](https://github.com/ollama/ollama)
- [Whisper](https://github.com/openai/whisper) (MIT) · [mlx-whisper](https://github.com/ml-explore/mlx-examples)
- [Supertonic](https://huggingface.co/Supertone/supertonic-3) (코드 MIT, 모델 OpenRAIL-M)
- [Silero VAD](https://github.com/snakers4/silero-vad) (MIT) · [vad-web](https://github.com/ricky0123/vad)
- [Tauri](https://tauri.app) · [FastAPI](https://fastapi.tiangolo.com) · [Pretendard](https://github.com/orioncactus/pretendard)

Supertonic 모델은 OpenRAIL-M 라이선스의 사용 제한(사칭 등 악용 금지)을 따릅니다.

## 라이선스

[MIT](LICENSE)
