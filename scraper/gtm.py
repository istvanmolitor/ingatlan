from __future__ import annotations

import json

# Sok ingatlanportál Google Tag Manager "ecommerce" dataLayer push-ot ágyaz be
# minden hirdetés-részletező oldalba (pl. "view_item" esemény), ami a hirdetés
# fő adatait (ár, méret, típus stb.) JSON-ként tartalmazza. Ezt próbáljuk kiolvasni.
_MARKER = "dataLayer.push("


def find_datalayer_pushes(html: str) -> list[dict]:
    pushes = []
    search_from = 0
    while True:
        marker_idx = html.find(_MARKER, search_from)
        if marker_idx == -1:
            break
        brace_idx = html.find("{", marker_idx)
        if brace_idx == -1:
            break

        depth = 0
        end_idx = None
        for i in range(brace_idx, len(html)):
            if html[i] == "{":
                depth += 1
            elif html[i] == "}":
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break

        if end_idx is None:
            break

        try:
            pushes.append(json.loads(html[brace_idx : end_idx + 1]))
        except json.JSONDecodeError:
            pass

        search_from = end_idx + 1

    return pushes


def find_ecommerce_item(html: str, event: str = "view_item") -> dict | None:
    for payload in find_datalayer_pushes(html):
        if payload.get("event") != event:
            continue
        items = (payload.get("ecommerce") or {}).get("items") or []
        if items:
            return items[0]
    return None
