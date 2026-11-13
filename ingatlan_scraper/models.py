from __future__ import annotations

from dataclasses import dataclass

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
    parsed_at: str = ""
    source_file: str = ""
