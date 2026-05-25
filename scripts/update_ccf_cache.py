#!/usr/bin/env python3
"""Update data/conference_cache.json from ccfddl/ccf-deadlines."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import requests
import yaml

ZIP_URL = "https://api.github.com/repos/ccfddl/ccf-deadlines/zipball/main"
OUTPUT = Path("data") / "conference_cache.json"


def is_conference_file(path: str) -> bool:
    parts = path.split("/")
    return len(parts) >= 4 and parts[-3] == "conference" and parts[-1].endswith(".yml")


def split_place(place: str) -> tuple[str, str]:
    cleaned = " ".join((place or "").split())
    if not cleaned:
        return "-", "-"
    parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[-1], ", ".join(parts[:-1])


def normalize_conference(conf: dict, categories: dict[str, dict[str, str]]) -> list[dict]:
    sub = conf.get("sub", "")
    category = categories.get(sub, {"name": sub, "name_en": sub})
    rank = conf.get("rank", {})
    rows: list[dict] = []

    for conf_year in conf.get("confs", []):
        country, region = split_place(conf_year.get("place", ""))
        timelines = [
            {
                "deadline": item.get("deadline", ""),
                "abstract_deadline": item.get("abstract_deadline"),
                "comment": item.get("comment", ""),
            }
            for item in conf_year.get("timeline", [])
        ]

        rows.append(
            {
                "title": conf.get("title", ""),
                "description": conf.get("description", ""),
                "sub": sub,
                "sub_name": category["name"],
                "sub_name_en": category["name_en"],
                "ccf_rank": rank.get("ccf", "N"),
                "core_rank": rank.get("core", "N"),
                "thcpl_rank": rank.get("thcpl", "N"),
                "dblp": conf.get("dblp", ""),
                "year": conf_year.get("year"),
                "id": conf_year.get("id", ""),
                "link": conf_year.get("link", ""),
                "date": conf_year.get("date", ""),
                "place": conf_year.get("place", ""),
                "country": country,
                "region": region,
                "timezone": conf_year.get("timezone", "UTC"),
                "timeline": timelines,
            }
        )
    return rows


def build_cache_payload(zip_bytes: bytes) -> dict:
    categories: dict[str, dict[str, str]] = {}
    records: list[dict] = []

    with ZipFile(BytesIO(zip_bytes)) as archive:
        names = archive.namelist()

        for name in names:
            if name.endswith("conference/types.yml"):
                raw_types = yaml.safe_load(archive.read(name).decode("utf-8"))
                for item in raw_types or []:
                    categories[item["sub"]] = {
                        "name": item.get("name", item["sub"]),
                        "name_en": item.get("name_en", item["sub"]),
                    }

        for name in names:
            if not is_conference_file(name):
                continue
            raw_items = yaml.safe_load(archive.read(name).decode("utf-8"))
            for conf in raw_items or []:
                records.extend(normalize_conference(conf, categories))

    records.sort(key=lambda item: (item.get("year", 0), item.get("title", ""), item.get("id", "")))
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "https://github.com/ccfddl/ccf-deadlines",
        "categories": categories,
        "records": records,
    }


def main() -> None:
    response = requests.get(ZIP_URL, timeout=90, headers={"User-Agent": "shihao-ccfddl-site-updater"})
    response.raise_for_status()

    payload = build_cache_payload(response.content)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Updated {OUTPUT} with {len(payload['records'])} records.")


if __name__ == "__main__":
    main()
