from ddgs import DDGS


def research_company(company_name: str) -> str:
    queries = [
        f'"{company_name}" empresa cultura trabalho avaliação benefícios',
        f'"{company_name}" company reviews glassdoor employees culture',
    ]
    snippets: list[str] = []
    try:
        with DDGS() as ddgs:
            for query in queries:
                for r in ddgs.text(query, max_results=3):
                    snippets.append(f"[{r['title']}] {r['body']}")
    except Exception as e:
        print(f"[WARN] Company research failed for '{company_name}': {e}")
        return ""
    return "\n\n".join(snippets[:6])
