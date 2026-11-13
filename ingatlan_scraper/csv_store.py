from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path

from .models import PROPERTY_FIELDNAMES, Property

FIELDNAMES = ["url", "portal", "status", "page_type", "discovered_at", "downloaded_at", "file_path"]


@dataclass
class LinkRecord:
    url: str
    portal: str
    status: str = "pending"  # "pending" | "downloaded" | "error"
    page_type: str = ""  # "" (ismeretlen) | "listing" | "property" | "other"
    discovered_at: str = ""
    downloaded_at: str = ""
    file_path: str = ""


class LinkStore:
    def __init__(self, csv_path: Path) -> None:
        self.csv_path = csv_path

    def load(self) -> dict[str, LinkRecord]:
        if not self.csv_path.exists():
            return {}
        with self.csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return {row["url"]: LinkRecord(**row) for row in reader}

    def save(self, records: dict[str, LinkRecord]) -> None:
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.csv_path.with_suffix(".tmp")
        with tmp_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            for url in sorted(records):
                writer.writerow(asdict(records[url]))
        tmp_path.replace(self.csv_path)

    @staticmethod
    def add_new(
        records: dict[str, LinkRecord],
        url: str,
        portal: str,
        discovered_at: str,
        page_type: str = "",
    ) -> bool:
        if url in records:
            return False
        records[url] = LinkRecord(url=url, portal=portal, discovered_at=discovered_at, page_type=page_type)
        return True


class PropertyStore:
    def __init__(self, csv_path: Path) -> None:
        self.csv_path = csv_path

    def load(self) -> dict[str, Property]:
        if not self.csv_path.exists():
            return {}
        with self.csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return {row["url"]: Property(**row) for row in reader}

    def save(self, properties: dict[str, Property]) -> None:
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.csv_path.with_suffix(".tmp")
        with tmp_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=PROPERTY_FIELDNAMES)
            writer.writeheader()
            for url in sorted(properties):
                writer.writerow(asdict(properties[url]))
        tmp_path.replace(self.csv_path)
