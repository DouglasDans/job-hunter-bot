"""
E2E test: carrega perfil real do Notion, analisa uma vaga fake com LLM e sobe no Notion.
Uso: uv run python scripts/e2e_llm.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date

from dotenv import load_dotenv
from notion_client import Client

from src.config import load_profile
from src.enricher import enrich_job
from src.llm import create_llm_client
from src.models import Job, ScoredJob
from src.notifier import push_job
from src.researcher import research_company

FAKE_JOB = Job(
    title="Senior Frontend Engineer",
    company="Nubank",
    url="https://nubank.com.br/careers/fake-e2e-test",
    source="indeed",
    location="Remote, Brazil",
    is_remote=True,
    job_level="Senior",
    date_posted=date.today(),
    description="""
Nubank is looking for a Senior Frontend Engineer to join our Growth team.

About the role:
- Build and maintain React applications used by millions of customers
- Collaborate with design, product, and backend teams
- Lead technical decisions on the frontend stack
- Mentor junior developers

Requirements:
- 5+ years of experience with React and TypeScript
- Strong knowledge of Node.js and REST APIs
- Experience with PostgreSQL or similar databases
- Familiar with Docker and CI/CD pipelines
- Experience with AWS (S3, Lambda, CloudFront)
- English proficiency (written and spoken)

Nice to have:
- GraphQL experience
- Experience with micro-frontends
- Knowledge of performance optimization techniques

What we offer:
- 100% remote work
- Competitive salary in USD
- Health insurance for you and your family
- Stock options
- Annual learning budget of R$ 5.000
- Flexible working hours
- Flat hierarchy and autonomy culture

We are a mission-driven company focused on fighting complexity and bureaucracy.
Our engineering culture values simplicity, ownership, and continuous learning.
""".strip(),
)

FAKE_SCORED = ScoredJob(
    job=FAKE_JOB,
    score=9.0,
    required_hits=["React", "TypeScript", "Node.js"],
    bonus_hits=["PostgreSQL", "Docker", "AWS"],
)


def main() -> None:
    load_dotenv()
    notion = Client(auth=os.environ["NOTION_TOKEN"])
    vagas_db_id = os.environ["NOTION_VAGAS_DATABASE_ID"]

    print("Carregando perfil do Notion...")
    profile = load_profile(notion, os.environ["NOTION_PROFILE_DATABASE_ID"])
    print(f"Perfil: {profile.seniority} | {profile.modality} | about_me={len(profile.about_me)} chars\n")

    print(f"Pesquisando empresa: {FAKE_JOB.company}...")
    company_context = research_company(FAKE_JOB.company)
    print(f"Contexto encontrado: {len(company_context)} chars\n")

    print("Enriquecendo vaga com LLM...")
    llm = create_llm_client()
    enriched = enrich_job(FAKE_SCORED, profile, llm, company_context=company_context)
    print(f"match_score={enriched.match_score}")
    print(f"body_markdown={len(enriched.body_markdown)} chars\n")

    print("Subindo no Notion...")
    push_job(notion, vagas_db_id, enriched)
    print("Pronto! Vaga salva no Notion.")


if __name__ == "__main__":
    main()
