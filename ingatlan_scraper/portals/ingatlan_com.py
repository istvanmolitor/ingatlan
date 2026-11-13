import re
from urllib.parse import urljoin

from ..gtm import find_ecommerce_item
from ..html_links import extract_hrefs
from ..models import Property
from .base import Portal

# hirdetés URL-ek numerikus azonosítóval záródnak, pl. .../33069975
_PROPERTY_LINK_RE = re.compile(r"ingatlan\.com/(?:[\w-]+/)*\d{6,}(?:-[\w-]+)?/?$", re.IGNORECASE)


class IngatlanComPortal(Portal):
    name = "ingatlan.com"
    domain = "ingatlan.com"
    seed_urls = [
        "https://ingatlan.com/szukites/elado+lakas",
        "https://ingatlan.com/szukites/elado+haz",
    ]

    def extract_property_links(self, html: str, base_url: str) -> set[str]:
        links = set()
        for href in extract_hrefs(html):
            absolute = urljoin(base_url, href)
            if self.belongs_to(absolute) and _PROPERTY_LINK_RE.search(absolute):
                links.add(self._normalize(absolute))
        return links

    def parse_property(self, html: str, url: str) -> Property | None:
        # Az ingatlan.com bot-védelme miatt élő hirdetés-HTML-en nem sikerült
        # ellenőrizni a pontos mezőneveket, ezért több lehetséges kulcsnevet is
        # kipróbálunk a GTM "view_item" dataLayer push-ban. Ha a valós HTML-ben
        # más kulcsnevek szerepelnek, itt kell módosítani.
        item = find_ecommerce_item(html)
        if item is None:
            return None

        def pick(*keys: str, default: str = "") -> str:
            for key in keys:
                value = item.get(key)
                if value not in (None, ""):
                    return str(value)
            return default

        if "kiad" in pick("type_of_sale", "ad_type", "listing_type").lower():
            return None

        return Property(
            url=url,
            portal=self.name,
            property_id=pick("item_id", "id", "ad_id"),
            property_type=pick("real_estate_type", "property_type", "category"),
            title=pick("item_name", "name", "title"),
            price=pick("price", "value"),
            currency=pick("currency", default="HUF"),
            area_sqm=pick("size", "area", "living_area"),
            location=pick("location_city", "city", "settlement"),
        )
