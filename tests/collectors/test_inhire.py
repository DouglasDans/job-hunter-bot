import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import httpx

from src.collectors.inhire import _strip_html, collect_inhire_jobs
from src.models import Profile

_LIST_URL = "https://api.inhire.app/job-posts/public/pages"


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def make_profile(**kwargs) -> Profile:
    defaults = dict(
        keywords=[],
        location="Brazil",
        stack_groups=[["Java"]],
        bonus_stack=[],
        seniority=[],
        modality=[],
        dealbreakers=[],
        hours_old=24,
        inhire_tenants=["venturus"],
    )
    defaults.update(kwargs)
    return Profile(**defaults)


def make_list_item(**kwargs) -> dict:
    defaults = dict(
        jobId="job-1",
        displayName="Desenvolvedor Java Pleno",
        status="published",
        workplaceType="Remote",
        location="BR",
    )
    defaults.update(kwargs)
    return defaults


def make_detail(**kwargs) -> dict:
    defaults = dict(
        jobId="job-1",
        displayName="Desenvolvedor Java Pleno",
        tenantName="Acme Corp",
        status="published",
        workplaceType="Remote",
        location="São Paulo, SP, BR",
        description="<p>Trabalhe com Java e Spring.</p>",
        publishedAt=_iso(datetime.now(UTC) - timedelta(hours=1)),
    )
    defaults.update(kwargs)
    return defaults


def _response(url: str, payload: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload, request=httpx.Request("GET", url))


def _mock_get(list_payload: dict, details: dict[str, dict]):
    def side_effect(url, headers, timeout):
        if url == _LIST_URL:
            return _response(url, list_payload)
        for job_id, detail in details.items():
            if url.endswith(f"/{job_id}"):
                return _response(url, detail)
        raise AssertionError(f"unexpected URL requested: {url}")

    return side_effect


# --- _strip_html ---


def test_strip_html_removes_simple_paragraph_tags():
    assert _strip_html("<p>Hello world</p>") == "Hello world"


def test_strip_html_decodes_named_entities():
    assert _strip_html("<p>caf&eacute;</p>") == "café"


def test_strip_html_converts_nbsp_entity_to_space():
    assert _strip_html("<p>a&nbsp;b</p>") == "a b"


def test_strip_html_decodes_amp_lt_gt_entities():
    assert _strip_html("<p>A &amp; B &lt;tag&gt;</p>") == "A & B <tag>"


def test_strip_html_strips_tags_with_attributes():
    assert _strip_html('<p class="foo">Texto</p>') == "Texto"


def test_strip_html_handles_unclosed_tag_without_crashing():
    assert _strip_html("<p>Texto sem fechar") == "Texto sem fechar"


def test_strip_html_empty_or_none_returns_empty_string():
    assert _strip_html("") == ""
    assert _strip_html(None) == ""


def test_strip_html_nested_list_items_are_not_glued_together():
    result = _strip_html("<ul><li>Item 1</li><li>Item 2</li></ul>")
    assert result == "Item 1\nItem 2"


def test_strip_html_block_elements_insert_separator_between_blocks():
    result = _strip_html("<h2>Requisitos</h2><p>Texto</p>")
    assert result == "Requisitos\nTexto"


def test_strip_html_inline_tags_do_not_add_extra_whitespace():
    result = _strip_html("<p>Isso é <strong>importante</strong> para nós.</p>")
    assert result == "Isso é importante para nós."


def test_strip_html_br_tag_does_not_glue_adjacent_text():
    assert _strip_html("Linha 1<br>Linha 2") == "Linha 1\nLinha 2"


def test_strip_html_stray_angle_bracket_in_text_is_preserved():
    assert _strip_html("Salário > R$5000") == "Salário > R$5000"


# --- collect_inhire_jobs ---


def test_collect_inhire_jobs_no_tenants_returns_empty_and_makes_no_http_call():
    profile = make_profile(inhire_tenants=[])
    with patch("src.collectors.inhire.httpx.get") as mock_get:
        jobs = collect_inhire_jobs(profile)
    assert jobs == []
    mock_get.assert_not_called()


def test_collect_inhire_jobs_calls_list_endpoint_with_tenant_header():
    profile = make_profile(inhire_tenants=["venturus"])
    list_payload = {"jobsPage": [make_list_item()]}
    details = {"job-1": make_detail()}
    with patch(
        "src.collectors.inhire.httpx.get", side_effect=_mock_get(list_payload, details)
    ) as mock_get:
        collect_inhire_jobs(profile)
    first_call = mock_get.call_args_list[0]
    assert first_call.args[0] == _LIST_URL
    assert first_call.kwargs["headers"] == {"X-Tenant": "venturus"}


