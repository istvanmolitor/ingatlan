# ingatlan_scraper

Ingatlanportálok hirdetéseinek gyűjtésére szolgáló eszköz: HTML-eket tölt le
portálonként mappázva, nyomon követi a linkeket egy CSV-ben, majd a letöltött
HTML-eket egységes formátumú (DTO) adatokká alakítja és egy közös CSV-be írja.

## Előfeltétel

```
pip install requests pandas
```

(a `requests` és `pandas` csomagokon kívül csak a Python standard library-t használja; a `pandas` csak a `show_data` parancshoz szükséges)

## Parancsok

Mindig a projekt gyökeréből (`/home/molitor/work/ingatlan`) futtasd:

```
python3 -m ingatlan_scraper seed
python3 -m ingatlan_scraper fetch --count 3
python3 -m ingatlan_scraper status
python3 -m ingatlan_scraper parse
python3 -m ingatlan_scraper show_data
```

### `seed`

Felveszi a portálok kezdő (seed) URL-jeit a `data/links.csv`-be
`pending` státusszal, ha még nincsenek benne. A seed URL-ek portálonkénti
listázó/kereső oldalak (pl. ingatlan.com "eladó lakás" keresés), ezekről indul
a hirdetéslinkek felderítése.

### `fetch`

Letölt egy kis, véletlenszerűen kiválasztott adagot a még le nem töltött
(`pending` vagy korábban hibázott `error` státuszú) linkekből:

```
python3 -m ingatlan_scraper fetch --count 3 --min-delay 2 --max-delay 6
```

- `--count`: hány linket töltsön le ebben a futásban (alapértelmezett: 3)
- `--min-delay` / `--max-delay`: véletlenszerű várakozás (mp) két letöltés
  között, hogy a portált ne terheljük feleslegesen

Minden letöltött HTML-t elment a `data/html/<portál>/<hash>.html` alá, majd a
HTML-ből kinyeri a portálhoz illő hirdetéslinkeket, és az újakat `pending`
státusszal felveszi a CSV-be — így a következő `fetch` futás ezeket is
letöltheti. A CSV-ben nyomon van tartva, hogy melyik link mikor és melyik
fájlba lett letöltve.

Ha a CSV még teljesen üres, a `fetch` automatikusan seedel is.

### `status`

Kiírja portálonként, hány link van `pending` / `downloaded` / `error`
státuszban a `data/links.csv`-ben.

### `parse`

Végigmegy a már letöltött (`downloaded` státuszú) HTML fájlokon, és
portálonkénti logika szerint egységes `Property` DTO-vá alakítja őket
(ár, terület, helyszín, típus stb.), majd a közös `data/properties.csv`-be
írja. Ha egy letöltött HTML nem hirdetés-részletező oldal (pl. egy
listázó/kereső oldal volt), azt kihagyja.

Újra futtatva a már feldolgozott hirdetéseket frissíti (URL alapján nem
duplikál).

### `show_data`

Betölti a `data/properties.csv`-t `pandas` DataFrame-ként, és táblázatos
formában kiírja a már feldolgozott ingatlanadatokat.

## Adatok

```
data/
  links.csv      # url, portal, status, discovered_at, downloaded_at, file_path
  properties.csv # url, portal, property_id, property_type, title, price,
                 # currency, area_sqm, rooms, location, parsed_at, source_file
  html/
    ingatlan_com/<hash>.html
    oc_hu/<hash>.html
```

## Új portál hozzáadása

1. Új fájl a `ingatlan_scraper/portals/` alá, benne egy `Portal` alosztály:
   - `name`, `domain`, `seed_urls`
   - `link_pattern`: regex, amivel a hirdetés-részletező linkeket lehet
     felismerni a listázó oldalak HTML-jében
   - `parse_property(html, url) -> Property | None`: a letöltött
     hirdetés-HTML-ből hogyan épül fel az egységes `Property` DTO
2. Felvenni az új osztály példányát az `ALL_PORTALS` listába
   (`ingatlan_scraper/portals/__init__.py`).

## Ismert korlátozás

Az **ingatlan.com** Cloudflare bot-védelemmel blokkolja az automatizált
kéréseket (`403 Forbidden`). A `fetch` ezt hibaként kezeli (`status=error`,
a link később újra megpróbálkozik vele), de magát a bot-védelmet a program
nem próbálja megkerülni. Emiatt az `IngatlanComPortal.parse_property` is csak
feltételezésen alapul (nem volt tesztelhető valódi letöltött HTML-en) — ha
sikerül valódi hirdetés-HTML-hez hozzáférni, a mezőneveket a
`ingatlan_scraper/portals/ingatlan_com.py`-ban kell majd pontosítani.

Az **oc.hu** portál működik: a hirdetés-részletező oldalakba ágyazott Google
Tag Manager `dataLayer.push({... "event":"view_item" ...})` hívásból nyeri ki
az adatokat (`ingatlan_scraper/gtm.py`).
