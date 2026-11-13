from __future__ import annotations

import re
from abc import ABC, abstractmethod
from urllib.parse import urlparse

from ..models import Property


class Portal(ABC):
    name: str
    domain: str
    seed_urls: list[str] = []

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "_", self.name.lower()).strip("_")

    def belongs_to(self, url: str) -> bool:
        return self.domain in urlparse(url).netloc

    @abstractmethod
    def extract_property_links(self, html: str, base_url: str) -> set[str]:
        """Visszaadja a html-ben található, ehhez a portálhoz tartozó ingatlan hirdetés linkeket."""

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
