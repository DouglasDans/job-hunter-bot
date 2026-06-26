from notion_client import Client

from .models import EnrichedJob

_MAX_TEXT = 2000

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


def build_properties(enriched: EnrichedJob) -> dict:
    job = enriched.job
    stack = sorted(set(enriched.required_hits + enriched.bonus_hits))

    props: dict = {
        "Nome": {"title": [{"type": "text", "text": {"content": job.title}}]},
        "Empresa": _rich_text(job.company),
        "URL": {"url": job.url},
        "Fonte": {"select": {"name": _SOURCE_MAP.get(job.source.lower(), job.source.capitalize())}},
        "Status": {"select": {"name": "Inbox"}},
        "Score": {"number": enriched.score},
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
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": label}}]},
        })
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": getattr(enriched, field)[:_MAX_TEXT]}}
                ]
            },
        })
    return blocks


def push_job(client: Client, database_id: str, enriched: EnrichedJob) -> None:
    client.pages.create(
        parent={"database_id": database_id},
        properties=build_properties(enriched),
        children=build_blocks(enriched),
    )
