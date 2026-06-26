import json

import pytest

from src.enricher import (
    _ENRICHMENT_SCHEMA,
    build_system_prompt,
    build_user_prompt,
    enrich_job,
    parse_enrichment_output,
)
from src.llm.client import LLMClient
from src.models import EnrichedJob, Job, Profile, ScoredJob

PROFILE = Profile(
    keywords=["React developer"],
    location="Brazil",
    required_stack=["React", "TypeScript"],
    bonus_stack=["PostgreSQL", "Docker"],
    seniority="Pleno",
    modality="Remoto",
    dealbreakers=["PHP"],
    score_threshold=5.0,
    hours_old=24,
)

SCORED_JOB = ScoredJob(
    job=Job(
        title="Frontend Engineer",
        company="Acme Corp",
        url="https://example.com/job/1",
        source="indeed",
        description="We use React and TypeScript. Remote work. Great culture.",
        location="Brazil",
    ),
    score=7.0,
    required_hits=["React", "TypeScript"],
    bonus_hits=[],
)

VALID_JSON = json.dumps({
    "plano_de_acao": "Prepare portfolio with React projects.",
    "o_que_estudar": "Review TypeScript advanced types.",
    "sinais_de_cultura": "Mentions remote work.",
    "red_flags": "No salary range disclosed.",
    "perguntas_provaveis": "Explain React hooks lifecycle.",
    "resumo_empresa": "Acme Corp is a B2B SaaS company.",
})


class StubLLMClient(LLMClient):
    def __init__(self, response: str):
        self._response = response
        self.last_schema: dict | None = None

    def complete(self, system: str, user: str, response_schema: dict | None = None) -> str:
        self.last_schema = response_schema
        return self._response


def test_build_system_prompt_contains_required_stack():
    prompt = build_system_prompt(PROFILE)
    assert "React" in prompt
    assert "TypeScript" in prompt


def test_build_system_prompt_contains_dealbreakers():
    prompt = build_system_prompt(PROFILE)
    assert "PHP" in prompt


def test_build_user_prompt_contains_job_title():
    prompt = build_user_prompt(SCORED_JOB)
    assert "Frontend Engineer" in prompt


def test_build_user_prompt_contains_description():
    prompt = build_user_prompt(SCORED_JOB)
    assert "React and TypeScript" in prompt


def test_parse_enrichment_output_valid():
    result = parse_enrichment_output(VALID_JSON, SCORED_JOB)
    assert isinstance(result, EnrichedJob)
    assert result.job == SCORED_JOB.job
    assert result.score == SCORED_JOB.score
    assert result.plano_de_acao == "Prepare portfolio with React projects."
    assert result.resumo_empresa == "Acme Corp is a B2B SaaS company."


def test_parse_enrichment_output_invalid_json():
    with pytest.raises(ValueError, match="JSON"):
        parse_enrichment_output("not json at all", SCORED_JOB)


def test_parse_enrichment_output_missing_field():
    incomplete = json.dumps({"plano_de_acao": "Do something."})
    with pytest.raises(ValueError):
        parse_enrichment_output(incomplete, SCORED_JOB)


def test_enrich_job_returns_enriched_job():
    llm = StubLLMClient(VALID_JSON)
    result = enrich_job(SCORED_JOB, PROFILE, llm)
    assert isinstance(result, EnrichedJob)
    assert result.required_hits == ["React", "TypeScript"]
    assert result.o_que_estudar == "Review TypeScript advanced types."


def test_enrich_job_passes_schema_to_llm():
    llm = StubLLMClient(VALID_JSON)
    enrich_job(SCORED_JOB, PROFILE, llm)
    assert llm.last_schema is _ENRICHMENT_SCHEMA
    assert llm.last_schema["properties"]["plano_de_acao"] == {"type": "string"}
    assert "resumo_empresa" in llm.last_schema["required"]
