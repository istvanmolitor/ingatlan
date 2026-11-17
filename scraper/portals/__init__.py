from .base import Portal
from .dh_hu import DhHuPortal
# from .ingatlan_com import IngatlanComPortal
from .ingatlanbazar_hu import IngatlanbazarHuPortal
from .jofogas_hu import JofogasHuPortal
from .oc_hu import OcHuPortal
from .zenga_hu import ZengaHuPortal

ALL_PORTALS: list[Portal] = [
    # IngatlanComPortal(),
    OcHuPortal(),
    JofogasHuPortal(),
    IngatlanbazarHuPortal(),
    DhHuPortal(),
    ZengaHuPortal(),
]
PORTALS_BY_NAME: dict[str, Portal] = {portal.name: portal for portal in ALL_PORTALS}


def find_portal_for_url(url: str) -> Portal | None:
    for portal in ALL_PORTALS:
        if portal.belongs_to(url):
            return portal
    return None
