import re
from urllib.parse import urljoin

from ..gtm import find_ecommerce_item
from ..html_links import extract_hrefs
from ..models import PAGE_TYPE_LISTING, PAGE_TYPE_OTHER, PAGE_TYPE_PROPERTY, Property, normalize_condition, normalize_property_type, parse_area_sqm
from .base import Portal

# hirdetés URL-ek formátuma: /ingatlanok/H123456 vagy /ingatlanok/NY123456
_PROPERTY_LINK_RE = re.compile(r"oc\.hu/ingatlanok/(?:H|NY)\d+", re.IGNORECASE)

# A hirdetés-részletező oldal jellemző adatai egy "data-label"/"data-value"
# div-pár formájában jelennek meg, pl.:
# <div class="col data-label">Állapot</div><div class="col data-value">Jó</div>
_CONDITION_RE = re.compile(r'col data-label">Állapot</div>\s*<div class="col data-value">([^<]*)</div>')


class OcHuPortal(Portal):
    name = "oc.hu"
    domain = "oc.hu"
    seed_urls = [
        "https://www.oc.hu/ingatlanok/lista/ertekesites:elado",
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
        # A hirdetés-részletező oldalak egy GTM "view_item" dataLayer push-ban
        # hordozzák a hirdetés adatait, pl.:
        # {"ecommerce":{"items":[{"real_estate_type":"lakás","type_of_sale":"használt eladó",
        #   "size":48,"currency":"HUF","item_id":"H526174","item_name":"H526174",
        #   "price":48000000,"location_city":"Budapest XVI. kerület",
        #   "location_district":"Rákosszentmihály","location_street":""}]},"event":"view_item"}
        item = find_ecommerce_item(html)
        if item is None:
            return None

        if "kiad" in str(item.get("type_of_sale", "")).lower():
            return None

        location = ", ".join(
            part
            for part in (
                item.get("location_city", ""),
                item.get("location_district", ""),
                item.get("location_street", ""),
            )
            if part
        )

        condition_match = _CONDITION_RE.search(html)

        return Property(
            url=url,
            portal=self.name,
            property_id=str(item.get("item_id", "")),
            property_type=normalize_property_type(item.get("real_estate_type")),
            condition=normalize_condition(condition_match.group(1) if condition_match else ""),
            title=str(item.get("item_name", "")),
            price=str(item.get("price", "")),
            currency=str(item.get("currency", "")),
            area_sqm=parse_area_sqm(item.get("size")),
            location=location,
        )
