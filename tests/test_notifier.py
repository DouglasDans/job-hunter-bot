from datetime import date

import pytest

from src.models import EnrichedJob, Job
from src.notifier import build_blocks, build_properties, push_job

_BASE_JOB = Job(
    title="Frontend Engineer",
    company="Acme Corp",
    url="https://example.com/job/1",
    source="indeed",
    description="React and TypeScript stack.",
    location="Brazil",
    is_remote=True,
    job_level="Pleno",
    date_posted=date(2026, 6, 20),
    salary_min=8000.0,
    salary_max=12000.0,
)

_BASE_ENRICHED = EnrichedJob(
    job=_BASE_JOB,
    score=8.5,
    required_hits=["React", "TypeScript"],
    bonus_hits=["Docker"],
    plano_de_acao="Prepare portfolio.",
    o_que_estudar="Review advanced TypeScript.",
    sinais_de_cultura="Remote-first culture.",
    red_flags="No salary disclosed.",
    perguntas_provaveis="Explain React hooks.",
    resumo_empresa="Acme is a B2B SaaS company.",
)


class _StubNotionClient:
    def __init__(self):
        self.calls: list[dict] = []
        self.pages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return {"id": "fake-page-id"}


def test_build_properties_title():
    props = build_properties(_BASE_ENRICHED)
    assert props["Nome"]["title"][0]["text"]["content"] == "Frontend Engineer"


def test_build_properties_empresa():
    props = build_properties(_BASE_ENRICHED)
    assert props["Empresa"]["rich_text"][0]["text"]["content"] == "Acme Corp"


def test_build_properties_url():
    props = build_properties(_BASE_ENRICHED)
    assert props["URL"]["url"] == "https://example.com/job/1"


def test_build_properties_fonte_indeed():
    props = build_properties(_BASE_ENRICHED)
    assert props["Fonte"]["select"]["name"] == "Indeed"


def test_build_properties_fonte_linkedin_capitalization():
    enriched = _BASE_ENRICHED.model_copy(
        update={"job": _BASE_JOB.model_copy(update={"source": "linkedin"})}
    )
    props = build_properties(enriched)
    assert props["Fonte"]["select"]["name"] == "LinkedIn"


def test_build_properties_status_default_inbox():
    props = build_properties(_BASE_ENRICHED)
    assert props["Status"]["select"]["name"] == "Inbox"


def test_build_properties_score():
    props = build_properties(_BASE_ENRICHED)
    assert props["Score"]["number"] == 8.5


def test_build_properties_stack_detectada():
    props = build_properties(_BASE_ENRICHED)
    names = {item["name"] for item in props["Stack detectada"]["multi_select"]}
    assert names == {"React", "TypeScript", "Docker"}


def test_build_properties_salary_range():
    props = build_properties(_BASE_ENRICHED)
    assert "8.000" in props["Salário"]["rich_text"][0]["text"]["content"]
    assert "12.000" in props["Salário"]["rich_text"][0]["text"]["content"]


def test_build_properties_salary_min_only():
    enriched = _BASE_ENRICHED.model_copy(
        update={"job": _BASE_JOB.model_copy(update={"salary_max": None})}
    )
    props = build_properties(enriched)
    content = props["Salário"]["rich_text"][0]["text"]["content"]
    assert "8.000" in content
    assert "+" in content


def test_build_properties_omits_salary_when_absent():
    enriched = _BASE_ENRICHED.model_copy(
        update={"job": _BASE_JOB.model_copy(update={"salary_min": None, "salary_max": None})}
    )
    props = build_properties(enriched)
    assert "Salário" not in props


def test_build_properties_date():
    props = build_properties(_BASE_ENRICHED)
    assert props["Data da vaga"]["date"]["start"] == "2026-06-20"


def test_build_properties_omits_date_when_none():
    enriched = _BASE_ENRICHED.model_copy(
        update={"job": _BASE_JOB.model_copy(update={"date_posted": None})}
    )
    props = build_properties(enriched)
    assert "Data da vaga" not in props


def test_build_properties_modalidade_remoto():
    props = build_properties(_BASE_ENRICHED)
    assert props["Modalidade"]["select"]["name"] == "Remoto"


def test_build_properties_modalidade_presencial():
    enriched = _BASE_ENRICHED.model_copy(
        update={"job": _BASE_JOB.model_copy(update={"is_remote": False})}
    )
    props = build_properties(enriched)
    assert props["Modalidade"]["select"]["name"] == "Presencial"


def test_build_properties_omits_modalidade_when_none():
    enriched = _BASE_ENRICHED.model_copy(
        update={"job": _BASE_JOB.model_copy(update={"is_remote": None})}
    )
    props = build_properties(enriched)
    assert "Modalidade" not in props


def test_build_blocks_has_all_six_sections():
    blocks = build_blocks(_BASE_ENRICHED)
    headings = [
        b["heading_2"]["rich_text"][0]["text"]["content"]
        for b in blocks
        if b["type"] == "heading_2"
    ]
    assert len(headings) == 6


def test_build_blocks_contains_enrichment_content():
    blocks = build_blocks(_BASE_ENRICHED)
    all_text = " ".join(
        b["paragraph"]["rich_text"][0]["text"]["content"]
        for b in blocks
        if b["type"] == "paragraph"
    )
    assert "Prepare portfolio." in all_text
    assert "Acme is a B2B SaaS company." in all_text


def test_build_blocks_truncates_long_text():
    long_text = "x" * 3000
    enriched = _BASE_ENRICHED.model_copy(update={"plano_de_acao": long_text})
    blocks = build_blocks(enriched)
    paragraphs = [b for b in blocks if b["type"] == "paragraph"]
    for p in paragraphs:
        assert len(p["paragraph"]["rich_text"][0]["text"]["content"]) <= 2000


def test_push_job_calls_pages_create():
    client = _StubNotionClient()
    push_job(client, "db-id-123", _BASE_ENRICHED)
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["parent"] == {"database_id": "db-id-123"}
    assert "Nome" in call["properties"]
    assert len(call["children"]) > 0
