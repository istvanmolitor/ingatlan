from __future__ import annotations

import re
from abc import ABC, abstractmethod
from urllib.parse import urlparse

from .. import downloader
from ..models import PAGE_TYPE_LISTING, PAGE_TYPE_OTHER, PAGE_TYPE_PROPERTY, Property


class Portal(ABC):
    name: str
    domain: str
    seed_urls: list[str] = []

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "_", self.name.lower()).strip("_")

    def belongs_to(self, url: str) -> bool:
        return self.domain in urlparse(url).netloc

    def fetch_html(self, url: str) -> str:
        """Letölti egy linkhez tartozó tartalmat.

        Alapesetben egy sima GET kérés (lásd `downloader.fetch_html`). Azok a
        portálok, amelyek a hirdetéseket (vagy a listázó oldalakat) csak egy
        JSON API-n keresztül szolgáltatják ki (pl. POST kéréssel), itt
        felülírhatják a letöltés módját.
        """
        return downloader.fetch_html(url)

    @abstractmethod
    def extract_property_links(self, html: str, base_url: str) -> set[str]:
        """Visszaadja a html-ben található, ehhez a portálhoz tartozó ingatlan hirdetés linkeket."""

    def classify_page(self, html: str, url: str) -> str:
        """Eldönti, hogy egy letöltött html/link lista oldal, konkrét hirdetés, vagy egyéb.

        Visszatérési érték: `PAGE_TYPE_LISTING`, `PAGE_TYPE_PROPERTY` vagy
        `PAGE_TYPE_OTHER`. Azért a `parse_property`-tól független logika,
        mert pl. egy kiadás-hirdetés a `parse_property`-nak None-t ad vissza
        (azt a célunk szerint nem tároljuk hirdetésként), holott a lapon
        valójában egy konkrét hirdetés van, nem egy lista oldal.

        Az alapértelmezett implementáció a meglévő
        `extract_property_links`/`parse_property` logikára épül; azok a
        portálok, ahol ez pontatlan (pl. kiadás-hirdetések), felülírhatják.
        """
        if self.parse_property(html, url) is not None:
            return PAGE_TYPE_PROPERTY
        if self.extract_property_links(html, url):
            return PAGE_TYPE_LISTING
        return PAGE_TYPE_OTHER

    @staticmethod
    def _normalize(url: str) -> str:
        # Séma/domain kis-nagybetű és a záró "/" eltérés ne okozzon duplikátumot
        # ugyanarra a hirdetésre (az útvonal case-ét megtartjuk, mert az
        # azonosítók kis-nagybetű érzékenyek lehetnek, pl. "H526174").
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        return parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
            path=path,
            query="",
            fragment="",
        ).geturl()

    @abstractmethod
    def parse_property(self, html: str, url: str) -> Property | None:
        """Egységes Property DTO-t épít egy letöltött hirdetés-részletező HTML-ből.

        Ha a HTML nem hirdetés-részletező oldal (pl. egy listázó/kereső oldal),
        vagy a várt adatok nem találhatók benne, None-t ad vissza.
        """
