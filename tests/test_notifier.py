from datetime import date

from src.models import EnrichedJob, Job
from src.notifier import _parse_inline, _text_to_blocks, build_blocks, build_properties, push_job

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
    stack_hits=["React", "TypeScript"],
    bonus_hits=["Docker"],
    body_markdown=(
        "## Plano de Ação\n"
        "Prepare portfolio.\n\n"
        "## O que Estudar\n"
        "Review advanced TypeScript.\n\n"
        "## Sinais de Cultura\n"
        "Remote-first culture.\n\n"
        "## Red Flags\n"
        "No salary disclosed.\n\n"
        "## Perguntas Prováveis\n"
        "Explain React hooks.\n\n"
        "## Resumo da Empresa\n"
        "Acme is a B2B SaaS company.\n\n"
        "## Análise da Empresa\n"
        "Acme was founded in 2010, 500 employees, B2B SaaS.\n\n"
        "## Fit Cultural\n"
        "Strong remote culture, horizontal structure, good fit."
    ),
    match_score=8.5,
)


class _StubChildren:
    def __init__(self):
        self.appended: list[list] = []

    def append(self, block_id: str, children: list) -> None:
        self.appended.append(children)


class _StubBlocks:
    def __init__(self):
        self.children = _StubChildren()


class _StubNotionClient:
    def __init__(self):
        self.calls: list[dict] = []
        self.pages = self
        self.blocks = _StubBlocks()

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return {"id": "fake-page-id"}


def test_parse_inline_plain_text():
    parts = _parse_inline("Hello world")
    assert len(parts) == 1
    assert parts[0]["text"]["content"] == "Hello world"
    assert parts[0]["annotations"]["bold"] is False


def test_parse_inline_bold():
    parts = _parse_inline("Use **React** aqui")
    texts = [(p["text"]["content"], p["annotations"]["bold"]) for p in parts]
    assert ("Use ", False) in texts
    assert ("React", True) in texts
    assert (" aqui", False) in texts


def test_parse_inline_multiple_bold():
    parts = _parse_inline("**A** e **B**")
    bold_texts = [p["text"]["content"] for p in parts if p["annotations"]["bold"]]
    assert "A" in bold_texts
    assert "B" in bold_texts


def test_parse_inline_empty_string():
    parts = _parse_inline("")
    assert isinstance(parts, list)
    assert len(parts) >= 1


def test_parse_inline_italic():
    parts = _parse_inline("*Resposta esperada*: detalhe")
    texts = [(p["text"]["content"], p["annotations"]["italic"]) for p in parts]
    assert ("Resposta esperada", True) in texts
    assert (": detalhe", False) in texts


def test_parse_inline_italic_quoted_sentence():
    parts = _parse_inline('*"Tenho experiência fullstack"*')
    italic = [p["text"]["content"] for p in parts if p["annotations"]["italic"]]
    assert italic == ['"Tenho experiência fullstack"']


def test_parse_inline_inline_code():
    parts = _parse_inline("rode `npm test` antes")
    code = [p["text"]["content"] for p in parts if p["annotations"]["code"]]
    assert code == ["npm test"]
    plain = [p["text"]["content"] for p in parts if not p["annotations"]["code"]]
    assert "rode " in plain
    assert " antes" in plain


def test_parse_inline_code_content_is_literal():
    parts = _parse_inline("`**não é bold**`")
    assert len(parts) == 1
    assert parts[0]["annotations"]["code"] is True
    assert parts[0]["text"]["content"] == "**não é bold**"
    assert parts[0]["annotations"]["bold"] is False


def test_parse_inline_italic_inside_bold():
    parts = _parse_inline("**bold com *italic* dentro**")
    both = [
        p["text"]["content"]
        for p in parts
        if p["annotations"]["bold"] and p["annotations"]["italic"]
    ]
    assert both == ["italic"]
    bold_only = [
        p["text"]["content"]
        for p in parts
        if p["annotations"]["bold"] and not p["annotations"]["italic"]
    ]
    assert "bold com " in bold_only
    assert " dentro" in bold_only


def test_parse_inline_unmatched_bold_marker_dropped():
    parts = _parse_inline("**Recomendação: aplicar")
    all_text = "".join(p["text"]["content"] for p in parts)
    assert all_text == "Recomendação: aplicar"
    assert all(not p["annotations"]["bold"] for p in parts)


def test_parse_inline_unmatched_italic_marker_dropped():
    parts = _parse_inline("texto com *marcador órfão")
    all_text = "".join(p["text"]["content"] for p in parts)
    assert all_text == "texto com marcador órfão"


def test_parse_inline_unmatched_backtick_dropped():
    parts = _parse_inline("texto com ` órfão")
    all_text = "".join(p["text"]["content"] for p in parts)
    assert all_text == "texto com  órfão"
    assert all(not p["annotations"]["code"] for p in parts)


def test_parse_inline_bold_and_italic_same_line():
    parts = _parse_inline("**Prioridade baixa** e *se tiver tempo*")
    bold = [p["text"]["content"] for p in parts if p["annotations"]["bold"]]
    italic = [p["text"]["content"] for p in parts if p["annotations"]["italic"]]
    assert bold == ["Prioridade baixa"]
    assert italic == ["se tiver tempo"]


def test_parse_inline_triple_asterisk_degrades_without_literals():
    parts = _parse_inline("***ênfase máxima***")
    all_text = "".join(p["text"]["content"] for p in parts)
    assert all_text == "ênfase máxima"
    assert "*" not in all_text


