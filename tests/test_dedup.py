from src.dedup import filter_new_jobs, normalize_company_title, normalize_url
from src.models import Job


def make_job(url: str, title: str = "Dev", company: str = "Co") -> Job:
    return Job(title=title, company=company, url=url, source="indeed")


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
    jobs = [
        make_job("https://example.com/1", title="Dev A"),
        make_job("https://example.com/2", title="Dev B"),
    ]
    assert len(filter_new_jobs(jobs, set())) == 2


def test_filter_empty_jobs():
    assert filter_new_jobs([], {"https://example.com/1"}) == []


def test_normalize_company_title_lowercases_and_strips_punctuation():
    key = normalize_company_title("Compass UOL", "Node.js Full-Stack Developer")
    assert key == "compass uol|node js full stack developer"


def test_normalize_company_title_collapses_whitespace():
    key = normalize_company_title("  Acme   Corp ", "Dev  Pleno")
    assert key == "acme corp|dev pleno"


def test_normalize_company_title_empty_company_returns_empty():
    assert normalize_company_title("", "Dev") == ""
    assert normalize_company_title("Acme", "") == ""


def test_filter_removes_same_company_title_with_different_url():
    existing_keys = {normalize_company_title("Compass UOL", "Node.js Full-Stack Developer")}
    jobs = [
        make_job(
            "https://br.indeed.com/viewjob?jk=novo",
            title="Node.js Full-Stack Developer",
            company="Compass UOL",
        )
    ]
    assert filter_new_jobs(jobs, set(), existing_keys) == []


def test_filter_keeps_same_title_different_company():
    existing_keys = {normalize_company_title("Compass UOL", "Node.js Developer")}
    jobs = [make_job("https://example.com/1", title="Node.js Developer", company="Outra Empresa")]
    assert len(filter_new_jobs(jobs, set(), existing_keys)) == 1


def test_filter_dedupes_within_batch_by_url():
    jobs = [
        make_job("https://example.com/1?refId=a", title="Dev A", company="X"),
        make_job("https://example.com/1?refId=b", title="Dev B", company="Y"),
    ]
    assert len(filter_new_jobs(jobs, set())) == 1


def test_filter_dedupes_within_batch_by_company_title():
    jobs = [
        make_job("https://gupy.io/vaga/1", title="Fullstack Pleno", company="Compass UOL"),
        make_job(
            "https://br.indeed.com/viewjob?jk=x", title="Fullstack Pleno", company="Compass UOL"
        ),
    ]
    result = filter_new_jobs(jobs, set())
    assert len(result) == 1
    assert result[0].url == "https://gupy.io/vaga/1"


def test_filter_missing_company_does_not_match_other_missing_company():
    jobs = [
        make_job("https://example.com/1", title="Dev", company=""),
        make_job("https://example.com/2", title="Dev", company=""),
    ]
    assert len(filter_new_jobs(jobs, set())) == 2
