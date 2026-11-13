from __future__ import annotations

import json
from urllib.parse import urljoin

from ..models import Property
from .base import Portal


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
            property_type=field_value("Ingatlan típusa"),
            title=str(prop.get("userTitle", "")),
            price=str(prop.get("priceHUF", "")),
            currency="HUF",
            area_sqm=str(prop.get("area", "")),
            rooms=str(prop.get("rooms", "")),
            location=location,
        )