def test_markdown_to_blocks_plain_paragraph():
    blocks = _text_to_blocks("Hello world")
    assert len(blocks) == 1
    assert blocks[0]["type"] == "paragraph"


def test_markdown_to_blocks_heading2():
    blocks = _text_to_blocks("## Subtítulo")
    assert blocks[0]["type"] == "heading_2"
    assert blocks[0]["heading_2"]["rich_text"][0]["text"]["content"] == "Subtítulo"


def test_markdown_to_blocks_heading3():
    blocks = _text_to_blocks("### Detalhe")
    assert blocks[0]["type"] == "heading_3"


def test_markdown_to_blocks_bullet_list():
    blocks = _text_to_blocks("- Item A\n- Item B")
    types = [b["type"] for b in blocks]
    assert types == ["bulleted_list_item", "bulleted_list_item"]


def test_markdown_to_blocks_numbered_list():
    blocks = _text_to_blocks("1. Primeiro\n2. Segundo")
    types = [b["type"] for b in blocks]
    assert types == ["numbered_list_item", "numbered_list_item"]


def test_markdown_to_blocks_divider():
    blocks = _text_to_blocks("---")
    assert blocks[0]["type"] == "divider"


def test_markdown_to_blocks_quote():
    blocks = _text_to_blocks('> "Oi Maria, vi a vaga de Fullstack"')
    assert blocks[0]["type"] == "quote"
    content = blocks[0]["quote"]["rich_text"][0]["text"]["content"]
    assert content == '"Oi Maria, vi a vaga de Fullstack"'


def test_markdown_to_blocks_quote_with_bold():
    blocks = _text_to_blocks("> valide **antes** de investir tempo")
    rich = blocks[0]["quote"]["rich_text"]
    bold = [p["text"]["content"] for p in rich if p["annotations"]["bold"]]
    assert bold == ["antes"]


def test_markdown_to_blocks_quote_no_literal_marker():
    blocks = _text_to_blocks("> citação")
    all_text = "".join(p["text"]["content"] for p in blocks[0]["quote"]["rich_text"])
    assert ">" not in all_text


def test_markdown_to_blocks_splits_on_newline():
    blocks = _text_to_blocks("First\nSecond\nThird")
    assert len(blocks) == 3


def test_markdown_to_blocks_skips_empty_lines():
    blocks = _text_to_blocks("First\n\nSecond")
    assert len(blocks) == 2


def test_markdown_to_blocks_bold_preserved():
    blocks = _text_to_blocks("**Important** item")
    rich = blocks[0]["paragraph"]["rich_text"]
    bold_parts = [p for p in rich if p["annotations"]["bold"]]
    assert any("Important" in p["text"]["content"] for p in bold_parts)


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


def test_build_properties_status_default_nao_inscrito():
    props = build_properties(_BASE_ENRICHED)
    assert props["Status"]["select"]["name"] == "Não Inscrito"


def test_build_properties_score_uses_match_score():
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


def test_build_properties_senioridade_uses_job_level_when_no_signal():
    props = build_properties(_BASE_ENRICHED)
    assert props["Senioridade"]["select"]["name"] == "Pleno"


def test_build_properties_senioridade_prefers_seniority_signal():
    enriched = _BASE_ENRICHED.model_copy(
        update={"job": _BASE_JOB.model_copy(update={"job_level": "mid-senior level"})}
    )
    enriched = enriched.model_copy(update={"seniority_signal": "Pleno"})
    props = build_properties(enriched)
    assert props["Senioridade"]["select"]["name"] == "Pleno"


def test_build_properties_omits_senioridade_when_neither_present():
    enriched = _BASE_ENRICHED.model_copy(
        update={"job": _BASE_JOB.model_copy(update={"job_level": None})}
    )
    props = build_properties(enriched)
    assert "Senioridade" not in props


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


def test_build_blocks_has_all_eight_sections():
    blocks = build_blocks(_BASE_ENRICHED)
    headings = [
        b["heading_2"]["rich_text"][0]["text"]["content"]
        for b in blocks
        if b["type"] == "heading_2"
    ]
    assert len(headings) == 8


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
    enriched = _BASE_ENRICHED.model_copy(update={"body_markdown": long_text})
    blocks = build_blocks(enriched)
    paragraphs = [b for b in blocks if b["type"] == "paragraph"]
    for p in paragraphs:
        assert len(p["paragraph"]["rich_text"][0]["text"]["content"]) <= 2000


def test_build_blocks_contains_analise_empresa():
    blocks = build_blocks(_BASE_ENRICHED)
    all_text = " ".join(
        b["paragraph"]["rich_text"][0]["text"]["content"]
        for b in blocks
        if b["type"] == "paragraph"
    )
    assert "Acme was founded in 2010" in all_text


def test_build_blocks_contains_fit_cultural():
    blocks = build_blocks(_BASE_ENRICHED)
    all_text = " ".join(
        b["paragraph"]["rich_text"][0]["text"]["content"]
        for b in blocks
        if b["type"] == "paragraph"
    )
    assert "horizontal structure" in all_text


def test_push_job_calls_pages_create():
    client = _StubNotionClient()
    push_job(client, "db-id-123", _BASE_ENRICHED)
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["parent"] == {"database_id": "db-id-123"}
    assert "Nome" in call["properties"]
    assert len(call["children"]) > 0
