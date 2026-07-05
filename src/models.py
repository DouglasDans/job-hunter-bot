from datetime import date

from pydantic import BaseModel, Field


class Profile(BaseModel):
    keywords: list[str]
    location: str
    stack_groups: list[list[str]] = Field(min_length=1)
    bonus_stack: list[str]
    seniority: list[str]
    modality: list[str]
    dealbreakers: list[str]
    score_threshold: float = Field(default=6.0)
    hours_old: int = Field(default=24)
    about_me: str = ""
    inhire_tenants: list[str] = Field(default_factory=list)


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
    stack_hits: list[str]
    bonus_hits: list[str]
    seniority_signal: str | None = None


class EnrichedJob(BaseModel):
    job: Job
    score: float
    stack_hits: list[str]
    bonus_hits: list[str]
    body_markdown: str
    match_score: float
    seniority_signal: str | None = None
