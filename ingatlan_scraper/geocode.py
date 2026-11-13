from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path

import requests

NOMINATIM_URL = os.environ.get("NOMINATIM_URL", "http://localhost:8080/search")

GEOCODE_CACHE_FIELDNAMES = ["address", "lat", "lon"]


def geocode(address: str, base_url: str = NOMINATIM_URL, timeout: float = 10.0) -> tuple[float, float] | None:
    """Egy cím GPS koordinátává alakítása egy (lokálisan futó) Nominatim API-n keresztül."""
    response = requests.get(
        base_url,
        params={"q": address, "format": "json", "limit": 1, "countrycodes": "hu"},
        headers={"User-Agent": "ingatlan-scraper/1.0"},
        timeout=timeout,
    )
    response.raise_for_status()
    results = response.json()
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])


@dataclass
class GeocodeCache:
    """Cím -> (lat, lon) gyorsítótár egy CSV fájlban, hogy ugyanazt a címet
    ne kelljen kétszer lekérdezni. Sikertelen lekérdezés is bekerül ("", "")
    értékkel, így azt sem próbáljuk újra feleslegesen."""

    csv_path: Path

    def load(self) -> dict[str, tuple[str, str]]:
        if not self.csv_path.exists():
            return {}
        with self.csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return {row["address"]: (row["lat"], row["lon"]) for row in reader}

    def save(self, cache: dict[str, tuple[str, str]]) -> None:
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.csv_path.with_suffix(".tmp")
        with tmp_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=GEOCODE_CACHE_FIELDNAMES)
            writer.writeheader()
            for address in sorted(cache):
                lat, lon = cache[address]
                writer.writerow({"address": address, "lat": lat, "lon": lon})
        tmp_path.replace(self.csv_path)
