from __future__ import annotations

import base64
import json
from urllib.parse import urljoin, urlparse

import requests

from ..downloader import USER_AGENT
from ..models import Property
from .base import Portal

_API_BASE = "https://newdhapi03.dh.hu/api"


class DhHuPortal(Portal):
    # A duna-house.hu domain nem létezik, a tényleges márkásított domain a dh.hu.
    name = "dh.hu"
    domain = "dh.hu"
    seed_urls = [
        "https://dh.hu/elado-ingatlan/lakas-haz",
    ]

    def fetch_html(self, url: str) -> str:
        # A dh.hu Angular SPA, a HTML-je kliensoldalon épül fel, ezért a sima
        # GET helyett a saját JSON API-ját hívjuk: a hirdetés-részletezőket
        # (/ingatlan/...) GET-tel, a listázó oldalakat (minden más útvonal)
        # POST-tal.
        parsed = urlparse(url)
        headers = {"User-Agent": USER_AGENT, "Referer": "https://dh.hu/"}
        if parsed.path.startswith("/ingatlan/"):
            encoded_path = base64.b64encode(parsed.path.encode()).decode()
            response = requests.get(
                f"{_API_BASE}/loadWebsiteOnlyData",
                params={"url": encoded_path},
                headers=headers,
                timeout=15,
            )
        else:
            response = requests.post(
                f"{_API_BASE}/getProperties",
                params={"page": 1},
                data={"url": parsed.path},
                headers=headers,
                timeout=15,
            )
        response.raise_for_status()
        return response.text

    def extract_property_links(self, html: str, base_url: str) -> set[str]:
        try:
            data = json.loads(html)
        except json.JSONDecodeError:
            return set()

        items = ((data.get("result") or {}).get("items")) or []
        links = set()
        for item in items:
            alias = item.get("alias")
            if not alias:
                continue
            links.add(self._normalize(urljoin("https://dh.hu/", alias)))
        return links

    def parse_property(self, html: str, url: str) -> Property | None:
        try:
            data = json.loads(html)
        except json.JSONDecodeError:
            return None

        result = data.get("result")
        if not result or not result.get("referenceNumber"):
            return None  # listázó oldal JSON-ja, nem egy konkrét hirdetés

        if "kiad" in str(result.get("contractTypeName", "")).lower():
            return None

        return Property(
            url=url,
            portal=self.name,
            property_id=str(result.get("referenceNumber", "")),
            property_type=str(result.get("propertyTypeName", "")),
            title=str(result.get("address", "")),
            price=str(result.get("priceNumeric", "")),
            currency=str(result.get("priceOriginalCurrency", "")),
            area_sqm=str(result.get("area", "")),
            rooms=str(result.get("rooms", "")),
            location=str(result.get("address", "")),
        )
