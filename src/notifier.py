import re

from notion_client import Client

from .models import EnrichedJob

_MAX_TEXT = 2000
_MAX_BLOCKS_PER_REQUEST = 100

_SOURCE_MAP = {
    "indeed": "Indeed",
    "linkedin": "LinkedIn",
    "greenhouse": "Greenhouse",
    "lever": "Lever",
    "gupy": "Gupy",
}

_SECTIONS = [
    ("Plano de Ação", "plano_de_acao"),
    ("O que Estudar", "o_que_estudar"),
    ("Sinais de Cultura", "sinais_de_cultura"),
    ("Red Flags", "red_flags"),
    ("Perguntas Prováveis", "perguntas_provaveis"),
    ("Resumo da Empresa", "resumo_empresa"),
    ("Análise da Empresa", "analise_empresa"),
    ("Fit Cultural", "fit_cultural"),
]


def _rich_text(content: str) -> dict:
    return {"rich_text": [{"type": "text", "text": {"content": content[:_MAX_TEXT]}}]}


def _fmt(n: float) -> str:
    return f"{n:,.0f}".replace(",", ".")


def _salary(enriched: EnrichedJob) -> str:
    job = enriched.job
    if job.salary_min and job.salary_max:
        return f"{_fmt(job.salary_min)} - {_fmt(job.salary_max)}"
    if job.salary_min:
        return f"{_fmt(job.salary_min)}+"
    if job.salary_max:
        return f"até {_fmt(job.salary_max)}"
    return ""


def _parse_inline(text: str) -> list[dict]:
    parts = []
    for i, segment in enumerate(re.split(r"\*\*(.*?)\*\*", text)):
        if not segment:
            continue
        parts.append({
            "type": "text",
            "text": {"content": segment[:_MAX_TEXT]},
            "annotations": {"bold": bool(i % 2)},
        })
    return parts or [{"type": "text", "text": {"content": text[:_MAX_TEXT]}}]


def _line_to_block(line: str) -> dict | None:
    line = line.rstrip()
    if not line:
        return None
    if line.strip() == "---":
        return {"object": "block", "type": "divider", "divider": {}}
    if line.startswith("## "):
        return {
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": _parse_inline(line[3:].strip())},
        }
    if line.startswith("### "):
        return {
            "object": "block", "type": "heading_3",
            "heading_3": {"rich_text": _parse_inline(line[4:].strip())},
        }
    if re.match(r"^[-*] ", line):
        return {
            "object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": _parse_inline(line[2:].strip())},
        }
    m = re.match(r"^\d+\.\s+(.+)", line)
    if m:
        return {
            "object": "block", "type": "numbered_list_item",
            "numbered_list_item": {"rich_text": _parse_inline(m.group(1))},
        }
    return {
        "object": "block", "type": "paragraph",
        "paragraph": {"rich_text": _parse_inline(line)},
    }


def _text_to_blocks(text: str) -> list[dict]:
    blocks = [b for line in text.split("\n") if (b := _line_to_block(line))]
    return blocks or [{
        "object": "block", "type": "paragraph",
        "paragraph": {"rich_text": _parse_inline(text)},
    }]


def build_properties(enriched: EnrichedJob) -> dict:
    job = enriched.job
    stack = sorted(set(enriched.required_hits + enriched.bonus_hits))

    props: dict = {
        "Nome": {"title": [{"type": "text", "text": {"content": job.title}}]},
        "Empresa": _rich_text(job.company),
        "URL": {"url": job.url},
        "Fonte": {"select": {"name": _SOURCE_MAP.get(job.source.lower(), job.source.capitalize())}},
        "Status": {"select": {"name": "Não Inscrito"}},
        "Score": {"number": enriched.match_score},
        "Stack detectada": {"multi_select": [{"name": s} for s in stack]},
    }

    if job.location:
        props["Localização"] = _rich_text(job.location)

    if job.is_remote is True:
        props["Modalidade"] = {"select": {"name": "Remoto"}}
    elif job.is_remote is False:
        props["Modalidade"] = {"select": {"name": "Presencial"}}

    if job.job_level:
        props["Senioridade"] = {"select": {"name": job.job_level}}

    if job.date_posted:
        props["Data da vaga"] = {"date": {"start": job.date_posted.isoformat()}}

    salary = _salary(enriched)
    if salary:
        props["Salário"] = _rich_text(salary)

    return props


def build_blocks(enriched: EnrichedJob) -> list[dict]:
    blocks: list[dict] = []
    for i, (label, field) in enumerate(_SECTIONS):
        if i > 0:
            blocks.append({"object": "block", "type": "divider", "divider": {}})
        blocks.append({
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": label}}]},
        })
        blocks.extend(_text_to_blocks(getattr(enriched, field)))
    return blocks


def push_job(client: Client, database_id: str, enriched: EnrichedJob) -> None:
    blocks = build_blocks(enriched)
    page = client.pages.create(
        parent={"database_id": database_id},
        properties=build_properties(enriched),
        children=blocks[:_MAX_BLOCKS_PER_REQUEST],
    )
    remaining = blocks[_MAX_BLOCKS_PER_REQUEST:]
    while remaining:
        client.blocks.children.append(
            block_id=page["id"],
            children=remaining[:_MAX_BLOCKS_PER_REQUEST],
        )
        remaining = remaining[_MAX_BLOCKS_PER_REQUEST:]
