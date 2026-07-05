import logging
import re

from .models import Job, Profile, ScoredJob

logger = logging.getLogger(__name__)

_SYNONYM_GROUPS = [
    {"node.js", "nodejs", "node"},
    {".net", "dotnet", "asp.net"},
    {"c#", "csharp"},
    {"react", "reactjs"},
    {"next.js", "nextjs"},
    {"spring", "spring boot"},
    {"nest", "nestjs"},
    {"llm", "llms"},
]

_MODALITY_TERMS = {"presencial", "on-site", "on site"}
_REMOTE_SIGNALS = {"remoto", "remota", "remote", "híbrido", "hibrido", "hybrid", "home office"}

_SENIOR_VETO_TOKENS = {
    "senior", "sênior", "sr", "iii", "especialista", "staff", "lead", "principal",
}
_POSITIVE_SENIORITY_TOKENS = {
    "pleno": "Pleno",
    "pl": "Pleno",
    "júnior": "Junior",
    "junior": "Junior",
    "jr": "Junior",
}


def _variants(term: str) -> set[str]:
    key = term.lower().strip()
    for group in _SYNONYM_GROUPS:
        if key in group:
            return group
    return {key}


def _contains_term(text: str, term: str) -> bool:
    for variant in _variants(term):
        pattern = r"(?<![a-z0-9])" + re.escape(variant) + r"(?![a-z0-9])"
        if re.search(pattern, text):
            return True
    return False


def _title_tokens(title: str) -> set[str]:
    return set(re.findall(r"[\w#+]+", title.lower()))


def _is_modality_dealbreaker(entry: str) -> bool:
    entry_lower = entry.lower()
    return any(term in entry_lower for term in _MODALITY_TERMS)


def _dealbreaker_veto(job: Job, profile: Profile) -> str | None:
    text = f"{job.title} {job.description}".lower()
    for dealbreaker in profile.dealbreakers:
        if _is_modality_dealbreaker(dealbreaker):
            continue
        if _contains_term(text, dealbreaker):
            return dealbreaker
    return None


def _modality_veto(job: Job, profile: Profile) -> str | None:
    title_location = f"{job.title} {job.location}".lower()
    if job.is_remote is True or any(_contains_term(title_location, s) for s in _REMOTE_SIGNALS):
        return None

    has_modality_dealbreaker = any(_is_modality_dealbreaker(d) for d in profile.dealbreakers)
    if has_modality_dealbreaker and any(
        _contains_term(title_location, term) for term in _MODALITY_TERMS
    ):
        return "modality dealbreaker in title/location"

    if job.is_remote is False and set(profile.modality) == {"Remoto"}:
        return "is_remote=False and profile only accepts Remoto"

    return None


def _seniority_veto(job: Job, profile: Profile) -> bool:
    if not profile.seniority or "Senior" in profile.seniority:
        return False
    if _title_tokens(job.title) & _SENIOR_VETO_TOKENS:
        return True
    if job.job_level and _contains_term(job.job_level.lower(), "senior"):
        return True
    return False


def _seniority_signal(job: Job) -> str | None:
    tokens = _title_tokens(job.title)
    for token, label in _POSITIVE_SENIORITY_TOKENS.items():
        if token in tokens:
            return label
    return None


def score_job(job: Job, profile: Profile) -> ScoredJob | None:
    if _seniority_veto(job, profile):
        logger.info("Vetada (senioridade): %s @ %s", job.title, job.company)
        return None

    modality_reason = _modality_veto(job, profile)
    if modality_reason:
        logger.info("Vetada (modalidade: %s): %s @ %s", modality_reason, job.title, job.company)
        return None

    dealbreaker = _dealbreaker_veto(job, profile)
    if dealbreaker:
        logger.info("Vetada (dealbreaker: %s): %s @ %s", dealbreaker, job.title, job.company)
        return None

    text = f"{job.title} {job.description}".lower()
    stack_hits = [
        tech for group in profile.stack_groups for tech in group if _contains_term(text, tech)
    ]
    bonus_hits = [tech for tech in profile.bonus_stack if _contains_term(text, tech)]
    matched_groups = sum(
        1 for group in profile.stack_groups if any(_contains_term(text, tech) for tech in group)
    )

    required_score = 7 * matched_groups / len(profile.stack_groups)
    bonus_score = 3 * len(bonus_hits) / len(profile.bonus_stack) if profile.bonus_stack else 0.0
    score = round(required_score + bonus_score, 1)

    if score < profile.score_threshold:
        logger.info(
            "Descartada (score %.1f < threshold %.1f): %s @ %s",
            score, profile.score_threshold, job.title, job.company,
        )
        return None

    return ScoredJob(
        job=job,
        score=score,
        stack_hits=stack_hits,
        bonus_hits=bonus_hits,
        seniority_signal=_seniority_signal(job),
    )


def score_jobs(jobs: list[Job], profile: Profile) -> list[ScoredJob]:
    scored = [score_job(job, profile) for job in jobs]
    return sorted([s for s in scored if s is not None], key=lambda s: s.score, reverse=True)
