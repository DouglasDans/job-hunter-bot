import math

import pandas as pd
import pytest

from src.collector import _row_to_job


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
