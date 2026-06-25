from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from notion_client import Client

from .models import Job


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    kept = {k: v[0] for k, v in params.items() if k == "jk"}
    return urlunparse(parsed._replace(query=urlencode(kept), fragment=""))


def fetch_existing_urls(client: Client, database_id: str) -> set[str]:
    db = client.databases.retrieve(database_id=database_id)
    data_source_id = db["data_sources"][0]["id"]

    urls: set[str] = set()
    cursor = None
    while True:
        kwargs = {"start_cursor": cursor} if cursor else {}
        response = client.data_sources.query(data_source_id, **kwargs)
        for page in response.get("results", []):
            raw = page.get("properties", {}).get("URL", {}).get("url") or ""
            if raw:
                urls.add(normalize_url(raw))
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
    return urls


def filter_new_jobs(jobs: list[Job], existing_urls: set[str]) -> list[Job]:
    return [job for job in jobs if normalize_url(job.url) not in existing_urls]
