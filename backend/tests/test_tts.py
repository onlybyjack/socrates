import sys

import pytest

from interview_agent.stt import is_hallucination
from interview_agent.tts import SupertonicTTS, pick_voice, to_wav


def test_voice_is_stable_per_session_and_both_get_used():
    voices = ("M3", "F2")
    assert pick_voice(voices, "abc") == pick_voice(voices, "abc")
    picked = {pick_voice(voices, f"session-{i}") for i in range(50)}
    assert picked == {"M3", "F2"}


def test_to_wav_is_16bit_mono():
    import wave, io

    import numpy as np

    data = to_wav(np.array([[0.0, 0.5, -0.5, 2.0]], dtype=np.float32), 44100)
    with wave.open(io.BytesIO(data)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 44100, 4)


def test_not_available_until_loaded():
    assert SupertonicTTS().available() is False


@pytest.mark.skipif(sys.platform != "darwin", reason="downloads the model; run on the dev Mac")
async def test_supertonic_speaks_korean():
    tts = SupertonicTTS()
    audio, mime = await tts.synthesize("안녕하세요.", "F2")
    assert mime == "audio/wav" and tts.available()
    assert audio[:4] == b"RIFF" and len(audio) > 20000


def test_hallucination_filter():
    assert is_hallucination("시청해주셔서 감사합니다.")
    assert is_hallucination("  구독과 좋아요 부탁드립니다!  ")
    assert is_hallucination("...")
    assert not is_hallucination("감사합니다. 저는 백엔드 개발자입니다.")


def _wav(rate: int, seconds: float = 0.5, channels: int = 1) -> bytes:
    import io
    import wave

    import numpy as np

    n = int(rate * seconds)
    t = np.arange(n) / rate
    pcm = (np.sin(2 * np.pi * 440 * t) * 0.5 * 32767).astype("<i2")
    if channels == 2:
        pcm = np.repeat(pcm, 2)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def test_load_wav_16k_passthrough_without_ffmpeg():
    from interview_agent.stt import load_wav_16k

    audio = load_wav_16k(_wav(16000))
    assert audio.dtype.name == "float32" and audio.ndim == 1
    assert len(audio) == 8000
    assert 0.45 < abs(audio).max() <= 0.51


def test_load_wav_16k_resamples_and_downmixes():
    from interview_agent.stt import load_wav_16k

    audio = load_wav_16k(_wav(22050, seconds=1.0, channels=2))
    assert audio.ndim == 1 and abs(len(audio) - 16000) <= 2
