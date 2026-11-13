from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import requests

from ..downloader import USER_AGENT
from ..models import Property
from .base import Portal

_SEARCH_PATH = "/api/rels/v1/adverts/search"


class ZengaHuPortal(Portal):
    # Az ingatlan.net 2026-ban zenga.hu néven futott tovább (a régi domain
    # ide irányít át).
    name = "zenga.hu"
    domain = "zenga.hu"
    seed_urls = [
        f"https://www.zenga.hu{_SEARCH_PATH}?textSearch=elado+lakas",
        f"https://www.zenga.hu{_SEARCH_PATH}?textSearch=elado+haz",
    ]

    def fetch_html(self, url: str) -> str:
        # A zenga.hu Angular SPA, a listázó oldalak kliensoldalon épülnek fel,
        # ezért a keresést a saját JSON API-ján (POST) hívjuk; a hirdetés-
        # részletezőket ("/api/rels/v1/adverts/<id>") sima GET-tel.
        parsed = urlparse(url)
        headers = {"User-Agent": USER_AGENT, "Referer": "https://www.zenga.hu/"}
        if parsed.path == _SEARCH_PATH:
            text_search = parse_qs(parsed.query).get("textSearch", [""])[0]
            payload = {
                "pageSize": 100,
                "page": 1,
                "agency": None,
                "textSearch": text_search,
                "searchObject": {},
                "ppcAdvertId": None,
            }
            response = requests.post(
                f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
                json=payload,
                headers=headers,
                timeout=15,
            )
        else:
            response = requests.get(url, headers=headers, timeout=15)
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
            advert_id = item.get("advertId")
            if not advert_id:
                continue
            links.add(self._normalize(f"https://www.zenga.hu/api/rels/v1/adverts/{advert_id}"))
        return links

    def parse_property(self, html: str, url: str) -> Property | None:
        try:
            data = json.loads(html)
        except json.JSONDecodeError:
            return None

        if not data.get("advertId"):
            return None

        if str(data.get("saleType", "")).upper() != "SALE":
            return None

        return Property(
            url=url,
            portal=self.name,
            property_id=str(data.get("advertId", "")),
            property_type=str(data.get("propertyCategory", "")),
            title=str(data.get("advertTitle", "")),
            price=str(data.get("price", "")),
            currency=str(data.get("currency", "")),
            area_sqm=str(data.get("floorAreaSize", "")),
            rooms=str(data.get("numberOfRooms", "")),
            location=str(data.get("address", "")),
        )
