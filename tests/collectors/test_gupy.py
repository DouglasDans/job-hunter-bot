import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import httpx

from src.collectors.gupy import _row_to_job, collect_gupy_jobs
from src.models import Profile


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def make_profile(**kwargs) -> Profile:
    defaults = dict(
        keywords=["desenvolvedor java"],
        location="Brazil",
        stack_groups=[["Java"]],
        bonus_stack=[],
        seniority=[],
        modality=[],
        dealbreakers=[],
        hours_old=24,
    )
    defaults.update(kwargs)
    return Profile(**defaults)


def make_item(**kwargs) -> dict:
    defaults = dict(
        name="Desenvolvedor Java Pleno",
        careerPageName="Acme Corp",
        jobUrl="https://acme.gupy.io/job/1",
        description="Trabalhe com Java&nbsp;e Spring.",
        isRemoteWork=True,
        city="",
        state="",
        country="Brasil",
        publishedDate=_iso(datetime.now(UTC) - timedelta(hours=1)),
    )
    defaults.update(kwargs)
    return defaults


def make_response(items: list[dict]) -> httpx.Response:
    return httpx.Response(
        200,
        json={"data": items, "pagination": {"total": len(items), "limit": 20, "offset": 0}},
        request=httpx.Request("GET", "https://employability-portal.gupy.io/api/v1/jobs"),
    )


def test_row_to_job_maps_all_fields():
    job = _row_to_job(make_item())
    assert job is not None
    assert job.title == "Desenvolvedor Java Pleno"
    assert job.company == "Acme Corp"
    assert job.url == "https://acme.gupy.io/job/1"
    assert job.source == "gupy"
    assert job.description == "Trabalhe com Java e Spring."
    assert job.is_remote is True
    assert job.job_level is None
    assert job.salary_min is None
    assert job.salary_max is None


def test_row_to_job_location_uses_city_state_when_present():
    job = _row_to_job(make_item(city="São Paulo", state="São Paulo", country="Brasil"))
    assert job.location == "São Paulo, São Paulo"


def test_row_to_job_location_falls_back_to_country_when_no_city():
    job = _row_to_job(make_item(city="", state="", country="Brasil"))
    assert job.location == "Brasil"


def test_row_to_job_missing_url_returns_none():
    assert _row_to_job(make_item(jobUrl="")) is None


def test_collect_gupy_jobs_filters_by_hours_old():
    profile = make_profile(hours_old=24)
    recent = make_item(
        jobUrl="https://acme.gupy.io/job/recent",
        publishedDate=_iso(datetime.now(UTC) - timedelta(hours=1)),
    )
    old = make_item(
        jobUrl="https://acme.gupy.io/job/old",
        publishedDate=_iso(datetime.now(UTC) - timedelta(hours=48)),
    )
    with patch("src.collectors.gupy.httpx.get", return_value=make_response([recent, old])):
        jobs = collect_gupy_jobs(profile)

    urls = [j.url for j in jobs]
    assert urls == ["https://acme.gupy.io/job/recent"]


def test_collect_gupy_jobs_dedups_url_across_keywords():
    profile = make_profile(keywords=["java", "spring"])
    item = make_item(jobUrl="https://acme.gupy.io/job/1")
    with patch("src.collectors.gupy.httpx.get", return_value=make_response([item])) as mock_get:
        jobs = collect_gupy_jobs(profile)

    assert len(jobs) == 1
    assert mock_get.call_count == 2


def test_collect_gupy_jobs_continues_on_http_error(caplog):
    profile = make_profile(keywords=["java", "spring"])
    ok_item = make_item(jobUrl="https://acme.gupy.io/job/1")

    def side_effect(url, params, timeout):
        if params["jobName"] == "java":
            raise httpx.ConnectTimeout("boom")
        return make_response([ok_item])

    with (
        patch("src.collectors.gupy.httpx.get", side_effect=side_effect),
        caplog.at_level(logging.WARNING),
    ):
        jobs = collect_gupy_jobs(profile)

    assert len(jobs) == 1
    assert "java" in caplog.text


def test_collect_gupy_jobs_no_keywords_returns_empty():
    profile = make_profile(keywords=[])
    assert collect_gupy_jobs(profile) == []
