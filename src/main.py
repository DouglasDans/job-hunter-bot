import os

from dotenv import load_dotenv
from notion_client import Client

from .collector import collect_jobs
from .config import load_profile
from .scorer import score_jobs


def main() -> None:
    load_dotenv()
    client = Client(auth=os.environ["NOTION_TOKEN"])
    profile = load_profile(client, os.environ["NOTION_PROFILE_DATABASE_ID"])

    print(f"Buscando: '{profile.keywords[0]}' em {profile.location} (últimas {profile.hours_old}h)")
    jobs = collect_jobs(profile)
    print(f"Coletadas: {len(jobs)} vagas")

    scored = score_jobs(jobs, profile)
    print(f"Aprovadas: {len(scored)} acima do threshold {profile.score_threshold}\n")

    for s in scored:
        stack = s.required_hits + [f"+{b}" for b in s.bonus_hits]
        print(f"  [{s.score:4.1f}] {s.job.title} @ {s.job.company} ({s.job.source})")
        print(f"         {', '.join(stack)}")


if __name__ == "__main__":
    main()
