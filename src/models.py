from datetime import date

from pydantic import BaseModel, Field


class Profile(BaseModel):
    keywords: list[str]
    location: str
    required_stack: list[str]
    bonus_stack: list[str]
    seniority: str
    modality: str
    dealbreakers: list[str]
    score_threshold: float = Field(default=6.0)
    hours_old: int = Field(default=24)
    about_me: str = ""


class Job(BaseModel):
    title: str
    company: str
    url: str
    source: str
    description: str = ""
    location: str = ""
    is_remote: bool | None = None
    job_level: str | None = None
    date_posted: date | None = None
    salary_min: float | None = None
    salary_max: float | None = None


class ScoredJob(BaseModel):
    job: Job
    score: float
    required_hits: list[str]
    bonus_hits: list[str]


class EnrichedJob(BaseModel):
    job: Job
    score: float
    required_hits: list[str]
    bonus_hits: list[str]
    plano_de_acao: str
    o_que_estudar: str
    sinais_de_cultura: str
    red_flags: str
    perguntas_provaveis: str
    resumo_empresa: str
    analise_empresa: str
    fit_cultural: str
    match_score: float
