from interview_agent.stt import vocabulary_hint, vocabulary_terms


def test_terms_come_only_from_the_candidates_materials():
    terms = vocabulary_terms(
        {"candidate": {"skills": ["Figma, Notion"]}, "job": {"required": ["Jira 사용 경험"], "preferred": ["GA4"]}},
        "프로덕트 디자이너입니다. Figma로 디자인 시스템을 만들고 Zeplin으로 넘겼습니다. The team used Slack.",
        "우대: Amplitude 분석 경험",
    )
    assert terms[:4] == ["Figma", "Notion", "Jira", "GA4"]
    assert {"Zeplin", "Slack", "Amplitude"} <= set(terms)
    assert "Kubernetes" not in terms and "The" not in terms  # no built-in dev list, no prose
    assert len({t.lower() for t in terms}) == len(terms)


def test_hint_is_empty_without_terms_and_bounded_with_them():
    assert vocabulary_hint([]) == ""
    hint = vocabulary_hint([f"Tool{i}" for i in range(200)])
    assert hint.startswith("면접 답변입니다.") and len(hint) <= 302


def test_multi_word_names_stay_whole():
    terms = vocabulary_terms({"job": {"preferred": ["Looker Studio", "Google Analytics 4 경험"]}})
    assert "Looker Studio" in terms and "Studio" not in terms
    assert "Google" in terms  # mixed with Korean prose: falls back to single names
