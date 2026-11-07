from interview_agent.stt import vocabulary_hint


def test_hint_uses_candidate_and_job_terms_first():
    hint = vocabulary_hint({
        "candidate": {"skills": ["Python, FastAPI", "Google Gemini API"]},
        "job": {"required": ["Kubernetes 운영 경험"], "preferred": ["사내 RAG 구축"]},
    })
    assert hint.startswith("개발자 기술 면접 답변입니다. 용어: Python, FastAPI, Google, Gemini, API, Kubernetes, RAG")
    assert hint.lower().count("python") == 1  # base list does not repeat it
    assert len(hint) <= 302


def test_hint_without_analysis_has_base_terms():
    hint = vocabulary_hint(None)
    assert "Gemini" in hint and "Whisper" in hint
