from __future__ import annotations

import argparse
import hashlib
import random
import shutil
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .csv_store import LinkRecord, LinkStore, PropertyStore
from .models import PAGE_TYPE_LISTING, PAGE_TYPE_PROPERTY
from .portals import ALL_PORTALS, PORTALS_BY_NAME, find_portal_for_url

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "links.csv"
PROPERTIES_CSV_PATH = DATA_DIR / "properties.csv"
GEOCODE_CACHE_CSV_PATH = DATA_DIR / "geocode_cache.csv"
HTML_DIR = DATA_DIR / "html"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def html_file_path(portal_slug: str, url: str) -> Path:
    file_id = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return HTML_DIR / portal_slug / f"{file_id}.html"


def cmd_seed() -> None:
    store = LinkStore(CSV_PATH)
    records = store.load()
    added = 0
    for portal in ALL_PORTALS:
        for url in portal.seed_urls:
            if LinkStore.add_new(records, url, portal.name, now_iso(), page_type=PAGE_TYPE_LISTING):
                added += 1
    store.save(records)
    print(f"Seed linkek hozzáadva: {added} (összesen a CSV-ben: {len(records)})")


def cmd_status() -> None:
    store = LinkStore(CSV_PATH)
    records = store.load()
    if not records:
        print("A CSV még üres. Futtasd előbb: seed")
        return
    per_portal: dict[str, dict[str, int]] = {}
    for record in records.values():
        counts = per_portal.setdefault(record.portal, {"pending": 0, "downloaded": 0, "error": 0})
        counts[record.status] = counts.get(record.status, 0) + 1

    headers = ["Portál", "Pending", "Downloaded", "Error", "Összesen"]
    rows = []
    totals = {"pending": 0, "downloaded": 0, "error": 0}
    for portal_name, counts in per_portal.items():
        pending = counts.get("pending", 0)
        downloaded = counts.get("downloaded", 0)
        error = counts.get("error", 0)
        totals["pending"] += pending
        totals["downloaded"] += downloaded
        totals["error"] += error
        rows.append([portal_name, str(pending), str(downloaded), str(error), str(pending + downloaded + error)])
    rows.append([
        "Összesen",
        str(totals["pending"]),
        str(totals["downloaded"]),
        str(totals["error"]),
        str(sum(totals.values())),
    ])

    widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))]
    separator = "-+-".join("-" * w for w in widths)

    def format_row(cells: list[str]) -> str:
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    print(format_row(headers))
    print(separator)
    for row in rows[:-1]:
        print(format_row(row))
    print(separator)
    print(format_row(rows[-1]))


def _round_robin_batch(records: dict, urls: list[str], count: int) -> list[str]:
    """Letöltési sorrend összeállítása úgy, hogy ugyanazon portál linkjei
    ne kövessék egymást közvetlenül (portálonkénti körbeforgatás)."""
    by_portal: dict[str, list[str]] = {}
    for url in urls:
        by_portal.setdefault(records[url].portal, []).append(url)
    for portal_urls in by_portal.values():
        random.shuffle(portal_urls)

    batch: list[str] = []
    last_portal = None
    while len(batch) < count and any(by_portal.values()):
        portal_names = [name for name, portal_urls in by_portal.items() if portal_urls]
        random.shuffle(portal_names)
        # ha van más portál is, kerüljük az előző kör utolsó portálját
        if last_portal in portal_names and len(portal_names) > 1:
            portal_names.remove(last_portal)
            portal_names.append(last_portal)
        for portal_name in portal_names:
            if len(batch) >= count:
                break
            portal_urls = by_portal[portal_name]
            batch.append(portal_urls.pop())
            last_portal = portal_name
    return batch


def build_batch(records: dict, pending_urls: list[str], count: int) -> list[str]:
    """Letöltési sorrend összeállítása. A lista oldalakat előnyben
    részesítjük, mivel egy letöltésükből több új link és (API-alapú
    portáloknál) több ingatlan adata is kinyerhető, mint egy konkrét
    hirdetés oldaláéból."""
    listing_urls = [url for url in pending_urls if records[url].page_type == PAGE_TYPE_LISTING]
    other_urls = [url for url in pending_urls if records[url].page_type != PAGE_TYPE_LISTING]

    batch = _round_robin_batch(records, listing_urls, count)
    if len(batch) < count:
        batch += _round_robin_batch(records, other_urls, count - len(batch))
    return batch


