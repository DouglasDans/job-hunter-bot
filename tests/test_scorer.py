import pytest
from src.models import Job, Profile
from src.scorer import score_job, score_jobs

PROFILE = Profile(
    keywords=["React developer"],
    location="Brazil",
    required_stack=["React", "TypeScript"],
    bonus_stack=["PostgreSQL", "Docker"],
    seniority="Pleno",
    modality="Remoto",
    dealbreakers=["PHP", "Delphi"],
    score_threshold=5.0,
    hours_old=24,
)


def make_job(description: str = "", title: str = "Software Engineer") -> Job:
    return Job(title=title, company="Acme", url="https://example.com/1", source="indeed", description=description)


def test_all_required_hits():
    result = score_job(make_job("We use React and TypeScript in our stack."), PROFILE)
    assert result is not None
    assert result.score == 7.0
    assert sorted(result.required_hits) == ["React", "TypeScript"]
    assert result.bonus_hits == []


def test_all_hits():
    result = score_job(make_job("React TypeScript PostgreSQL Docker stack."), PROFILE)
    assert result is not None
    assert result.score == 10.0
    assert sorted(result.required_hits) == ["React", "TypeScript"]
    assert sorted(result.bonus_hits) == ["Docker", "PostgreSQL"]


def test_partial_required_hits():
    profile = PROFILE.model_copy(update={"score_threshold": 0.0})
    result = score_job(make_job("We use React for our frontend. Backend is Java."), profile)
    assert result is not None
    assert result.score == 3.5
    assert result.required_hits == ["React"]


def test_dealbreaker_vetoes():
    result = score_job(make_job("We use PHP and React."), PROFILE)
    assert result is None


def test_dealbreaker_in_title():
    result = score_job(make_job(title="PHP Developer", description="React is used too."), PROFILE)
    assert result is None


def test_below_threshold_returns_none():
    result = score_job(make_job("Pure JavaScript shop, no TypeScript."), PROFILE)
    assert result is None


def test_empty_required_stack_passes():
    profile = PROFILE.model_copy(update={"required_stack": [], "score_threshold": 0.0})
    result = score_job(make_job("We use Go and Rust."), profile)
    assert result is not None
    assert result.score == 7.0


def test_case_insensitive():
    result = score_job(make_job("Experience with REACT and TYPESCRIPT required."), PROFILE)
    assert result is not None
    assert "React" in result.required_hits
    assert "TypeScript" in result.required_hits


def test_score_jobs_filters_nones_and_sorts():
    jobs = [
        make_job("React TypeScript PostgreSQL Docker"),  # 10.0
        make_job("PHP developer"),                       # dealbreaker → None
        make_job("React developer, java backend"),       # 3.5 < threshold → None
        make_job("React TypeScript Docker"),             # 8.5
    ]
    results = score_jobs(jobs, PROFILE)
    assert len(results) == 2
    assert results[0].score == 10.0
    assert results[1].score == 8.5


def test_score_jobs_empty_input():
    assert score_jobs([], PROFILE) == []


def test_is_remote_false_vetoes():
    result = score_job(make_job("React TypeScript", title="React Dev"), PROFILE)
    assert result is not None
    presencial = make_job("React TypeScript")
    presencial = presencial.model_copy(update={"is_remote": False})
    assert score_job(presencial, PROFILE) is None


def test_is_remote_none_passes():
    job = make_job("React TypeScript").model_copy(update={"is_remote": None})
    assert score_job(job, PROFILE) is not None


def test_is_remote_true_passes():
    job = make_job("React TypeScript").model_copy(update={"is_remote": True})
    assert score_job(job, PROFILE) is not None
