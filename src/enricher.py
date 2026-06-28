import json

from pydantic import BaseModel, ValidationError

from .llm.client import LLMClient
from .models import EnrichedJob, Profile, ScoredJob

_ENRICHMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "plano_de_acao": {"type": "string"},
        "o_que_estudar": {"type": "string"},
        "sinais_de_cultura": {"type": "string"},
        "red_flags": {"type": "string"},
        "perguntas_provaveis": {"type": "string"},
        "resumo_empresa": {"type": "string"},
        "analise_empresa": {"type": "string"},
        "fit_cultural": {"type": "string"},
        "match_score": {"type": "number"},
    },
    "required": [
        "plano_de_acao",
        "o_que_estudar",
        "sinais_de_cultura",
        "red_flags",
        "perguntas_provaveis",
        "resumo_empresa",
        "analise_empresa",
        "fit_cultural",
        "match_score",
    ],
}


class _LLMEnrichment(BaseModel):
    plano_de_acao: str
    o_que_estudar: str
    sinais_de_cultura: str
    red_flags: str
    perguntas_provaveis: str
    resumo_empresa: str
    analise_empresa: str
    fit_cultural: str
    match_score: float


_JSON_SCHEMA = """\
{
  "plano_de_acao": "passos concretos e personalizados dado o seu perfil",
  "o_que_estudar": "lacunas específicas na sua stack antes de aplicar",
  "sinais_de_cultura": "evidências positivas de cultura ou ambiente de trabalho",
  "red_flags": "alertas ou aspectos negativos identificados na vaga ou empresa",
  "perguntas_provaveis": "perguntas técnicas ou comportamentais prováveis na entrevista",
  "resumo_empresa": "contexto sobre a empresa, produto e mercado",
  "analise_empresa": "histórico, reputação, cultura e benefícios da empresa",
  "fit_cultural": "avaliação de se a cultura da empresa bate com seus valores",
  "match_score": 7.5
}"""


def build_system_prompt(profile: Profile) -> str:
    lines = [
        "Você é um assistente pessoal de carreira ajudando um desenvolvedor"
        " a se preparar para vagas específicas.",
        "",
    ]
    if profile.about_me:
        lines += [
            "Perfil detalhado do candidato:",
            profile.about_me,
            "",
        ]
    lines += [
        "Resumo técnico:",
        f"- Senioridade: {profile.seniority}",
        f"- Modalidade preferida: {profile.modality}",
        f"- Stack principal: {', '.join(profile.required_stack)}",
        f"- Stack bônus: {', '.join(profile.bonus_stack)}",
        f"- Dealbreakers: {', '.join(profile.dealbreakers)}",
        "",
        "Use o perfil detalhado do candidato para personalizar cada campo da análise.",
        "Plano de ação e o que estudar devem ser específicos para este candidato, não genéricos.",
        "Formate cada campo em Markdown: use **negrito** para destaques, - para listas,"
        " ## para subtítulos e \\n entre itens. Os campos são strings JSON com \\n literal.",
        "match_score é sua avaliação de compatibilidade candidato/vaga"
        " (0.0 a 10.0, uma casa decimal).",
        "",
        f"Responda em JSON com exatamente estes campos:\n{_JSON_SCHEMA}",
        "",
        "Responda APENAS com o JSON. Nenhum texto antes ou depois.",
    ]
    return "\n".join(lines)


def build_user_prompt(scored_job: ScoredJob, company_context: str = "") -> str:
    job = scored_job.job
    parts = [
        f"Título: {job.title}\n"
        f"Empresa: {job.company}\n"
        f"Localização: {job.location or 'não informada'}\n"
        f"Score técnico (keyword matching): {scored_job.score}/10\n\n"
        f"Descrição da vaga:\n{job.description}"
    ]
    if company_context:
        parts.append(f"\n\nInformações externas sobre a empresa:\n{company_context}")
    return "".join(parts)


def _extract_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n", 1)
        raw = lines[1] if len(lines) > 1 else ""
        if raw.endswith("```"):
            raw = raw[:-3].rstrip()
    return raw


def parse_enrichment_output(raw: str, scored_job: ScoredJob) -> EnrichedJob:
    raw = _extract_json(raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}") from e
    try:
        enrichment = _LLMEnrichment.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"LLM output missing required fields: {e}") from e
    return EnrichedJob(
        job=scored_job.job,
        score=scored_job.score,
        required_hits=scored_job.required_hits,
        bonus_hits=scored_job.bonus_hits,
        **enrichment.model_dump(),
    )


def enrich_job(
    scored_job: ScoredJob,
    profile: Profile,
    llm: LLMClient,
    company_context: str = "",
) -> EnrichedJob:
    system = build_system_prompt(profile)
    user = build_user_prompt(scored_job, company_context=company_context)
    raw = llm.complete(system, user, response_schema=_ENRICHMENT_SCHEMA)
    return parse_enrichment_output(raw, scored_job)