def cmd_fetch(count: int, min_delay: float, max_delay: float) -> None:
    store = LinkStore(CSV_PATH)
    records = store.load()
    if not records:
        print("A CSV üres, előbb seedelünk...")
        for portal in ALL_PORTALS:
            for url in portal.seed_urls:
                LinkStore.add_new(records, url, portal.name, now_iso(), page_type=PAGE_TYPE_LISTING)

    pending_urls = [url for url, record in records.items() if record.status in ("pending", "error")]
    if not pending_urls:
        print("Nincs letöltésre váró link.")
        store.save(records)
        return

    batch = build_batch(records, pending_urls, count)

    new_links_found = 0
    for i, url in enumerate(batch):
        record = records[url]
        portal = PORTALS_BY_NAME.get(record.portal)
        if portal is None:
            print(f"Ismeretlen portál ehhez a linkhez, kihagyva: {url}")
            continue

        print(f"Letöltés ({i + 1}/{len(batch)}): {url}")
        try:
            html = portal.fetch_html(url)
        except Exception as exc:  # noqa: BLE001 - egy sikertelen letöltés ne állítsa meg a futást
            print(f"  Hiba letöltés közben: {exc}")
            record.status = "error"
            continue

        file_path = html_file_path(portal.slug, url)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(html, encoding="utf-8")

        record.status = "downloaded"
        record.downloaded_at = now_iso()
        record.file_path = str(file_path.relative_to(BASE_DIR))
        record.page_type = portal.classify_page(html, url)

        discovered_links = portal.extract_property_links(html, url)
        for link in discovered_links:
            if LinkStore.add_new(records, link, portal.name, now_iso(), page_type=PAGE_TYPE_PROPERTY):
                new_links_found += 1

        if i < len(batch) - 1:
            time.sleep(random.uniform(min_delay, max_delay))

    store.save(records)
    print(f"Kész. Újonnan talált link: {new_links_found}")


def _geocode_location(location: str, cache: dict[str, tuple[str, str]]) -> tuple[str, str, str]:
    """Egy location mező GPS koordinátává alakítása, gyorsítótárral.

    Visszaadja a (lat, lon, forrás) hármast, ahol a forrás "cache", "new"
    vagy "failed" (cím nem található). A geocoding API hibáját (pl. nem fut
    a lokális szerver) nem itt kezeljük, hanem a hívó oldalon.
    """
    if location in cache:
        lat, lon = cache[location]
        return lat, lon, "cache"

    from .geocode import geocode

    result = geocode(location)
    if result is None:
        cache[location] = ("", "")
        return "", "", "failed"

    lat, lon = str(result[0]), str(result[1])
    cache[location] = (lat, lon)
    return lat, lon, "new"


def _try_geocode_location(location: str, cache: dict[str, tuple[str, str]]) -> tuple[str, str, str]:
    """_geocode_location hívása úgy, hogy ha a geocoding API egyáltalán nem
    érhető el (pl. a lokális Nominatim szerver nincs elindítva), azt egyetlen
    üzenettel jelezzük, és a hívó ezt a futás hátralévő részében kihagyhatja
    — így egy leállt szerver nem spammel ki egy hibát minden egyes
    hirdetésre."""
    import requests

    try:
        return _geocode_location(location, cache)
    except requests.exceptions.RequestException as exc:
        print(f"  A geocoding API nem érhető el ({exc}), a geocode-olás kihagyva ebben a futásban.")
        return "", "", "unavailable"


