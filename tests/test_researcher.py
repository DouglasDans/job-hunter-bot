from unittest.mock import MagicMock, patch

from src.researcher import research_company


def _mock_ddgs(results: list[dict]) -> MagicMock:
    instance = MagicMock()
    instance.__enter__ = MagicMock(return_value=instance)
    instance.__exit__ = MagicMock(return_value=False)
    instance.text.return_value = results
    return instance


def test_research_company_returns_string():
    mock = _mock_ddgs([{"title": "Acme Reviews", "body": "Great company culture."}])
    with patch("src.researcher.DDGS", return_value=mock):
        result = research_company("Acme Corp")
    assert isinstance(result, str)
    assert "Great company culture" in result


def test_research_company_empty_when_no_results():
    mock = _mock_ddgs([])
    with patch("src.researcher.DDGS", return_value=mock):
        result = research_company("Unknown Corp")
    assert result == ""


def test_research_company_handles_exception_gracefully():
    with patch("src.researcher.DDGS", side_effect=Exception("network error")):
        result = research_company("Acme Corp")
    assert result == ""


def test_research_company_includes_title_and_body():
    results = [{"title": "Glassdoor Acme", "body": "Employees love the culture."}]
    mock = _mock_ddgs(results)
    with patch("src.researcher.DDGS", return_value=mock):
        result = research_company("Acme Corp")
    assert "Glassdoor Acme" in result
    assert "Employees love the culture" in result


def test_research_company_limits_total_snippets():
    many_results = [{"title": f"Result {i}", "body": f"Content {i}"} for i in range(10)]
    mock = _mock_ddgs(many_results)
    with patch("src.researcher.DDGS", return_value=mock):
        result = research_company("Big Corp")
    snippets = [s for s in result.split("\n\n") if s]
    assert len(snippets) <= 6
