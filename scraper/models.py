from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum

# Egy link/HTML tartalmának típusa: lista (kereső/listázó) oldal, konkrét
# ingatlan hirdetés, vagy egyéb (sem lista, sem hirdetés) oldal.
PAGE_TYPE_LISTING = "listing"
PAGE_TYPE_PROPERTY = "property"
PAGE_TYPE_OTHER = "other"


class PropertyType(str, Enum):
    """Egységes ingatlan típus, portálonként eltérő elnevezések helyett.

    Pl. a zenga.hu "HOUSE", az oc.hu "ház", a dh.hu "Ház" helyett mindhárom
    `PropertyType.HAZ`-ra normalizálódik.
    """

    LAKAS = "lakas"
    HAZ = "haz"
    SORHAZ = "sorhaz"
    TELEK = "telek"
    NYARALO = "nyaralo"
    BERUHAZAS = "beruhazas"
    EGYEB = "egyeb"


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize_property_type(value: object) -> PropertyType:
    """Portálonként eltérő property_type szöveg (pl. "HAUSE", "Ház", "ház",
    "Sorház/ikerház/házrész") egységes `PropertyType` értékké alakítása.

    A sorrend fontos: a specifikusabb kulcsszavakat (pl. "sorhaz") előbb
    kell vizsgálni, mert azok szövege a generikusabb "haz" kulcsszót is
    tartalmazza.
    """
    if not value:
        return PropertyType.EGYEB
    text = _strip_accents(str(value)).lower()
    if any(keyword in text for keyword in ("sorhaz", "ikerhaz", "hazresz", "terraced", "semi-detached", "semidetached")):
        return PropertyType.SORHAZ
    if any(keyword in text for keyword in ("nyaral", "udulo", "holiday", "vacation")):
        return PropertyType.NYARALO
    if any(keyword in text for keyword in ("telek", "fold", "plot", "land")):
        return PropertyType.TELEK
    if any(keyword in text for keyword in ("beruhaz", "investment")):
        return PropertyType.BERUHAZAS
    if any(keyword in text for keyword in ("lak", "flat", "apartment", "condo")):
        return PropertyType.LAKAS
    if any(keyword in text for keyword in ("haz", "house")):
        return PropertyType.HAZ
    return PropertyType.EGYEB


class PropertyCondition(str, Enum):
    """Egységes ingatlan állapot, portálonként eltérő elnevezések helyett.

    Pl. a dh.hu "6 - Új. ép.", az oc.hu "Kiváló" helyett mindkettő
    `PropertyCondition.UJ`, illetve `PropertyCondition.KIVALO` értékre
    normalizálódik.
    """

    UJ = "uj"
    FELUJITOTT = "felujitott"
    KIVALO = "kivalo"
    JO = "jo"
    ATLAGOS = "atlagos"
    FELUJITANDO = "felujitando"
    BONTANDO = "bontando"
    EGYEB = "egyeb"


def normalize_condition(value: object) -> PropertyCondition:
    """Portálonként eltérő condition/állapot szöveg (pl. "6 - Új. ép.",
    "Jó állapotú", "Kiváló") egységes `PropertyCondition` értékké alakítása.

    A sorrend fontos: a specifikusabb kulcsszavakat (pl. "felujitando") előbb
    kell vizsgálni, mert azok szövege egy generikusabb kulcsszót (pl. "uj",
    ami a "felUJitott"-ban is megtalálható) is tartalmazhat.
    """
    if not value:
        return PropertyCondition.EGYEB
    text = _strip_accents(str(value)).lower()
    if "bontand" in text:
        return PropertyCondition.BONTANDO
    if "felujitand" in text or ("felujit" in text and "szorul" in text):
        return PropertyCondition.FELUJITANDO
    if "felujit" in text:
        return PropertyCondition.FELUJITOTT
    if any(keyword in text for keyword in ("uj", "new")):
        return PropertyCondition.UJ
    if any(keyword in text for keyword in ("kivalo", "nagyon jo", "premium", "excellent")):
        return PropertyCondition.KIVALO
    if any(keyword in text for keyword in ("atlagos", "kozepes", "lakhato", "average")):
        return PropertyCondition.ATLAGOS
    if any(keyword in text for keyword in ("jo", "good")):
        return PropertyCondition.JO
    return PropertyCondition.EGYEB

PROPERTY_FIELDNAMES = [
    "url",
    "portal",
    "property_id",
    "property_type",
    "condition",
    "title",
    "price",
    "currency",
    "area_sqm",
    "rooms",
    "location",
    "city",
    "lat",
    "lon",
    "scraped_at",
    "source_file",
]


def parse_area_sqm(value: object) -> int:
    """Négyzetméter érték DTO-kompatibilis egésszé alakítása.

    A portálok négyzetmétert különböző formában adják (pl. "110 m²",
    "155.46", 45), ezért a nem numerikus karaktereket levágjuk, majd
    egészre kerekítünk.
    """
    if value in (None, ""):
        return 0
    match = re.search(r"-?\d+(?:[.,]\d+)?", str(value))
    if not match:
        return 0
    return round(float(match.group(0).replace(",", ".")))


def parse_rooms(value: object) -> float | None:
    """Szobák száma DTO-kompatibilis float-tá vagy None-ná alakítása.

    A portálok a szobaszámot különböző formában adják (pl. "3 szoba",
    "5+ szoba", "3+1 fél", 2.5, vagy üresen), ezért a nem numerikus
    részeket levágjuk; a "fél" (fél szoba) szó jelenlétét +0.5-ként
    vesszük figyelembe. Ha nincs felismerhető szám, None-t adunk vissza
    (nincs kitöltve), mert 0 szoba nem ugyanaz, mint "nem tudjuk".
    """
    if value in (None, ""):
        return None
    text = _strip_accents(str(value)).lower()
    match = re.search(r"\d+(?:[.,]\d+)?", text)
    if match is None:
        return None
    rooms = float(match.group(0).replace(",", "."))
    if "fel" in text and "." not in match.group(0) and "," not in match.group(0):
        rooms += 0.5
    return rooms


@dataclass
class Property:
    url: str
    portal: str
    property_id: str = ""
    property_type: PropertyType = PropertyType.EGYEB
    condition: PropertyCondition = PropertyCondition.EGYEB
    title: str = ""
    price: str = ""
    currency: str = ""
    area_sqm: int = 0
    rooms: float | None = None
    location: str = ""
    city: str = ""
    lat: str = ""
    lon: str = ""
    scraped_at: str = ""
    source_file: str = ""
