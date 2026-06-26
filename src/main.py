import os

from dotenv import load_dotenv
from notion_client import Client

from .collector import collect_jobs
from .config import load_profile
from .dedup import fetch_existing_urls, filter_new_jobs
from .enricher import enrich_job
from .llm import create_llm_client
from .scorer import score_jobs


def main() -> None:
    load_dotenv()
    client = Client(auth=os.environ["NOTION_TOKEN"])
    profile = load_profile(client, os.environ["NOTION_PROFILE_DATABASE_ID"])

    print(f"Buscando: '{profile.keywords[0]}' em {profile.location} (últimas {profile.hours_old}h)")
    jobs = collect_jobs(profile)
    print(f"Coletadas: {len(jobs)} vagas")

    existing_urls = fetch_existing_urls(client, os.environ["NOTION_VAGAS_DATABASE_ID"])
    new_jobs = filter_new_jobs(jobs, existing_urls)
    print(f"Novas: {len(new_jobs)} (descartadas {len(jobs) - len(new_jobs)} duplicatas)")

    scored = score_jobs(new_jobs, profile)
    print(f"Aprovadas: {len(scored)} acima do threshold {profile.score_threshold}\n")

    llm = create_llm_client()
    enriched = []
    for s in scored:
        stack = s.required_hits + [f"+{b}" for b in s.bonus_hits]
        print(f"  [{s.score:4.1f}] {s.job.title} @ {s.job.company} ({s.job.source})")
        print(f"         {', '.join(stack)}")
        try:
            enriched.append(enrich_job(s, profile, llm))
            print("         [OK] enriquecido")
        except Exception as e:
            print(f"         [ERR] enriquecimento falhou: {e}")

    print(f"\nEnriquecidas: {len(enriched)}/{len(scored)}")


if __name__ == "__main__":
    main()
