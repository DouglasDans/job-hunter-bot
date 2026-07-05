import html
import logging
from datetime import UTC, datetime, timedelta

import httpx

from ..models import Job, Profile

_API_URL = "https://employability-portal.gupy.io/api/v1/jobs"

logger = logging.getLogger(__name__)


def _parse_published_date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _row_to_job(item: dict) -> Job | None:
    url = item.get("jobUrl") or ""
    if not url:
        return None

    city = item.get("city") or ""
    state = item.get("state") or ""
    location = f"{city}, {state}" if city else item.get("country") or ""

    published = item.get("publishedDate")
    return Job(
        title=item.get("name") or "",
        company=item.get("careerPageName") or "",
        url=url,
        source="gupy",
        description=html.unescape(item.get("description") or "").replace("\xa0", " "),
        location=location,
        is_remote=item.get("isRemoteWork"),
        job_level=None,
        date_posted=_parse_published_date(published).date() if published else None,
        salary_min=None,
        salary_max=None,
    )


def collect_gupy_jobs(profile: Profile) -> list[Job]:
    if not profile.keywords:
        return []

    cutoff = datetime.now(UTC) - timedelta(hours=profile.hours_old)
    seen: set[str] = set()
    jobs: list[Job] = []

    for keyword in profile.keywords:
        try:
            response = httpx.get(
                _API_URL,
                params={"jobName": keyword, "limit": 20, "offset": 0},
                timeout=10,
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("Gupy collection failed for keyword %r: %s", keyword, e)
            continue

        for item in response.json().get("data", []):
            published = item.get("publishedDate")
            if published and _parse_published_date(published) < cutoff:
                break  # sorted desc by publishedDate; nothing further is newer

            job = _row_to_job(item)
            if job is None or job.url in seen:
                continue
            seen.add(job.url)
            jobs.append(job)

    return jobs
