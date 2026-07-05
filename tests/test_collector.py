import math
from unittest.mock import call, patch

import pandas as pd
import pytest

from src.collector import _row_to_job, collect_jobs
from src.models import Profile


def make_row(**kwargs) -> pd.Series:
    defaults = {
        "site": "indeed",
        "job_url": "https://example.com/job/1",
        "title": "React Developer",
        "company": "Acme Corp",
        "location": "São Paulo, Brazil",
        "description": "We use React and TypeScript.",
        "is_remote": True,
        "job_level": "Mid-Senior level",
        "date_posted": None,
        "min_amount": None,
        "max_amount": None,
    }
    defaults.update(kwargs)
    return pd.Series(defaults)


def test_row_to_job_maps_all_fields():
    job = _row_to_job(make_row())
    assert job is not None
    assert job.title == "React Developer"
    assert job.company == "Acme Corp"
    assert job.url == "https://example.com/job/1"
    assert job.source == "indeed"
    assert job.location == "São Paulo, Brazil"
    assert job.description == "We use React and TypeScript."
    assert job.is_remote is True
    assert job.job_level == "Mid-Senior level"


def test_missing_url_returns_none():
    assert _row_to_job(make_row(job_url=None)) is None


def test_nan_url_returns_none():
    assert _row_to_job(make_row(job_url=float("nan"))) is None


def test_nan_optional_fields_become_none():
    nan = float("nan")
    job = _row_to_job(make_row(is_remote=nan, min_amount=nan, max_amount=nan, job_level=nan))
    assert job is not None
    assert job.is_remote is None
    assert job.salary_min is None
    assert job.salary_max is None
    assert job.job_level is None


def test_nan_description_becomes_empty_string():
    job = _row_to_job(make_row(description=float("nan")))
    assert job is not None
    assert job.description == ""


def test_salary_fields_mapped():
    job = _row_to_job(make_row(min_amount=5000.0, max_amount=8000.0))
    assert job is not None
    assert job.salary_min == 5000.0
    assert job.salary_max == 8000.0


_PROFILE = Profile(
    keywords=["React developer", "frontend engineer"],
    location="Brazil",
    stack_groups=[["React"]],
    bonus_stack=[],
    seniority=["Pleno", "Junior"],
    modality=["Remoto"],
    dealbreakers=[],
    score_threshold=4.0,
    hours_old=168,
)


def _make_df(*urls: str) -> pd.DataFrame:
    rows = [make_row(job_url=url, title=f"Job {url}") for url in urls]
    return pd.DataFrame([r.to_dict() for r in rows])


def test_collect_jobs_calls_scrape_for_each_keyword():
    df1 = _make_df("https://example.com/1")
    df2 = _make_df("https://example.com/2")
    with patch("src.collector.scrape_jobs", side_effect=[df1, df2]) as mock_scrape:
        jobs = collect_jobs(_PROFILE)
    assert mock_scrape.call_count == 2
    assert mock_scrape.call_args_list[0][1]["search_term"] == "React developer"
    assert mock_scrape.call_args_list[1][1]["search_term"] == "frontend engineer"
    assert len(jobs) == 2


def test_collect_jobs_deduplicates_across_keywords():
    shared_url = "https://example.com/shared"
    df1 = _make_df(shared_url)
    df2 = _make_df(shared_url, "https://example.com/unique")
    with patch("src.collector.scrape_jobs", side_effect=[df1, df2]):
        jobs = collect_jobs(_PROFILE)
    urls = [j.url for j in jobs]
    assert urls.count(shared_url) == 1
    assert len(jobs) == 2


def test_collect_jobs_empty_keywords_returns_empty():
    profile = _PROFILE.model_copy(update={"keywords": []})
    with patch("src.collector.scrape_jobs") as mock_scrape:
        jobs = collect_jobs(profile)
    mock_scrape.assert_not_called()
    assert jobs == []
