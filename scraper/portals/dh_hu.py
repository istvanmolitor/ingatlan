from __future__ import annotations

import base64
import json
import re
from urllib.parse import urljoin, urlparse

import requests

from ..downloader import USER_AGENT
from ..models import PAGE_TYPE_LISTING, PAGE_TYPE_OTHER, PAGE_TYPE_PROPERTY, Property, normalize_condition, normalize_property_type, parse_area_sqm, parse_rooms
from .base import Portal

_API_BASE = "https://newdhapi03.dh.hu/api"

# A dh.hu "address" mezője "<irányítószám> <város>[ <kerület>][ , <extra>]"
# formátumú, pl. "1098 Budapest 9. kerület , Pöttyös utcai metró megállónál
# közvetlenül!" vagy "2000 Szentendre ". A várost az irányítószám és az első
# vessző közötti rész adja.
_ADDRESS_CITY_RE = re.compile(r"^\s*\d{4}\s+(.*?)\s*(?:,.*)?$")


def _city_from_address(address: str) -> str:
    match = _ADDRESS_CITY_RE.match(address)
    return match.group(1) if match else ""


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

    def classify_page(self, html: str, url: str) -> str:
        # Az útvonal ugyanúgy dönt, mint a `fetch_html`: a "/ingatlan/" alatti
        # linkek hirdetés-részletezők, minden más lista/kereső oldal.
        if urlparse(url).path.startswith("/ingatlan/"):
            return PAGE_TYPE_PROPERTY

        try:
            data = json.loads(html)
        except json.JSONDecodeError:
            return PAGE_TYPE_OTHER
        if ((data.get("result") or {}).get("items")) is not None:
            return PAGE_TYPE_LISTING
        return PAGE_TYPE_OTHER

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

        general = ((result.get("details") or {}).get("general")) or {}
        address = str(result.get("address", ""))

        return Property(
            url=url,
            portal=self.name,
            property_id=str(result.get("referenceNumber", "")),
            property_type=normalize_property_type(result.get("propertyTypeName")),
            condition=normalize_condition(general.get("buildingInsideCondition")),
            title=address,
            price=str(result.get("priceNumeric", "")),
            currency=str(result.get("priceOriginalCurrency", "")),
            area_sqm=parse_area_sqm(result.get("area")),
            rooms=parse_rooms(result.get("rooms")),
            location=address,
            city=_city_from_address(address),
        )