def test_collect_inhire_jobs_continues_on_list_http_error(caplog):
    profile = make_profile(inhire_tenants=["broken", "venturus"])
    list_payload = {"jobsPage": [make_list_item()]}
    details = {"job-1": make_detail()}

    def side_effect(url, headers, timeout):
        if headers["X-Tenant"] == "broken":
            raise httpx.ConnectTimeout("boom")
        return _mock_get(list_payload, details)(url, headers, timeout)

    with (
        patch("src.collectors.inhire.httpx.get", side_effect=side_effect),
        caplog.at_level(logging.WARNING),
    ):
        jobs = collect_inhire_jobs(profile)

    assert "broken" in caplog.text
    assert len(jobs) == 1
    assert jobs[0].company == "Acme Corp"


def test_collect_inhire_jobs_multiple_tenants_are_all_queried():
    profile = make_profile(inhire_tenants=["venturus", "outra"])
    list_payload = {"jobsPage": [make_list_item()]}
    details = {"job-1": make_detail()}
    with patch(
        "src.collectors.inhire.httpx.get", side_effect=_mock_get(list_payload, details)
    ) as mock_get:
        collect_inhire_jobs(profile)
    tenants_called = {call.kwargs["headers"]["X-Tenant"] for call in mock_get.call_args_list}
    assert tenants_called == {"venturus", "outra"}


def test_collect_inhire_jobs_empty_jobs_page_returns_no_jobs_for_tenant():
    profile = make_profile()
    with patch(
        "src.collectors.inhire.httpx.get", side_effect=_mock_get({"jobsPage": []}, {})
    ):
        jobs = collect_inhire_jobs(profile)
    assert jobs == []


def test_collect_inhire_jobs_skips_detail_call_for_non_published_status():
    profile = make_profile()
    list_payload = {
        "jobsPage": [
            make_list_item(jobId="job-1", status="published"),
            make_list_item(jobId="job-2", status="closed"),
        ]
    }
    details = {"job-1": make_detail(jobId="job-1")}
    with patch(
        "src.collectors.inhire.httpx.get", side_effect=_mock_get(list_payload, details)
    ) as mock_get:
        jobs = collect_inhire_jobs(profile)
    assert len(jobs) == 1
    # 1 list call + 1 detail call (job-2 never fetched)
    assert mock_get.call_count == 2


def test_collect_inhire_jobs_treats_missing_status_as_not_published():
    profile = make_profile()
    item = make_list_item()
    del item["status"]
    with patch(
        "src.collectors.inhire.httpx.get", side_effect=_mock_get({"jobsPage": [item]}, {})
    ) as mock_get:
        jobs = collect_inhire_jobs(profile)
    assert jobs == []
    assert mock_get.call_count == 1  # only the list call


def test_collect_inhire_jobs_status_comparison_is_exact_match():
    profile = make_profile()
    item = make_list_item(status="Published")
    with patch(
        "src.collectors.inhire.httpx.get", side_effect=_mock_get({"jobsPage": [item]}, {})
    ):
        jobs = collect_inhire_jobs(profile)
    assert jobs == []


def test_collect_inhire_jobs_missing_job_id_is_skipped():
    profile = make_profile()
    item = make_list_item()
    del item["jobId"]
    with patch(
        "src.collectors.inhire.httpx.get", side_effect=_mock_get({"jobsPage": [item]}, {})
    ) as mock_get:
        jobs = collect_inhire_jobs(profile)
    assert jobs == []
    assert mock_get.call_count == 1  # only the list call


def test_collect_inhire_jobs_continues_on_detail_http_error(caplog):
    profile = make_profile()
    list_payload = {
        "jobsPage": [
            make_list_item(jobId="job-1"),
            make_list_item(jobId="job-2"),
        ]
    }
    details = {"job-2": make_detail(jobId="job-2")}

    def side_effect(url, headers, timeout):
        if url.endswith("/job-1"):
            raise httpx.ConnectTimeout("boom")
        return _mock_get(list_payload, details)(url, headers, timeout)

    with (
        patch("src.collectors.inhire.httpx.get", side_effect=side_effect),
        caplog.at_level(logging.WARNING),
    ):
        jobs = collect_inhire_jobs(profile)

    assert "job-1" in caplog.text
    assert len(jobs) == 1
    assert jobs[0].url.endswith("/job-2")


