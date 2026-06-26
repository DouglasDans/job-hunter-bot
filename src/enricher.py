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
    },
    "required": [
        "plano_de_acao",
        "o_que_estudar",
        "sinais_de_cultura",
        "red_flags",
        "perguntas_provaveis",
        "resumo_empresa",
    ],
}


class _LLMEnrichment(BaseModel):
    plano_de_acao: str
    o_que_estudar: str
    sinais_de_cultura: str
    red_flags: str
    perguntas_provaveis: str
    resumo_empresa: str


_JSON_SCHEMA = """\
{
  "plano_de_acao": "passos concretos para se candidatar a esta vaga",
  "o_que_estudar": "lacunas na stack ou conhecimentos a revisar antes de aplicar",
  "sinais_de_cultura": "evidências positivas de cultura, valores ou ambiente",
  "red_flags": "alertas, inconsistências ou aspectos negativos identificados",
  "perguntas_provaveis": "perguntas técnicas ou comportamentais na entrevista",
  "resumo_empresa": "contexto sobre a empresa, produto e mercado"
}"""


def build_system_prompt(profile: Profile) -> str:
    return (
        "Você é um assistente especializado em análise de vagas para desenvolvedores.\n\n"
        "Perfil do candidato:\n"
        f"- Senioridade: {profile.seniority}\n"
        f"- Modalidade preferida: {profile.modality}\n"
        f"- Stack principal: {', '.join(profile.required_stack)}\n"
        f"- Stack bônus: {', '.join(profile.bonus_stack)}\n"
        f"- Dealbreakers: {', '.join(profile.dealbreakers)}\n\n"
        f"Analise a vaga e responda em JSON com exatamente estes campos:\n{_JSON_SCHEMA}\n\n"
        "Responda APENAS com o JSON. Nenhum texto antes ou depois."
    )


def build_user_prompt(scored_job: ScoredJob) -> str:
    job = scored_job.job
    return (
        f"Título: {job.title}\n"
        f"Empresa: {job.company}\n"
        f"Localização: {job.location or 'não informada'}\n"
        f"Score de compatibilidade: {scored_job.score}/10\n\n"
        f"Descrição da vaga:\n{job.description}"
    )


def parse_enrichment_output(raw: str, scored_job: ScoredJob) -> EnrichedJob:
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


def enrich_job(scored_job: ScoredJob, profile: Profile, llm: LLMClient) -> EnrichedJob:
    system = build_system_prompt(profile)
    user = build_user_prompt(scored_job)
    raw = llm.complete(system, user, response_schema=_ENRICHMENT_SCHEMA)
    return parse_enrichment_output(raw, scored_job)
