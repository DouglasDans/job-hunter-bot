import pytest
from src.config import parse_profile

SAMPLE_PAGE = {
    "properties": {
        "keywords": {"rich_text": [{"plain_text": "React developer, frontend engineer"}]},
        "location": {"rich_text": [{"plain_text": "Brazil"}]},
        "required_stack": {"multi_select": [{"name": "React"}, {"name": "TypeScript"}]},
        "bonus_stack": {"multi_select": [{"name": "PostgreSQL"}, {"name": "Docker"}]},
        "seniority": {"select": {"name": "Pleno"}},
        "modality": {"select": {"name": "Remoto"}},
        "dealbreakers": {"rich_text": [{"plain_text": "PHP, Delphi"}]},
        "score_threshold": {"number": 6.0},
        "hours_old": {"number": 24},
    }
}


def _with(overrides: dict) -> dict:
    return {"properties": {**SAMPLE_PAGE["properties"], **overrides}}


def test_parse_full_profile():
    profile = parse_profile(SAMPLE_PAGE)
    assert profile.keywords == ["React developer", "frontend engineer"]
    assert profile.location == "Brazil"
    assert profile.required_stack == ["React", "TypeScript"]
    assert profile.bonus_stack == ["PostgreSQL", "Docker"]
    assert profile.seniority == "Pleno"
    assert profile.modality == "Remoto"
    assert profile.dealbreakers == ["PHP", "Delphi"]
    assert profile.score_threshold == 6.0
    assert profile.hours_old == 24


def test_keywords_trimmed():
    page = _with({"keywords": {"rich_text": [{"plain_text": " React dev ,  Node engineer "}]}})
    profile = parse_profile(page)
    assert profile.keywords == ["React dev", "Node engineer"]


def test_empty_dealbreakers():
    page = _with({"dealbreakers": {"rich_text": []}})
    profile = parse_profile(page)
    assert profile.dealbreakers == []


def test_empty_stacks():
    page = _with({"required_stack": {"multi_select": []}, "bonus_stack": {"multi_select": []}})
    profile = parse_profile(page)
    assert profile.required_stack == []
    assert profile.bonus_stack == []


def test_null_score_threshold_uses_default():
    page = _with({"score_threshold": {"number": None}})
    profile = parse_profile(page)
    assert profile.score_threshold == 6.0


def test_null_hours_old_uses_default():
    page = _with({"hours_old": {"number": None}})
    profile = parse_profile(page)
    assert profile.hours_old == 24


def test_missing_select_returns_empty_string():
    page = _with({"seniority": {"select": None}})
    profile = parse_profile(page)
    assert profile.seniority == ""