def cmd_parse() -> None:
    from .geocode import GeocodeCache

    link_store = LinkStore(CSV_PATH)
    records = link_store.load()
    property_store = PropertyStore(PROPERTIES_CSV_PATH)
    properties = property_store.load()
    cache_store = GeocodeCache(GEOCODE_CACHE_CSV_PATH)
    cache = cache_store.load()

    parsed_count = 0
    skipped_count = 0
    geocoded_count = 0
    geocode_failed_count = 0
    geocode_available = True
    for record in records.values():
        if record.status != "downloaded" or not record.file_path:
            continue

        portal = PORTALS_BY_NAME.get(record.portal)
        if portal is None:
            continue

        html_path = BASE_DIR / record.file_path
        if not html_path.exists():
            continue

        html = html_path.read_text(encoding="utf-8")
        record.page_type = portal.classify_page(html, record.url)
        prop = portal.parse_property(html, record.url)
        if prop is None:
            skipped_count += 1
            continue

        prop.parsed_at = now_iso()
        prop.source_file = record.file_path

        if prop.location and geocode_available:
            lat, lon, source = _try_geocode_location(prop.location, cache)
            if lat and lon:
                prop.lat = lat
                prop.lon = lon
            if source == "new":
                geocoded_count += 1
            elif source == "failed":
                geocode_failed_count += 1
            elif source == "unavailable":
                geocode_available = False

        properties[record.url] = prop
        parsed_count += 1

    link_store.save(records)
    property_store.save(properties)
    cache_store.save(cache)
    print(
        f"Feldolgozott hirdetés: {parsed_count}, kihagyva (nem hirdetés-oldal vagy nem parse-olható): {skipped_count}, "
        f"geocode-olt: {geocoded_count}, geocode sikertelen: {geocode_failed_count}"
    )


def cmd_geocode(delay: float) -> None:
    from .geocode import GeocodeCache

    property_store = PropertyStore(PROPERTIES_CSV_PATH)
    properties = property_store.load()
    cache_store = GeocodeCache(GEOCODE_CACHE_CSV_PATH)
    cache = cache_store.load()

    geocoded_count = 0
    cached_count = 0
    failed_count = 0
    geocode_available = True

    for prop in properties.values():
        if not prop.location or (prop.lat and prop.lon) or not geocode_available:
            continue

        lat, lon, source = _try_geocode_location(prop.location, cache)
        if lat and lon:
            prop.lat = lat
            prop.lon = lon

        if source == "cache":
            cached_count += 1
        elif source == "new":
            geocoded_count += 1
            if delay:
                time.sleep(delay)
        elif source == "failed":
            failed_count += 1
        elif source == "unavailable":
            geocode_available = False

    property_store.save(properties)
    cache_store.save(cache)
    print(
        f"Geocode kész. Újonnan lekérdezett: {geocoded_count}, cache-ből: {cached_count}, "
        f"sikertelen (cím nem található): {failed_count}"
    )


def cmd_show_data() -> None:
    import pandas as pd

    if not PROPERTIES_CSV_PATH.exists():
        print("A data/properties.csv még nem létezik. Futtasd előbb: parse")
        return

    df = pd.read_csv(PROPERTIES_CSV_PATH)
    df = df.drop(columns=["url", "title", "parsed_at", "source_file"], errors="ignore")
    pd.set_option("display.max_rows", None)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", None)
    print(df)


def cmd_export(output_path: Path) -> None:
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_count = 0
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if CSV_PATH.exists():
            zf.write(CSV_PATH, arcname="links.csv")
        if HTML_DIR.exists():
            for html_path in sorted(HTML_DIR.rglob("*.html")):
                arcname = str(Path("html") / html_path.relative_to(HTML_DIR))
                zf.write(html_path, arcname=arcname)
                html_count += 1
    print(f"Export kész: {output_path} (links.csv + {html_count} HTML fájl)")


def _copy_imported_html(tmp_dir: Path, record: LinkRecord) -> bool:
    """Az importált HTML fájl átmásolása a data/html alá, ha még nincs ott."""
    if record.status != "downloaded" or not record.file_path:
        return False

    try:
        relative = Path(record.file_path).relative_to(Path("data") / "html")
    except ValueError:
        return False

    source = tmp_dir / "html" / relative
    if not source.exists():
        return False

    dest = BASE_DIR / record.file_path
    if dest.exists():
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    return True


