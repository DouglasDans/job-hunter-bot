from .models import Job, Profile, ScoredJob

_SENIOR_TITLE_TERMS = {"senior", "sênior", "sr."}
_SENIOR_JOB_LEVELS = {"senior"}


def _is_senior_job(job: Job) -> bool:
    title_words = job.title.lower().split()
    if any(term in title_words for term in _SENIOR_TITLE_TERMS):
        return True
    return job.job_level is not None and job.job_level.lower() in _SENIOR_JOB_LEVELS


def score_job(job: Job, profile: Profile) -> ScoredJob | None:
    if job.is_remote is False:
        return None

    if profile.seniority and "Senior" not in profile.seniority and _is_senior_job(job):
        return None

    text = f"{job.title} {job.description}".lower()

    for dealbreaker in profile.dealbreakers:
        if dealbreaker.lower() in text:
            return None

    required_hits = [s for s in profile.required_stack if s.lower() in text]
    bonus_hits = [s for s in profile.bonus_stack if s.lower() in text]

    n_required = len(profile.required_stack)
    required_ratio = len(required_hits) / n_required if n_required else 1.0
    bonus_ratio = len(bonus_hits) / len(profile.bonus_stack) if profile.bonus_stack else 0.0

    score = round(required_ratio * 7 + bonus_ratio * 3, 1)

    if score < profile.score_threshold:
        return None

    return ScoredJob(job=job, score=score, required_hits=required_hits, bonus_hits=bonus_hits)


def score_jobs(jobs: list[Job], profile: Profile) -> list[ScoredJob]:
    scored = [score_job(job, profile) for job in jobs]
    return sorted([s for s in scored if s is not None], key=lambda s: s.score, reverse=True)