def test_collect_inhire_jobs_discards_job_older_than_cutoff():
    profile = make_profile(hours_old=24)
    old_detail = make_detail(publishedAt=_iso(datetime.now(UTC) - timedelta(hours=48)))
    with patch(
        "src.collectors.inhire.httpx.get",
        side_effect=_mock_get({"jobsPage": [make_list_item()]}, {"job-1": old_detail}),
    ):
        jobs = collect_inhire_jobs(profile)
    assert jobs == []


def test_collect_inhire_jobs_keeps_job_within_window():
    profile = make_profile(hours_old=24)
    recent_detail = make_detail(publishedAt=_iso(datetime.now(UTC) - timedelta(hours=1)))
    with patch(
        "src.collectors.inhire.httpx.get",
        side_effect=_mock_get({"jobsPage": [make_list_item()]}, {"job-1": recent_detail}),
    ):
        jobs = collect_inhire_jobs(profile)
    assert len(jobs) == 1


def test_collect_inhire_jobs_keeps_job_with_missing_published_at():
    profile = make_profile(hours_old=24)
    detail = make_detail()
    del detail["publishedAt"]
    with patch(
        "src.collectors.inhire.httpx.get",
        side_effect=_mock_get({"jobsPage": [make_list_item()]}, {"job-1": detail}),
    ):
        jobs = collect_inhire_jobs(profile)
    assert len(jobs) == 1
    assert jobs[0].date_posted is None


def test_collect_inhire_jobs_keeps_job_with_malformed_published_at():
    profile = make_profile(hours_old=24)
    detail = make_detail(publishedAt="not-a-date")
    with patch(
        "src.collectors.inhire.httpx.get",
        side_effect=_mock_get({"jobsPage": [make_list_item()]}, {"job-1": detail}),
    ):
        jobs = collect_inhire_jobs(profile)
    assert len(jobs) == 1
    assert jobs[0].date_posted is None


def test_collect_inhire_jobs_maps_all_fields():
    profile = make_profile()
    detail = make_detail(
        jobId="job-1",
        displayName="Desenvolvedora Fullstack",
        tenantName="Venturus",
        workplaceType="Remote",
        location="Campinas, SP, BR",
        description="<p>Java e React.</p>",
    )
    with patch(
        "src.collectors.inhire.httpx.get",
        side_effect=_mock_get({"jobsPage": [make_list_item()]}, {"job-1": detail}),
    ):
        jobs = collect_inhire_jobs(profile)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Desenvolvedora Fullstack"
    assert job.company == "Venturus"
    assert job.url == "https://venturus.inhire.app/vagas/job-1"
    assert job.source == "inhire"
    assert job.description == "Java e React."
    assert job.location == "Campinas, SP, BR"
    assert job.is_remote is True
    assert job.job_level is None
    assert job.salary_min is None
    assert job.salary_max is None


def test_collect_inhire_jobs_workplace_type_hybrid_maps_to_is_remote_false():
    profile = make_profile()
    detail = make_detail(workplaceType="Hybrid")
    with patch(
        "src.collectors.inhire.httpx.get",
        side_effect=_mock_get({"jobsPage": [make_list_item()]}, {"job-1": detail}),
    ):
        jobs = collect_inhire_jobs(profile)
    assert jobs[0].is_remote is False


def test_collect_inhire_jobs_unknown_workplace_type_maps_to_is_remote_false():
    profile = make_profile()
    detail = make_detail(workplaceType="Onsite")
    with patch(
        "src.collectors.inhire.httpx.get",
        side_effect=_mock_get({"jobsPage": [make_list_item()]}, {"job-1": detail}),
    ):
        jobs = collect_inhire_jobs(profile)
    assert jobs[0].is_remote is False


def test_collect_inhire_jobs_dedups_same_job_id_within_tenant():
    profile = make_profile()
    list_payload = {"jobsPage": [make_list_item(), make_list_item()]}
    details = {"job-1": make_detail()}
    with patch(
        "src.collectors.inhire.httpx.get", side_effect=_mock_get(list_payload, details)
    ) as mock_get:
        jobs = collect_inhire_jobs(profile)
    assert len(jobs) == 1
    # 1 list call + 1 detail call (second occurrence deduped before fetching)
    assert mock_get.call_count == 2
