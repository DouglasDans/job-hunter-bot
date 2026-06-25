import pandas as pd
from jobspy import scrape_jobs

from .models import Job, Profile


def _na(val) -> bool:
    try:
        return val is None or pd.isna(val)
    except TypeError:
        return False


def _safe_str(val) -> str:
    return "" if _na(val) else str(val)


def _safe_bool(val) -> bool | None:
    return None if _na(val) else bool(val)


def _safe_float(val) -> float | None:
    return None if _na(val) else float(val)


def _safe_date(val):
    return None if _na(val) else val


def _row_to_job(row: pd.Series) -> Job | None:
    url = _safe_str(row.get("job_url"))
    if not url:
        return None
    return Job(
        title=_safe_str(row.get("title")),
        company=_safe_str(row.get("company")),
        url=url,
        source=_safe_str(row.get("site")),
        description=_safe_str(row.get("description")),
        location=_safe_str(row.get("location")),
        is_remote=_safe_bool(row.get("is_remote")),
        job_level=_safe_str(row.get("job_level")) or None,
        date_posted=_safe_date(row.get("date_posted")),
        salary_min=_safe_float(row.get("min_amount")),
        salary_max=_safe_float(row.get("max_amount")),
    )


def collect_jobs(profile: Profile) -> list[Job]:
    if not profile.keywords:
        return []
    df = scrape_jobs(
        site_name=["indeed", "linkedin"],
        search_term=profile.keywords[0],
        location=profile.location,
        country_indeed="brazil",
        hours_old=profile.hours_old,
        results_wanted=20,
        description_format="markdown",
        linkedin_fetch_description=True,
    )
    jobs = []
    for _, row in df.iterrows():
        job = _row_to_job(row)
        if job is not None:
            jobs.append(job)
    return jobs
