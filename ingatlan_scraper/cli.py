from __future__ import annotations

import argparse
import hashlib
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .csv_store import LinkRecord, LinkStore, PropertyStore
from .portals import ALL_PORTALS, PORTALS_BY_NAME, find_portal_for_url

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "links.csv"
PROPERTIES_CSV_PATH = DATA_DIR / "properties.csv"
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
            if LinkStore.add_new(records, url, portal.name, now_iso()):
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
    for portal_name, counts in per_portal.items():
        print(f"{portal_name}: pending={counts.get('pending', 0)} downloaded={counts.get('downloaded', 0)} error={counts.get('error', 0)}")


def cmd_fetch(count: int, min_delay: float, max_delay: float) -> None:
    store = LinkStore(CSV_PATH)
    records = store.load()
    if not records:
        print("A CSV üres, előbb seedelünk...")
        for portal in ALL_PORTALS:
            for url in portal.seed_urls:
                LinkStore.add_new(records, url, portal.name, now_iso())

    pending_urls = [url for url, record in records.items() if record.status in ("pending", "error")]
    if not pending_urls:
        print("Nincs letöltésre váró link.")
        store.save(records)
        return

    random.shuffle(pending_urls)
    batch = pending_urls[:count]

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

        discovered_links = portal.extract_property_links(html, url)
        for link in discovered_links:
            if LinkStore.add_new(records, link, portal.name, now_iso()):
                new_links_found += 1

        if i < len(batch) - 1:
            time.sleep(random.uniform(min_delay, max_delay))

    store.save(records)
    print(f"Kész. Újonnan talált link: {new_links_found}")


def cmd_parse() -> None:
    link_store = LinkStore(CSV_PATH)
    records = link_store.load()
    property_store = PropertyStore(PROPERTIES_CSV_PATH)
    properties = property_store.load()

    parsed_count = 0
    skipped_count = 0
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
        prop = portal.parse_property(html, record.url)
        if prop is None:
            skipped_count += 1
            continue

        prop.parsed_at = now_iso()
        prop.source_file = record.file_path
        properties[record.url] = prop
        parsed_count += 1

    property_store.save(properties)
    print(f"Feldolgozott hirdetés: {parsed_count}, kihagyva (nem hirdetés-oldal vagy nem parse-olható): {skipped_count}")


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

    args = parser.parse_args(argv)

    if args.command == "seed":
        cmd_seed()
    elif args.command == "fetch":
        cmd_fetch(args.count, args.min_delay, args.max_delay)
    elif args.command == "status":
        cmd_status()
    elif args.command == "parse":
        cmd_parse()
    elif args.command == "show_data":
        cmd_show_data()


if __name__ == "__main__":
    sys.exit(main())
