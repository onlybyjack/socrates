import sys

import pytest

from interview_agent.stt import is_hallucination
from interview_agent.tts import MacSayTTS


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
async def test_mac_say_produces_wav():
    tts = MacSayTTS("Yuna")
    assert tts.available()
    audio, mime = await tts.synthesize("안녕하세요.")
    assert mime == "audio/wav"
    assert audio[:4] == b"RIFF" and len(audio) > 2000


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
async def test_mac_say_text_starting_with_dash_is_spoken_not_flag():
    audio, _ = await MacSayTTS("Yuna").synthesize("-v 테스트")
    assert audio[:4] == b"RIFF"


def test_unknown_voice_not_available():
    assert MacSayTTS("NoSuchVoice123").available() is False


def test_hallucination_filter():
    assert is_hallucination("시청해주셔서 감사합니다.")
    assert is_hallucination("  구독과 좋아요 부탁드립니다!  ")
    assert is_hallucination("...")
    assert not is_hallucination("감사합니다. 저는 백엔드 개발자입니다.")
