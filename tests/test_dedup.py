from src.dedup import filter_new_jobs, normalize_url
from src.models import Job


def make_job(url: str) -> Job:
    return Job(title="Dev", company="Co", url=url, source="indeed")


def test_normalize_linkedin_strips_tracking():
    url = "https://www.linkedin.com/jobs/view/4431846556?refId=abc&trackingId=xyz"
    assert normalize_url(url) == "https://www.linkedin.com/jobs/view/4431846556"


def test_normalize_indeed_keeps_jk():
    url = "https://br.indeed.com/viewjob?jk=abc123&from=hp&vjk=xyz"
    assert normalize_url(url) == "https://br.indeed.com/viewjob?jk=abc123"


def test_normalize_url_no_params_unchanged():
    url = "https://www.linkedin.com/jobs/view/123456789"
    assert normalize_url(url) == url


def test_normalize_strips_fragment():
    url = "https://www.linkedin.com/jobs/view/123#section"
    assert normalize_url(url) == "https://www.linkedin.com/jobs/view/123"


def test_filter_removes_existing():
    existing = {"https://www.linkedin.com/jobs/view/123"}
    assert filter_new_jobs([make_job("https://www.linkedin.com/jobs/view/123")], existing) == []


def test_filter_keeps_new():
    existing = {"https://www.linkedin.com/jobs/view/123"}
    result = filter_new_jobs([make_job("https://www.linkedin.com/jobs/view/456")], existing)
    assert len(result) == 1


def test_filter_normalizes_before_comparison():
    existing = {"https://www.linkedin.com/jobs/view/123"}
    jobs = [make_job("https://www.linkedin.com/jobs/view/123?refId=tracking")]
    assert filter_new_jobs(jobs, existing) == []


def test_filter_empty_existing():
    jobs = [make_job("https://example.com/1"), make_job("https://example.com/2")]
    assert len(filter_new_jobs(jobs, set())) == 2


def test_filter_empty_jobs():
    assert filter_new_jobs([], {"https://example.com/1"}) == []
