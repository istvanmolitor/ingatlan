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
   - `extract_property_links(html, base_url) -> set[str]`: hogyan lehet a
     letöltött (listázó vagy hirdetés-) oldalból kinyerni a hirdetés-
     részletező linkeket
   - `parse_property(html, url) -> Property | None`: a letöltött
     hirdetés-tartalomból hogyan épül fel az egységes `Property` DTO
   - ha a portál a hirdetéseket (vagy a listázó oldalakat) csak egy JSON
     API-n keresztül szolgáltatja ki (pl. POST kéréssel, mert a weboldal
     kliensoldalon – Angular/React – épül fel), a `fetch_html(url)` metódus
     felülírható, hogy a sima GET helyett a megfelelő API-hívást végezze el
     (lásd `DhHuPortal` / `ZengaHuPortal`)
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

## Támogatott portálok

- **oc.hu**: a hirdetés-részletező oldalakba ágyazott Google Tag Manager
  `dataLayer.push({... "event":"view_item" ...})` hívásból nyeri ki az
  adatokat (`ingatlan_scraper/gtm.py`).
- **jofogas.hu** (`ingatlan.jofogas.hu`): sima szerveroldali HTML, a
  hirdetés-részletező oldalak egy schema.org `Product` JSON-LD blokkot
  tartalmaznak (`ingatlan_scraper/portals/jofogas_hu.py`).
- **ingatlanbazar.hu**: a weboldal kliensoldali (Angular) SPA, de a
  hirdetéseket egy nyilvános, sima GET-tel elérhető JSON API szolgáltatja ki
  (`/api/property-search`, `/api/property/<id>`), ezt használjuk HTML
  letöltés helyett.
- **dh.hu** (korábban/márkanév szerint "Duna House" — a `duna-house.hu`
  domain nem létezik): szintén Angular SPA, a saját JSON API-ját
  (`newdhapi03.dh.hu`) hívjuk a `Portal.fetch_html` felülírásával (a
  listázáshoz POST, a hirdetés-részletezőhöz GET kérés szükséges).
- **zenga.hu** (az **ingatlan.net** domain 2026-ban ide irányít át):
  ugyanígy SPA, a saját JSON API-ját (`/api/rels/v1/adverts/...`) hívjuk,
  a kereséshez POST-tal, a hirdetés-részletezőhöz GET-tel.

Mivel az ingatlanbazar.hu, a dh.hu és a zenga.hu mögötti JSON API-k nem
publikus, dokumentált API-k, hanem a weboldal saját, reverse-engineeringelt
belső végpontjai, bármikor változhatnak — ha egy ilyen portál hirtelen leáll
(`error` státuszú linkek halmozódnak, vagy a `parse` sok mindent kihagy),
érdemes friss böngésző-hálózati naplóval (DevTools → Network) ellenőrizni,
hogy a végpont vagy a válasz formátuma nem változott-e.
