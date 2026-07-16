import re

from .llm.client import LLMClient
from .models import EnrichedJob, Profile, ScoredJob


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
        f"- Senioridade: {', '.join(profile.seniority)}",
        f"- Modalidade preferida: {', '.join(profile.modality)}",
        f"- Stack principal: {' | '.join(', '.join(g) for g in profile.stack_groups)}",
        f"- Stack bônus: {', '.join(profile.bonus_stack)}",
        f"- Dealbreakers: {', '.join(profile.dealbreakers)}",
        "",
        "Use o perfil detalhado do candidato para personalizar cada campo da análise.",
        "Plano de ação e o que estudar devem ser específicos para este candidato, não genéricos.",
        "Regras de formatação Markdown (obrigatórias):",
        "- Use apenas: **negrito**, *itálico*, `código`, listas com - ou 1.,"
        " ## subtítulos, > citações e --- como divisor.",
        "- Feche **negrito** e *itálico* sempre na mesma linha em que abriu.",
        "- Numere listas sequencialmente (1., 2., 3.) — nunca repita 1.",
        "- Sub-itens de uma lista: indente com 2 espaços sob o item pai.",
        "- Citações (ex.: mensagem sugerida de LinkedIn) em linha própria começando com > .",
        "Use emojis conforme convenção: ✅ para cada sinal positivo de cultura,"
        " 🚩 para red flags críticos, 🟠 para red flags secundários.",
        "",
        "Responda APENAS em Markdown puro, sem blocos de código, exatamente neste formato:",
        "",
        "match_score: 7.5",
        "",
        "## Plano de Ação",
        "(passos concretos e personalizados dado o seu perfil;"
        " se a vaga tiver bom fit, inclua um passo de abordagem direta:"
        " quem contatar no LinkedIn — recrutador, tech lead ou EM —"
        " e um exemplo curto de mensagem personalizada para esta vaga)",
        "",
        "## O que Estudar",
        "(lacunas específicas na sua stack antes de aplicar)",
        "",
        "## Sinais de Cultura",
        "(evidências positivas de cultura ou ambiente de trabalho — use ✅ para cada item)",
        "",
        "## Red Flags",
        "(alertas ou aspectos negativos — use 🚩 para críticos e 🟠 para secundários)",
        "",
        "## Perguntas Prováveis",
        "(perguntas técnicas ou comportamentais prováveis na entrevista)",
        "",
        "## Resumo da Empresa",
        "(contexto sobre a empresa, produto e mercado)",
        "",
        "## Análise da Empresa",
        "(histórico, reputação, cultura e benefícios da empresa)",
        "",
        "## Fit Cultural",
        "(avaliação de se a cultura da empresa bate com seus valores)",
        "",
        "match_score é um número de 0.0 a 10.0, uma casa decimal,"
        " avaliando compatibilidade candidato/vaga.",
        "A primeira linha DEVE ser 'match_score: X.X'. Nenhum texto antes ou depois do bloco.",
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


def parse_markdown_output(raw: str, scored_job: ScoredJob) -> EnrichedJob:
    raw = raw.strip()
    first_line, _, body = raw.partition("\n")
    m = re.match(r"match_score:\s*([\d.]+)", first_line.strip())
    if not m:
        raise ValueError(f"LLM output missing match_score on first line: {first_line!r}")
    match_score = float(m.group(1))
    return EnrichedJob(
        job=scored_job.job,
        score=scored_job.score,
        stack_hits=scored_job.stack_hits,
        bonus_hits=scored_job.bonus_hits,
        body_markdown=body.strip(),
        match_score=match_score,
        seniority_signal=scored_job.seniority_signal,
    )


def enrich_job(
    scored_job: ScoredJob,
    profile: Profile,
    llm: LLMClient,
    company_context: str = "",
) -> EnrichedJob:
    system = build_system_prompt(profile)
    user = build_user_prompt(scored_job, company_context=company_context)
    raw = llm.complete(system, user)
    return parse_markdown_output(raw, scored_job)
