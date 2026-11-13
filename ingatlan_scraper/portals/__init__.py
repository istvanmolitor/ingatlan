from .base import Portal
from .ingatlan_com import IngatlanComPortal
from .oc_hu import OcHuPortal

ALL_PORTALS: list[Portal] = [IngatlanComPortal(), OcHuPortal()]
PORTALS_BY_NAME: dict[str, Portal] = {portal.name: portal for portal in ALL_PORTALS}


def find_portal_for_url(url: str) -> Portal | None:
    for portal in ALL_PORTALS:
        if portal.belongs_to(url):
            return portal
    return None
