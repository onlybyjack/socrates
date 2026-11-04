from interview_agent.sentences import SentenceSplitter


def test_splits_two_sentences():
    s = SentenceSplitter()
    out = s.feed("안녕하세요. 반가워요! ")
    assert out == ["안녕하세요.", "반가워요!"]
    assert s.flush() == []


def test_partial_feed_carries_over():
    s = SentenceSplitter()
    assert s.feed("자기소개를 부탁") == []
    assert s.feed("드립니다. 편하게") == ["자기소개를 부탁드립니다."]
    assert s.flush() == ["편하게"]


def test_newline_is_boundary_and_no_empty():
    s = SentenceSplitter()
    assert s.feed("좋습니다\n\n그럼 다음 질문입니다?") == ["좋습니다"]
    assert s.flush() == ["그럼 다음 질문입니다?"]


def test_decimal_not_split():
    s = SentenceSplitter()
    assert s.feed("응답 시간을 3.5초 줄였어요. ") == ["응답 시간을 3.5초 줄였어요."]
