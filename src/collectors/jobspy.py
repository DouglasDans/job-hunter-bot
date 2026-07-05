from datetime import UTC, datetime, timedelta

import pandas as pd
from jobspy import scrape_jobs

from ..models import Job, Profile


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

    # Google ignores the native hours_old time-window phrase once google_search_term
    # overrides the query, so we re-apply the cutoff ourselves for google-sourced rows.
    cutoff_date = (datetime.now(UTC) - timedelta(hours=profile.hours_old)).date()
    seen: set[str] = set()
    jobs: list[Job] = []

    for keyword in profile.keywords:
        df = scrape_jobs(
            site_name=["indeed", "linkedin", "google"],
            search_term=keyword,
            google_search_term=f"{keyword} vagas brasil",
            location=profile.location,
            country_indeed="brazil",
            hours_old=profile.hours_old,
            results_wanted=20,
            description_format="markdown",
            linkedin_fetch_description=True,
        )
        for _, row in df.iterrows():
            job = _row_to_job(row)
            if job is None or job.url in seen:
                continue
            if job.source == "google" and job.date_posted is not None:
                if job.date_posted < cutoff_date:
                    continue
            seen.add(job.url)
            jobs.append(job)

    return jobs
