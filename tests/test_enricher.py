import pytest

from src.enricher import (
    build_system_prompt,
    build_user_prompt,
    enrich_job,
    parse_markdown_output,
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

PROFILE_WITH_ABOUT = Profile(
    keywords=["React developer"],
    location="Brazil",
    required_stack=["React", "TypeScript"],
    bonus_stack=["PostgreSQL", "Docker"],
    seniority="Pleno",
    modality="Remoto",
    dealbreakers=["PHP"],
    score_threshold=5.0,
    hours_old=24,
    about_me=(
        "Desenvolvedor frontend com 4 anos de experiência em React e TypeScript."
        " Gosto de ambientes remotos e culturas horizontais."
    ),
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

VALID_MARKDOWN = """\
match_score: 8.5

## Plano de Ação
Prepare portfolio with React projects.
- **Abordagem direta:** Contact tech lead on LinkedIn: "Saw your Frontend role at Acme."

## O que Estudar
Review TypeScript advanced types.

## Sinais de Cultura
✅ Mentions remote work.
✅ Flexible hours.

## Red Flags
🚩 No salary range disclosed.
🟠 No information about team size.

## Perguntas Prováveis
Explain React hooks lifecycle.

## Resumo da Empresa
Acme Corp is a B2B SaaS company.

## Análise da Empresa
Acme Corp was founded in 2010, 500 employees.

## Fit Cultural
Strong remote culture, good fit for candidate preferences.
"""


class StubLLMClient(LLMClient):
    def __init__(self, response: str):
        self._response = response

    def complete(self, system: str, user: str) -> str:
        return self._response


def test_build_system_prompt_contains_required_stack():
    prompt = build_system_prompt(PROFILE)
    assert "React" in prompt
    assert "TypeScript" in prompt


def test_build_system_prompt_contains_dealbreakers():
    prompt = build_system_prompt(PROFILE)
    assert "PHP" in prompt


def test_build_system_prompt_contains_about_me():
    prompt = build_system_prompt(PROFILE_WITH_ABOUT)
    assert "4 anos de experiência" in prompt


def test_build_system_prompt_without_about_me_still_works():
    prompt = build_system_prompt(PROFILE)
    assert "React" in prompt
    assert "TypeScript" in prompt


def test_build_user_prompt_contains_job_title():
    prompt = build_user_prompt(SCORED_JOB)
    assert "Frontend Engineer" in prompt


def test_build_user_prompt_contains_description():
    prompt = build_user_prompt(SCORED_JOB)
    assert "React and TypeScript" in prompt


def test_build_user_prompt_contains_company_context():
    prompt = build_user_prompt(SCORED_JOB, company_context="Founded 2010, 500 employees.")
    assert "Founded 2010" in prompt


def test_build_user_prompt_without_company_context_omits_section():
    prompt = build_user_prompt(SCORED_JOB)
    assert "Informações externas" not in prompt


def test_parse_markdown_output_valid():
    result = parse_markdown_output(VALID_MARKDOWN, SCORED_JOB)
    assert isinstance(result, EnrichedJob)
    assert result.job == SCORED_JOB.job
    assert result.score == SCORED_JOB.score
    assert result.match_score == 8.5


def test_parse_markdown_output_has_body_markdown():
    result = parse_markdown_output(VALID_MARKDOWN, SCORED_JOB)
    assert "## Plano de Ação" in result.body_markdown
    assert "Acme Corp is a B2B SaaS company." in result.body_markdown


def test_parse_markdown_output_missing_match_score():
    with pytest.raises(ValueError, match="match_score"):
        parse_markdown_output("## Plano de Ação\nFazer algo.", SCORED_JOB)


def test_parse_markdown_output_propagates_hits():
    result = parse_markdown_output(VALID_MARKDOWN, SCORED_JOB)
    assert result.required_hits == ["React", "TypeScript"]
    assert result.bonus_hits == []


def test_enrich_job_returns_enriched_job():
    llm = StubLLMClient(VALID_MARKDOWN)
    result = enrich_job(SCORED_JOB, PROFILE, llm)
    assert isinstance(result, EnrichedJob)
    assert result.required_hits == ["React", "TypeScript"]
    assert result.match_score == 8.5


def test_build_system_prompt_mentions_linkedin_outreach():
    prompt = build_system_prompt(PROFILE)
    assert "LinkedIn" in prompt
    assert "mensagem" in prompt


def test_build_system_prompt_uses_emoji_conventions():
    prompt = build_system_prompt(PROFILE)
    assert "✅" in prompt
    assert "🚩" in prompt
    assert "🟠" in prompt
