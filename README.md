# scraper

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
python3 -m scraper seed
python3 -m scraper fetch --count 3
python3 -m scraper status
python3 -m scraper parse
python3 -m scraper geocode
python3 -m scraper show_data
python3 -m scraper export [output.zip]
python3 -m scraper import <input.zip>
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
python3 -m scraper fetch --count 3 --min-delay 2 --max-delay 6
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

A `location` mezőt egyúttal GPS koordinátává is alakítja (lásd `geocode`
lejjebb) egy lokálisan futó Nominatim API-n keresztül, és a `lat`/`lon`
mezőket is kitölti. Ha a geocoding API nem érhető el, az adott hirdetés
koordináta nélkül kerül be, de a `parse` ettől nem áll meg — újrafuttatva
(vagy a `geocode` paranccsal) utólag is pótolható.

Újra futtatva a már feldolgozott hirdetéseket frissíti (URL alapján nem
duplikál).

### `geocode`

```
python3 -m scraper geocode
```

A `parse` parancs már automatikusan geocode-olja az új hirdetéseket, ez a
parancs arra való, hogy utólag pótolja azokat a koordinátákat, amik valamiért
(pl. a geocoding API nem volt elérhető a `parse` futásakor) még hiányoznak a
`data/properties.csv`-ből. Végigmegy a már feldolgozott hirdetéseken, és
akinek még nincs GPS koordinátája (`lat`/`lon` oszlop), annak a `location`
mezőjét egy lokálisan futó [Nominatim](https://nominatim.org/) API-n keresztül
(lásd lejjebb) GPS koordinátává alakítja. A lekérdezett címeket a
`data/geocode_cache.csv`-ben gyorsítótárazza (a sikerteleneket is), így egy
címet csak egyszer kérdez le.

- `--delay`: várakozás (mp) két, nem cache-elt lekérdezés között
  (alapértelmezett: 0 — lokális szerver esetén nincs szükség korlátozásra)
- a Nominatim API címe a `NOMINATIM_URL` környezeti változóval írható felül
  (alapértelmezett: `http://localhost:8080/search`)

#### Lokális Nominatim szerver indítása

A nyilvános `nominatim.openstreetmap.org` helyett (ami max. 1 kérés/mp-re
korlátoz) érdemes lokálisan futtatni egy saját Nominatim szervert, csak
Magyarország OSM adataival (ez elég a hazai portálok címeihez, és nem kell a
teljes bolygót importálni):

```
docker compose up -d
```

Ez az első indításkor letölti és importálja Magyarország OSM extractját
(`docker-compose.yml`), ami néhány GB helyet és 10-30 percet vehet igénybe.
Az import végén a `http://localhost:8080` alatt elérhető a saját, korlátlanul
hívható geocoding API. Az importált adatok a `nominatim-data` docker volume-ban
maradnak meg, így a konténer újraindításakor nem kell újraimportálni.

### `show_data`

Betölti a `data/properties.csv`-t `pandas` DataFrame-ként, és táblázatos
formában kiírja a már feldolgozott ingatlanadatokat.

### `export`

```
python3 -m scraper export backup.zip
```

Egy zip fájlba csomagolja a `data/links.csv`-t és az összes letöltött
`data/html/**/*.html` fájlt (a zipen belül `links.csv` + `html/<portál>/<hash>.html`
szerkezetben). Ha nem adsz meg kimeneti fájlnevet, `export.zip`-be ment.

### `import`

```
python3 -m scraper import backup.zip
```

Egy korábban `export`-tal létrehozott zip tartalmát (HTML fájlok + `links.csv`)
összefésüli a jelenlegi adatokkal:

- az eddig ismeretlen linkeket felveszi a `data/links.csv`-be, a hozzájuk
  tartozó HTML fájlt pedig átmásolja a megfelelő helyre;
- ha egy link már szerepel a CSV-ben, de csak `pending`/`error` státuszban,
  az importból érkező `downloaded` állapot és HTML fájl felülírja/pótolja;
- egyébként a meglévő rekord marad, nem keletkezik duplikátum.

Mivel a linkek URL szerint kulcsolt rekordok, a `data/links.csv` import után
is garantáltan csak egyszer tartalmaz egy-egy linket. Ez teszi lehetővé, hogy
több helyen (pl. több gépen) külön-külön letöltött adagokat utólag egy közös
adatbázisba lehessen összefésülni.

## Adatok

```
data/
  links.csv      # url, portal, status, discovered_at, downloaded_at, file_path
  properties.csv # url, portal, property_id, property_type, condition, title,
                 # price, currency, area_sqm, rooms, location, lat, lon,
                 # scraped_at, source_file
  geocode_cache.csv # address, lat, lon (a geocode parancs gyorsítótára)
  html/
    ingatlan_com/<hash>.html
    oc_hu/<hash>.html
```

## Új portál hozzáadása

1. Új fájl a `scraper/portals/` alá, benne egy `Portal` alosztály:
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
   (`scraper/portals/__init__.py`).

## Ismert korlátozás

Az **ingatlan.com** Cloudflare bot-védelemmel blokkolja az automatizált
kéréseket (`403 Forbidden`). A `fetch` ezt hibaként kezeli (`status=error`,
a link később újra megpróbálkozik vele), de magát a bot-védelmet a program
nem próbálja megkerülni. Emiatt az `IngatlanComPortal.parse_property` is csak
feltételezésen alapul (nem volt tesztelhető valódi letöltött HTML-en) — ha
sikerül valódi hirdetés-HTML-hez hozzáférni, a mezőneveket a
`scraper/portals/ingatlan_com.py`-ban kell majd pontosítani.

## Támogatott portálok

- **oc.hu**: a hirdetés-részletező oldalakba ágyazott Google Tag Manager
  `dataLayer.push({... "event":"view_item" ...})` hívásból nyeri ki az
  adatokat (`scraper/gtm.py`).
- **jofogas.hu** (`ingatlan.jofogas.hu`): sima szerveroldali HTML, a
  hirdetés-részletező oldalak egy schema.org `Product` JSON-LD blokkot
  tartalmaznak (`scraper/portals/jofogas_hu.py`).
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
