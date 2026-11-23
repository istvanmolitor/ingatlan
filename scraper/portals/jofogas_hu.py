from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import parse_qs, urljoin

from ..html_links import extract_hrefs
from ..models import PAGE_TYPE_LISTING, PAGE_TYPE_OTHER, PAGE_TYPE_PROPERTY, Property, normalize_condition, normalize_property_type, parse_area_sqm, parse_rooms
from .base import Portal

# hirdetés URL-ek formátuma: ingatlan.jofogas.hu/<megye>/<cim>_<szamazonosito>.htm
_PROPERTY_LINK_RE = re.compile(r"ingatlan\.jofogas\.hu/[a-z_]+/[^/\"?]+_\d+\.htm", re.IGNORECASE)

# A hirdetés-részletező oldalak egy "page-jsonld" script-tagben hordozzák a
# hirdetés adatait schema.org Product/BreadcrumbList formátumban.
_JSONLD_RE = re.compile(r'<script id="page-jsonld" type="application/ld\+json">(.*?)</script>', re.S)

# A "customtarget" meta tag "debug" attribútuma tartalmazza a hirdetés
# tranzakciótípusát (type=s: eladás, type=u: bérlet/kiadás).
_CUSTOMTARGET_RE = re.compile(r'name="customtarget" debug="([^"]*)"')


class JofogasHuPortal(Portal):
    name = "jofogas.hu"
    domain = "jofogas.hu"
    seed_urls = [
        "https://ingatlan.jofogas.hu/magyarorszag/ingatlan",
    ]

    def extract_property_links(self, html: str, base_url: str) -> set[str]:
        links = set()
        for href in extract_hrefs(html):
            absolute = urljoin(base_url, href)
            if self.belongs_to(absolute) and _PROPERTY_LINK_RE.search(absolute):
                links.add(self._normalize(absolute))
        return links

    def classify_page(self, html: str, url: str) -> str:
        if self.belongs_to(url) and _PROPERTY_LINK_RE.search(url):
            return PAGE_TYPE_PROPERTY
        if self.extract_property_links(html, url):
            return PAGE_TYPE_LISTING
        return PAGE_TYPE_OTHER

    def parse_property(self, html: str, url: str) -> Property | None:
        target_match = _CUSTOMTARGET_RE.search(html)
        if target_match:
            params = parse_qs(unescape(target_match.group(1)))
            if params.get("type", [""])[0] == "u":
                return None  # bérlet/kiadás hirdetés

        jsonld_match = _JSONLD_RE.search(html)
        if jsonld_match is None:
            return None
        try:
            data = json.loads(jsonld_match.group(1))
        except json.JSONDecodeError:
            return None

        graph = data.get("@graph") or []
        product = next((node for node in graph if node.get("@type") == "Product"), None)
        if product is None:
            return None

        breadcrumb = next((node for node in graph if node.get("@type") == "BreadcrumbList"), None)
        location = ""
        city = ""
        if breadcrumb is not None:
            # az első három elem mindig "Jófogás", "Ingatlan" és a kategória
            # (pl. "Lakás"), azokat kihagyjuk - a kategóriát a property_type
            # már tartalmazza a product.category mezőből.
            names = [item["name"] for item in breadcrumb.get("itemListElement", [])[3:]]
            location = ", ".join(names)
            # names[0] a megye, names[1] a település (ami önmagában is
            # tartalmazhat több, vesszővel elválasztott nevet, pl.
            # "Agárd, Gárdony" - ilyenkor az elsőt vesszük városnak).
            if len(names) > 1:
                city = names[1].split(",")[0].strip()
            elif names:
                city = names[0].split(",")[0].strip()

        size = next(
            (prop.get("value", "") for prop in product.get("additionalProperty", []) if prop.get("name") == "Méret"),
            "",
        )
        rooms = next(
            (prop.get("value", "") for prop in product.get("additionalProperty", []) if prop.get("name") == "Szobák száma"),
            "",
        )
        condition = next(
            (prop.get("value", "") for prop in product.get("additionalProperty", []) if prop.get("name") == "Állapot"),
            "",
        )
        offers = product.get("offers") or {}

        return Property(
            url=url,
            portal=self.name,
            property_id=str(product.get("sku", "")),
            property_type=normalize_property_type(product.get("category")),
            condition=normalize_condition(condition),
            title=str(product.get("name", "")),
            price=str(offers.get("price", "")),
            currency=str(offers.get("priceCurrency", "")),
            area_sqm=parse_area_sqm(size),
            rooms=parse_rooms(rooms),
            location=location,
            city=city,
        )
