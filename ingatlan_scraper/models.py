from __future__ import annotations

from dataclasses import dataclass

# Egy link/HTML tartalmának típusa: lista (kereső/listázó) oldal, konkrét
# ingatlan hirdetés, vagy egyéb (sem lista, sem hirdetés) oldal.
PAGE_TYPE_LISTING = "listing"
PAGE_TYPE_PROPERTY = "property"
PAGE_TYPE_OTHER = "other"

PROPERTY_FIELDNAMES = [
    "url",
    "portal",
    "property_id",
    "property_type",
    "title",
    "price",
    "currency",
    "area_sqm",
    "rooms",
    "location",
    "lat",
    "lon",
    "parsed_at",
    "source_file",
]


@dataclass
class Property:
    url: str
    portal: str
    property_id: str = ""
    property_type: str = ""
    title: str = ""
    price: str = ""
    currency: str = ""
    area_sqm: str = ""
    rooms: str = ""
    location: str = ""
    lat: str = ""
    lon: str = ""
    parsed_at: str = ""
    source_file: str = ""
