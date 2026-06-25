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
