from notion_client import Client

from .models import Profile


def _text(props: dict, key: str) -> str:
    items = props.get(key, {}).get("rich_text", [])
    return items[0]["plain_text"] if items else ""


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _multi_select(props: dict, key: str) -> list[str]:
    return [item["name"] for item in props.get(key, {}).get("multi_select", [])]


def _select(props: dict, key: str) -> str:
    sel = props.get(key, {}).get("select")
    return sel["name"] if sel else ""


def _number(props: dict, key: str, default: float) -> float:
    val = props.get(key, {}).get("number")
    return val if val is not None else default


def parse_profile(page: dict) -> Profile:
    props = page["properties"]
    return Profile(
        keywords=_split_csv(_text(props, "keywords")),
        location=_text(props, "location"),
        required_stack=_multi_select(props, "required_stack"),
        bonus_stack=_multi_select(props, "bonus_stack"),
        seniority=_select(props, "seniority"),
        modality=_select(props, "modality"),
        dealbreakers=_split_csv(_text(props, "dealbreakers")),
        score_threshold=_number(props, "score_threshold", 6.0),
        hours_old=int(_number(props, "hours_old", 24)),
    )


def load_profile(client: Client, database_id: str) -> Profile:
    db = client.databases.retrieve(database_id=database_id)
    data_source_id = db["data_sources"][0]["id"]
    response = client.data_sources.query(data_source_id)
    results = response.get("results", [])
    if not results:
        raise ValueError(f"No profile found in database {database_id}")
    return parse_profile(results[0])
