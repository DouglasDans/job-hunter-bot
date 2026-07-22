import html
import logging
import re
from datetime import UTC, datetime, timedelta

import httpx

from ..models import Job, Profile

logger = logging.getLogger(__name__)

_LIST_URL = "https://api.inhire.app/job-posts/public/pages"
_DETAIL_URL = "https://api.inhire.app/job-posts/public/pages/{job_id}"

_BLOCK_TAG_RE = re.compile(r"</?(p|div|li|ul|ol|h[1-6]|br)[^>]*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = _BLOCK_TAG_RE.sub("\n", value)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text).replace("\xa0", " ")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def _parse_published_at(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _detail_to_job(detail: dict, url: str, published_at: datetime | None) -> Job:
    return Job(
        title=detail.get("displayName") or "",
        company=detail.get("tenantName") or "",
        url=url,
        source="inhire",
        description=_strip_html(detail.get("description")),
        location=detail.get("location") or "",
        is_remote=detail.get("workplaceType") == "Remote",
        job_level=None,
        date_posted=published_at.date() if published_at else None,
        salary_min=None,
        salary_max=None,
    )


def collect_inhire_jobs(profile: Profile) -> list[Job]:
    if not profile.inhire_tenants:
        return []

    cutoff = datetime.now(UTC) - timedelta(hours=profile.hours_old)
    seen: set[str] = set()
    jobs: list[Job] = []

    for tenant in profile.inhire_tenants:
        try:
            list_response = httpx.get(_LIST_URL, headers={"X-Tenant": tenant}, timeout=10)
            list_response.raise_for_status()
        except (httpx.HTTPError, UnicodeError) as e:
            logger.warning("InHire list collection failed for tenant %r: %s", tenant, e)
            continue

        for item in list_response.json().get("jobsPage", []):
            job_id = item.get("jobId") or ""
            if not job_id or item.get("status") != "published":
                continue

            url = f"https://{tenant}.inhire.app/vagas/{job_id}"
            if url in seen:
                continue
            seen.add(url)

            try:
                detail_response = httpx.get(
                    _DETAIL_URL.format(job_id=job_id),
                    headers={"X-Tenant": tenant},
                    timeout=10,
                )
                detail_response.raise_for_status()
            except httpx.HTTPError as e:
                logger.warning(
                    "InHire detail collection failed for %r (tenant %r): %s", job_id, tenant, e
                )
                continue

            detail = detail_response.json()
            raw_published_at = detail.get("publishedAt")
            published_at = _parse_published_at(raw_published_at)
            if raw_published_at and published_at is None:
                logger.warning(
                    "InHire: could not parse publishedAt %r for job %r (tenant %r)",
                    raw_published_at,
                    job_id,
                    tenant,
                )
            if published_at is not None and published_at < cutoff:
                continue

            jobs.append(_detail_to_job(detail, url, published_at))

    return jobs
