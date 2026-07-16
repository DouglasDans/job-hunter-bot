import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from notion_client import Client

from .models import Job


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    kept = {k: v[0] for k, v in params.items() if k == "jk"}
    return urlunparse(parsed._replace(query=urlencode(kept), fragment=""))


def normalize_company_title(company: str, title: str) -> str:
    def norm(value: str) -> str:
        return re.sub(r"\W+", " ", value.lower()).strip()

    company, title = norm(company), norm(title)
    if not company or not title:
        return ""
    return f"{company}|{title}"


def _plain_text(prop: dict, kind: str) -> str:
    return "".join(t.get("plain_text", "") for t in prop.get(kind, []))


def fetch_existing_index(client: Client, database_id: str) -> tuple[set[str], set[str]]:
    db = client.databases.retrieve(database_id=database_id)
    data_source_id = db["data_sources"][0]["id"]

    urls: set[str] = set()
    keys: set[str] = set()
    cursor = None
    while True:
        kwargs = {"start_cursor": cursor} if cursor else {}
        response = client.data_sources.query(data_source_id, **kwargs)
        for page in response.get("results", []):
            props = page.get("properties", {})
            raw = props.get("URL", {}).get("url") or ""
            if raw:
                urls.add(normalize_url(raw))
            key = normalize_company_title(
                _plain_text(props.get("Empresa", {}), "rich_text"),
                _plain_text(props.get("Nome", {}), "title"),
            )
            if key:
                keys.add(key)
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
    return urls, keys


def filter_new_jobs(
    jobs: list[Job],
    existing_urls: set[str],
    existing_keys: set[str] | None = None,
) -> list[Job]:
    seen_urls = set(existing_urls)
    seen_keys = set(existing_keys or ())
    new_jobs: list[Job] = []
    for job in jobs:
        url = normalize_url(job.url)
        key = normalize_company_title(job.company, job.title)
        if url in seen_urls or (key and key in seen_keys):
            continue
        seen_urls.add(url)
        if key:
            seen_keys.add(key)
        new_jobs.append(job)
    return new_jobs
