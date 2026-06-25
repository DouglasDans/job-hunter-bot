import os

from dotenv import load_dotenv
from notion_client import Client

from .config import load_profile


def main() -> None:
    load_dotenv()
    client = Client(auth=os.environ["NOTION_TOKEN"])
    profile = load_profile(client, os.environ["NOTION_PROFILE_DATABASE_ID"])
    print(profile.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