def cmd_import(input_path: Path) -> None:
    input_path = input_path.resolve()
    if not input_path.exists():
        print(f"A megadott fájl nem létezik: {input_path}")
        return

    store = LinkStore(CSV_PATH)
    records = store.load()

    added = 0
    upgraded = 0
    copied_files = 0

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        with zipfile.ZipFile(input_path, "r") as zf:
            zf.extractall(tmp_dir)

        incoming_csv = tmp_dir / "links.csv"
        if not incoming_csv.exists():
            print("A zip nem tartalmaz links.csv fájlt.")
            return

        incoming_records = LinkStore(incoming_csv).load()

        for url, incoming in incoming_records.items():
            existing = records.get(url)

            if existing is None:
                if _copy_imported_html(tmp_dir, incoming):
                    copied_files += 1
                records[url] = incoming
                added += 1
                continue

            # Egy link csak egyszer szerepelhet a CSV-ben: ha már megvan,
            # csak akkor frissítjük, ha az import letöltött állapotot hoz,
            # a meglévő viszont még nem az.
            if existing.status != "downloaded" and incoming.status == "downloaded":
                if _copy_imported_html(tmp_dir, incoming):
                    copied_files += 1
                existing.status = incoming.status
                existing.downloaded_at = incoming.downloaded_at
                existing.file_path = incoming.file_path
                existing.page_type = incoming.page_type
                upgraded += 1

    store.save(records)
    print(
        f"Import kész. Új link: {added}, letöltöttre frissített link: {upgraded}, "
        f"átmásolt HTML fájl: {copied_files} (összesen a CSV-ben: {len(records)})"
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ingatlan-scraper",
        description="Ingatlanportálok hirdetés-HTML-jeinek gyűjtése és linkjeinek nyomon követése.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="Portálok kezdő (seed) linkjeinek felvétele a CSV-be")

    fetch_parser = sub.add_parser("fetch", help="Néhány véletlenszerű, még le nem töltött link letöltése")
    fetch_parser.add_argument("--count", type=int, default=3, help="Hány linket töltsön le ebben a futásban (alapértelmezett: 3)")
    fetch_parser.add_argument("--min-delay", type=float, default=2.0, help="Minimum várakozás (mp) két letöltés között")
    fetch_parser.add_argument("--max-delay", type=float, default=6.0, help="Maximum várakozás (mp) két letöltés között")

    sub.add_parser("status", help="CSV statisztika portálonként")

    sub.add_parser("parse", help="Letöltött HTML-ek feldolgozása egységes Property DTO-vá és közös CSV-be írása")

    sub.add_parser("show_data", help="A már feldolgozott ingatlanadatok (data/properties.csv) megjelenítése pandas táblázatként")

    geocode_parser = sub.add_parser("geocode", help="A hirdetések location mezőjének GPS koordinátává alakítása (lokális Nominatim API-n keresztül)")
    geocode_parser.add_argument("--delay", type=float, default=0.0, help="Várakozás (mp) két, nem cache-elt geocode kérés között (alapértelmezett: 0, lokális szerver esetén nem szükséges)")

    export_parser = sub.add_parser("export", help="A links.csv és a letöltött HTML fájlok exportálása egy zip fájlba")
    export_parser.add_argument("output", type=Path, nargs="?", default=Path("export.zip"), help="A létrehozandó zip fájl elérési útja (alapértelmezett: export.zip)")

    import_parser = sub.add_parser("import", help="Korábban exportált zip (links.csv + HTML fájlok) összefésülése a meglévő adatokkal")
    import_parser.add_argument("input", type=Path, help="A beimportálandó zip fájl elérési útja")

    args = parser.parse_args(argv)

    if args.command == "seed":
        cmd_seed()
    elif args.command == "fetch":
        cmd_fetch(args.count, args.min_delay, args.max_delay)
    elif args.command == "status":
        cmd_status()
    elif args.command == "parse":
        cmd_parse()
    elif args.command == "geocode":
        cmd_geocode(args.delay)
    elif args.command == "show_data":
        cmd_show_data()
    elif args.command == "export":
        cmd_export(args.output)
    elif args.command == "import":
        cmd_import(args.input)


if __name__ == "__main__":
    sys.exit(main())
