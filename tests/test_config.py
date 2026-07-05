import pytest
from pydantic import ValidationError

from src.config import _blocks_to_text, parse_profile

SAMPLE_PAGE = {
    "properties": {
        "keywords": {"rich_text": [{"plain_text": "React developer, frontend engineer"}]},
        "location": {"rich_text": [{"plain_text": "Brazil"}]},
        "stack_groups": {"rich_text": [{"plain_text": "React, TypeScript | Node.js, Java"}]},
        "bonus_stack": {"multi_select": [{"name": "PostgreSQL"}, {"name": "Docker"}]},
        "seniority": {"multi_select": [{"name": "Pleno"}, {"name": "Junior"}]},
        "modality": {"multi_select": [{"name": "Remoto"}, {"name": "Híbrido"}]},
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
    assert profile.stack_groups == [["React", "TypeScript"], ["Node.js", "Java"]]
    assert profile.bonus_stack == ["PostgreSQL", "Docker"]
    assert profile.seniority == ["Pleno", "Junior"]
    assert profile.modality == ["Remoto", "Híbrido"]
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


def test_bonus_stack_empty():
    page = _with({"bonus_stack": {"multi_select": []}})
    profile = parse_profile(page)
    assert profile.bonus_stack == []


def test_stack_groups_malformed_filters_empty_groups():
    page = _with({"stack_groups": {"rich_text": [{"plain_text": "React |  | Node"}]}})
    profile = parse_profile(page)
    assert profile.stack_groups == [["React"], ["Node"]]


def test_stack_groups_empty_raises_validation_error():
    page = _with({"stack_groups": {"rich_text": []}})
    with pytest.raises(ValidationError):
        parse_profile(page)


def test_null_score_threshold_uses_default():
    page = _with({"score_threshold": {"number": None}})
    profile = parse_profile(page)
    assert profile.score_threshold == 6.0


def test_null_hours_old_uses_default():
    page = _with({"hours_old": {"number": None}})
    profile = parse_profile(page)
    assert profile.hours_old == 24


def test_missing_multi_select_returns_empty_list():
    page = _with({"seniority": {"multi_select": []}})
    profile = parse_profile(page)
    assert profile.seniority == []


def test_inhire_tenants_parsed_from_csv():
    page = _with({"inhire_tenants": {"rich_text": [{"plain_text": "venturus, outra_empresa"}]}})
    profile = parse_profile(page)
    assert profile.inhire_tenants == ["venturus", "outra_empresa"]


def test_inhire_tenants_defaults_empty_when_missing():
    profile = parse_profile(SAMPLE_PAGE)
    assert profile.inhire_tenants == []


def test_parse_profile_about_me_defaults_empty():
    profile = parse_profile(SAMPLE_PAGE)
    assert profile.about_me == ""


def test_parse_profile_accepts_about_me():
    profile = parse_profile(SAMPLE_PAGE, about_me="Senior frontend dev com 4 anos de experiência.")
    assert profile.about_me == "Senior frontend dev com 4 anos de experiência."


def test_blocks_to_text_extracts_paragraphs():
    response = {
        "results": [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Hello world"}]}},
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Second paragraph"}]}},
        ]
    }
    text = _blocks_to_text(response)
    assert "Hello world" in text
    assert "Second paragraph" in text


def test_blocks_to_text_ignores_empty_rich_text():
    response = {
        "results": [
            {"type": "paragraph", "paragraph": {"rich_text": []}},
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Real content"}]}},
        ]
    }
    text = _blocks_to_text(response)
    assert text == "Real content"


def test_blocks_to_text_ignores_non_text_blocks():
    response = {
        "results": [
            {"type": "image", "image": {}},
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Text block"}]}},
        ]
    }
    text = _blocks_to_text(response)
    assert text == "Text block"


def test_blocks_to_text_handles_headings():
    response = {
        "results": [
            {"type": "heading_2", "heading_2": {"rich_text": [{"plain_text": "My heading"}]}},
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Under heading"}]}},
        ]
    }
    text = _blocks_to_text(response)
    assert "My heading" in text
    assert "Under heading" in text


def test_blocks_to_text_empty_response():
    assert _blocks_to_text({"results": []}) == ""
