from __future__ import annotations

import json
from urllib.parse import urljoin, urlparse

from ..models import PAGE_TYPE_LISTING, PAGE_TYPE_OTHER, PAGE_TYPE_PROPERTY, Property, normalize_condition, normalize_property_type, parse_area_sqm, parse_rooms
from .base import Portal

_ADVERT_PATH_PREFIX = "/api/property/"
_SEARCH_PATH_PREFIX = "/api/property-search"


class IngatlanbazarHuPortal(Portal):
    name = "ingatlanbazar.hu"
    domain = "ingatlanbazar.hu"
    # A listázó oldal kliensoldali (Angular) renderelésű, a tényleges
    # hirdetéseket a saját JSON API-ja szolgáltatja ki, amit sima GET
    # kéréssel is el lehet érni.
    seed_urls = [
        "https://ingatlanbazar.hu/api/property-search?limit=100",
    ]

    def extract_property_links(self, html: str, base_url: str) -> set[str]:
        try:
            data = json.loads(html)
        except json.JSONDecodeError:
            return set()

        links = set()
        for hit in data.get("hits") or []:
            property_id = hit.get("propertyId")
            if not property_id:
                continue
            links.add(self._normalize(urljoin(base_url, f"/api/property/{property_id}")))
        return links

    def classify_page(self, html: str, url: str) -> str:
        path = urlparse(url).path
        if path.startswith(_ADVERT_PATH_PREFIX):
            return PAGE_TYPE_PROPERTY
        if path.startswith(_SEARCH_PATH_PREFIX):
            return PAGE_TYPE_LISTING
        return PAGE_TYPE_OTHER

    def parse_property(self, html: str, url: str) -> Property | None:
        try:
            data = json.loads(html)
        except json.JSONDecodeError:
            return None

        prop = data.get("property")
        if not prop:
            return None

        fields = prop.get("serializedFields") or []

        def field_value(group_name: str) -> str:
            return next((str(f.get("fieldName", "")) for f in fields if f.get("groupName") == group_name), "")

        if "kiad" in field_value("Hirdetés típusa").lower():
            return None

        location = ", ".join(
            part
            for part in (
                str(prop.get("settlement", "")),
                str(prop.get("district", "")),
                str(prop.get("street", "")),
            )
            if part
        )

        return Property(
            url=url,
            portal=self.name,
            property_id=str(prop.get("propertyId", "")),
            property_type=normalize_property_type(field_value("Ingatlan típusa")),
            condition=normalize_condition(field_value("Ingatlan állapot")),
            title=str(prop.get("userTitle", "")),
            price=str(prop.get("priceHUF", "")),
            currency="HUF",
            area_sqm=parse_area_sqm(prop.get("area")),
            rooms=parse_rooms(prop.get("rooms")),
            location=location,
            city=str(prop.get("settlement", "")),
        )
