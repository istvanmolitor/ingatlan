# Magyar ingatlanhirdetések ár-becslése

*Féléves projekt dokumentáció*

---

## 1. Bevezetés

### 1.1 Probléma

A projekt célja, hogy magyarországi (elsősorban eladó ház/lakás) ingatlanhirdetésekből
gyűjtött adatok alapján **megbecsülje egy ingatlan hirdetett árát** olyan jellemzők
felhasználásával, mint az alapterület, a szobaszám, az ingatlan típusa és a
földrajzi elhelyezkedés. A feladat tehát egy **regressziós** probléma: a cél
változó az `price` (illetve a modellezésben a log-transzformált `log_price`),
a magyarázó változók pedig a hirdetésekből kinyert, egységesített jellemzők.

### 1.2 Motiváció

Az ingatlanpiaci árak nyilvánosan hozzáférhetők ugyan hirdetési portálokon, de
**szétszórtan, portálonként eltérő formátumban és terminológiával** jelennek meg
(pl. ugyanaz az ingatlantípus az egyik portálon `"HOUSE"`, a másikon `"Ház"`,
a harmadikon `"Sorház/ikerház/házrész"` néven szerepel). Nincs egyetlen közös,
letölthető, tanításra alkalmas adatkészlet, amely több portál hirdetéseit
egységes séma szerint, árral és földrajzi koordinátával együtt tartalmazná.

A projekt emellett jó gyakorlófeladat egy **teljes, end-to-end adattudományi
pipeline** bemutatására: nyers, strukturálatlan weboldalaktól (HTML) induló
adatgyűjtés → egységes adatmodellre alakítás → geokódolás → feltáró
adatanalízis (EDA) → előfeldolgozás → regressziós modellezés → kiértékelés.

### 1.3 Mit old meg, és mit nem

A projekt egy **első, dokumentált baseline**-t ad az ár-becslésre, és
feltérképezi, mely jellemzők és adatminőségi problémák a legfontosabbak. **Nem**
cél egy éles, pontos árbecslő (pl. ingatlanközvetítői) rendszer felépítése —
ehhez jelentősen több adat, több jellemző (pl. állapot részletesebb kódolása,
emeletszám, energetikai besorolás) és finomabb modellezés szükséges. A
korlátokat az 5. (Elemzés) fejezetben részletezzük.

---

## 2. Adatkészlet

### 2.1 Forrás és gyűjtési módszer

Az adatokat egy saját fejlesztésű Python eszköz (`scraper/` modul) gyűjti öt
magyar ingatlanportálról:

| Portál | Hozzáférés módja |
|---|---|
| **oc.hu** | szerveroldali HTML, Google Tag Manager `dataLayer` JSON-ből |
| **jofogas.hu** | szerveroldali HTML, schema.org `Product` JSON-LD blokkból |
| **ingatlanbazar.hu** | kliensoldali (Angular) SPA, nyilvános JSON API-n keresztül |
| **dh.hu** (Duna House) | kliensoldali SPA, saját (nem dokumentált) JSON API-n keresztül |
| **zenga.hu** (korábban ingatlan.net) | kliensoldali SPA, saját JSON API-n keresztül |

A gyűjtés két lépésben történik:

1. **`fetch`** — seed (keresőoldal) linkekről indulva letölti a hirdetés-
   részletező oldalak HTML-jét (vagy a megfelelő JSON API válaszát), majd az
   onnan kinyert újabb hirdetéslinkeket is felveszi a letöltési sorba. A
   letöltések között véletlenszerű várakozás van, hogy a portálokat ne
   terheljük feleslegesen, és egy CSV (`data/links.csv`) nyomon követi
   minden link állapotát (`pending` / `downloaded` / `error`).
2. **`parse`** — a letöltött HTML-eket/API-válaszokat portálonkénti logika
   szerint egy egységes `Property` adatszerkezetté (DTO) alakítja (ár,
   terület, helyszín, típus, állapot stb.), és a közös `data/properties.csv`-be
   írja.

Egy ismert korlátozás: az **ingatlan.com** Cloudflare bot-védelemmel
blokkolja az automatizált kéréseket, ezért ez a portál a végleges
adatkészletben nem szerepel.

### 2.2 Geokódolás

A hirdetések `location` mezője szabad szöveg (pl. `"9444 Fertőszentmiklós , -"`
vagy `"Budapest V. kerület, Belváros, Október 6. utca"`). Ezt egy lokálisan
futtatott [Nominatim](https://nominatim.org/) szerver (OpenStreetMap
Magyarország-extract, Docker konténerben) alakítja GPS-koordinátává
(`lat`/`lon`). A lekérdezéseket egy cache CSV (`data/geocode_cache.csv`)
gyorsítja, így egy adott cím csak egyszer kerül lekérdezésre.

### 2.3 Az adatkészlet jelenlegi mérete és a `Property` séma

A dokumentáció frissítésekor a nyers adatkészlet **1615 hirdetést**
tartalmaz, portálonkénti megoszlásban:

| Portál | Hirdetések száma |
|---|---|
| jofogas.hu | 1197 |
| zenga.hu | 166 |
| oc.hu | 141 |
| ingatlanbazar.hu | 100 |
| dh.hu | 11 |

A `fetch`/`parse` pipeline időről időre újra feldolgoz már korábban látott
hirdetéseket (ha azok linkje többször is bekerül a letöltési sorba) —
emiatt **170 sor** 81, (portál, `property_id`) alapján duplikált hirdetés
több pillanatképét tartalmazza (ár és egyéb mezők azonosak, csak a
`scraped_at` különbözik). Ezeket a legfrissebb pillanatkép megtartásával
deduplikáljuk, így **1526 egyedi hirdetés** marad az elemzés alapja.

A `data/properties.csv` oszlopai (a `Property` DTO):

`url, portal, property_id, property_type, condition, title, price, currency,
area_sqm, rooms, location, city, lat, lon, scraped_at, source_file`

Az `property_type` és `condition` mezők portálonként eltérő elnevezéseket
egységesítenek (pl. `PropertyType` enum: `lakas`, `haz`, `sorhaz`, `telek`,
`nyaralo`, `beruhazas`). A `city` egy újabban hozzáadott mező: a scraper
portálonkénti logikája ezt is kinyeri (a szabad szöveges `location` mellett),
és a geokódolás fallback-forrásaként is szolgál, ha a teljes `location`-ra
nem ad találatot a geokódoló (ld. 2.2 és 3.2).

### 2.4 Leíró statisztikák és adatminőség

**Típus szerinti megoszlás** (deduplikált adaton):

| Típus | Darab |
|---|---|
| lakás | 698 |
| ház | 678 |
| telek | 80 |
| nyaraló | 49 |
| sorház | 20 |
| beruházás | 1 |

A `sorház` kategória a korábbi 1 elemről mára **20 elemesre** nőtt, tehát
érdemben kezelhető a modellezésben is; a `beruházás` kategória maradt
1 elemes — ez sem tanításra, sem kiértékelésre nem alkalmas, a
modellezésből kizárjuk.

**Hiányzó értékek** (a nyers, deduplikált adatkészleten):

| Oszlop | Hiányzó arány |
|---|---|
| `rooms` | 14,5 % |
| `title` | 2,4 % |
| `lat` / `lon` / `city` | 0 % |

A `rooms` hiánya nem véletlen: típusonként erősen eltér (`telek`-nél 100%,
`nyaraló`-nál 28,6%, `lakás`-nál 10,5%, `ház`-nál 8,0%) — ez logikus, egy
földterületnek nincs szobaszáma. A hiányzó arány a korábbi (477 soros)
adatkészlethez képest minden típusnál csökkent, valószínűleg mert az új
hirdetések (elsősorban jofogas.hu-ról) jellemzően pontosabban vannak
kitöltve. A koordináta immár **minden sorra** elérhető (korábban 3,6%
hiányzott) — ez annak köszönhető, hogy a geokódolás mára a `city` mezőre is
tud esni fallback-ként, ha a teljes `location`-ra nincs találat.

**Ár és terület eloszlása:** mindkettő továbbra is erősen jobbra elnyúló
eloszlású (pár nagyon drága/nagy ingatlan húzza el az átlagot), ami
log-transzformációt indokol:

| | `price` (HUF) | `area_sqm` (m²) |
|---|---|---|
| medián | 70 823 130 | 78 |
| átlag | 79 347 130 | 374,6 |
| szórás | 69 075 610 | 4 307,5 |
| max | 1 000 000 000 | 95 989 |

Az `area_sqm` rendkívül nagy szórását továbbra is a **telek** típusú
hirdetések okozzák (földterület m²-ben, ami nagyságrendekkel nagyobb
skálán mozog, mint egy lakás/ház alapterülete) — ez fontos modellezési
döntést indokol (ld. 4.2).

**Egy konkrét adatminőségi hiba** is előkerült feltárás közben: egy `oc.hu`
hirdetésnél (`H525602`) a `currency` mező `EUR`, miközben az ár nagyságrendje
(egy 55 m²-es budapesti lakás "86 126 910 EUR"-ért) egyértelműen azt jelzi,
hogy a valós pénznem HUF, és a portál GTM `dataLayer`-jéből valószínűleg egy
másik (ajánlott) hirdetés adata keveredett be. Mivel a helyes értéket nem
tudjuk megbízhatóan rekonstruálni, ezt az 1 sort kiszűrjük (1525 sor marad).
Egy **második, hasonló jellegű hiba** is előkerült a modellezés közben (ld.
4.3): egy `haz` típusú hirdetés ára **82 000 HUF** egy 141 m²-es ingatlanra
(≈580 HUF/m²) — ezt a kiugró-érték-jelölés automatikusan felismeri, de
mutatja, hogy a nyers adatban valószínűleg lehet még hasonló, egyedileg nem
azonosított hiba (ld. 5.2 korlátok).

**Földrajzi lefedettség:** a koordinátával rendelkező sorok aránya 100%
(1525/1525 a currency-szűrés után); a hirdetések mindössze **13,3%-a**
budapesti — ez jelentős csökkenés a korábbi 32,4%-hoz képest, mert az új
hirdetések nagy része a jofogas.hu-ról érkezett, és azon belül erősen
koncentrálódik néhány vidéki településre (elsősorban Debrecen és
Dunaújváros környékére — ld. 5.2 korlátok, ez torzíthatja a tanult
összefüggéseket).

---

## 3. Módszertan

### 3.1 Modellezési irány kiválasztása

Az EDA notebook (`01_eda_and_preprocessing.ipynb`) négy lehetséges irányt
vetett fel, és ezek életképességét vizsgálta a jelenlegi adatmennyiséggel:

- **A) Regresszió** (ár/ár-m² becslés) — minden sorra van `price`/`area_sqm`,
  a log-transzformáció láthatóan segít a torzított eloszláson → **ez a
  választott fő irány**.
- **B) Osztályozás** (`property_type` predikció) — csak kiegészítő irányként
  életképes (2 kategória 1 elemes).
- **C) Klaszterezés** (földrajzi árszegmensek) — a koordináta-hiány miatt
  korlátozott, csak a koordinátával rendelkező részhalmazon futna.
- **D) Anomália-detektálás** (alul-/túlárazott hirdetések) — csak egy kész
  regressziós modell reziduumaira épülhet, ezért ez egy **tervezett
  következő lépés**, jelen dokumentáció ezt nem tartalmazza.

### 3.2 Előfeldolgozás

Az előfeldolgozás (`01_eda_and_preprocessing.ipynb` 4. pontja) lépései:

1. **Duplikátumok eldobása** — a `(portal, property_id)` páronként
   ismételten letöltött/feldolgozott hirdetéseknél (170 sor, 81 egyedi
   hirdetés) a legfrissebb `scraped_at` pillanatkép megtartása, a korábbiak
   eldobása (ld. 2.3).
2. **Konstans/hibás oszlopok kezelése** — a `currency` oszlop (mindig HUF a
   tisztított adatban) elhagyása; az 1 db `EUR`-ra jelölt, adatminőségi hibás
   sor kiszűrése (ld. 2.4).
3. **`rooms` hiányzó érték kezelése** — típuson belüli mediánnal pótolva
   (egy ház és egy lakás tipikus szobaszáma eltér), `telek`-nél logikus `0`,
   és egy `rooms_missing` jelzőoszlop megtartása, hogy a modell
   megkülönböztethesse a pótolt és az eredeti értéket.
4. **`city` feldolgozása** — a korábbi verzióban a szabad szöveges
   `location` mezőből, portál-specifikus string-logikával (pl. a jofogas.hu
   fordított sorrendben adja meg a település/megye részeket) kellett
   kinyerni a települést; mivel a scraper mára egy dedikált, egységesebb
   `city` mezőt is szolgáltat, ebből nyerjük ki `is_budapest` (bináris) és
   `settlement` (település) jellemzőket. Emellett a budapesti
   hirdetésekből kinyerjük a kerületet (`bp_district`) római és arab
   számjegyes formátumból is (a `city` Budapesten belül portálonként
   eltérő formátumú lehet).
5. **Koordináta-alapú jellemző** — a koordináta-lefedettség mára majdnem
   teljes (a `city`-re eső geokódolási fallback miatt), a hiány
   lehetőségét mégsem imputáljuk mesterséges koordinátával (egy kitalált
   koordináta rosszabb lenne, mint a hiány jelzése), helyette egy
   `has_coords` flaget és egy folytonos `dist_to_bp_km` (haversine-távolság
   Budapest centrumától) jellemzőt számolunk ott, ahol van koordináta.
6. **Transzformációk** — `log_price`, `log_area_sqm` (log1p), valamint
   alternatív célváltozóként `price_per_sqm` és `log_price_per_sqm`.
7. **Kiugró értékek jelölése** — az 1./99. percentilis alapján `price`,
   `area_sqm` és `price_per_sqm` oszlopokon (nem automatikus eldobás, a
   döntést a modellezési notebookra hagyva).
8. **Kategorikus kódolás** — `property_type` és a top-N település
   (`settlement_grouped`, a ritka településeket `"egyeb"` csoportba sorolva)
   one-hot kódolása. A `portal` oszlopot megtartjuk informatívnak, de
   szándékosan **nem** kódoljuk be jellemzőként (adatforrás-zajt vinne a
   modellbe).

Az eredmény a `data/properties_preprocessed.csv` (1525 sor, 45 oszlop), ez a
modellezés bemenete.

### 3.3 Modellek és kísérleti terv

A `02_modeling.ipynb` notebookban három modellt hasonlítunk össze:

- **Lineáris regresszió** — egyszerű, interpretálható baseline.
- **Ridge regresszió** — a lineáris regresszió regularizált változata, a
  kollineáris jellemzők (pl. one-hot oszlopok) miatti instabilitás
  csökkentésére. Az 1-3. kísérletben fix α = 1,0-val fut, a 4. kísérletben
  az α-t is hangoljuk.
- **Random Forest regresszió** — nemlineáris kapcsolatok és jellemző-
  kölcsönhatások kezelésére. Az 1-3. kísérletben fix hiperparaméterekkel
  (300 fa, max. mélység 6) fut, a 4. kísérletben
  `sklearn.model_selection.RandomizedSearchCV`-vel hangoljuk a
  hiperparamétereit (`n_estimators`, `max_depth`, `min_samples_leaf`,
  `min_samples_split`, `max_features`), mert kis/közepes adatmennyiségnél a
  fix beállítás könnyen alul- vagy túlbonyolított lehet.

Minden kísérletnél **80/20 train/test felosztást** használunk (`random_state`
rögzítve a reprodukálhatóságért), a train részen **5-fold keresztvalidációt**
az átlagos hiba és annak szórásának becslésére (a `RandomizedSearchCV` is
ugyanezt az 5-fold keresztvalidációt, `neg_mean_absolute_error` pontszámmal
használja a kereséshez), a végső kiértékelés pedig a sosem látott
teszthalmazon történik. A lineáris modelleknél a jellemzőket
`StandardScaler`-rel skálázzuk.

Négy, egymásra épülő kísérletet futtatunk (indoklás a 4. és 5. fejezetben):

1. **Teljes adathalmaz** (az 1-elemű `beruhazas` típus kivételével, n=1524),
   fix hiperparaméterekkel.
2. **Szűkített adathalmaz**, csak `ház` + `lakás` (n=1375) — homogénebb
   `area_sqm` jelentés és piaci logika.
3. **Kiugró értékek nélkül**, a 2. kísérlet adatain (n=1344).
4. **Hiperparaméter-keresés** `RandomizedSearchCV`-vel, a 3. kísérlet
   train/test felosztásán, Random Forestre és Ridge-re.

---

## 4. Kísérletek és eredmények

### 4.1 Metrikák

Minden kísérletnél a következő metrikákat jelentjük:

- **MAE / RMSE (log skálán)** — mivel a modell a `log_price`-ot becsli,
  ezek közvetlenül a tanítási célt mérik.
- **R²** (log skálán) — a megmagyarázott varianca aránya.
- **MAE visszatranszformálva HUF-ra** (`expm1`) — könnyebben interpretálható
  abszolút hiba forintban.
- **MAPE (%)** — relatív hiba, ami jobban összemérhető különböző
  ártartományok között.

### 4.2 1. kísérlet — teljes adathalmaz

| Modell | CV MAE (log, train) | Teszt MAE (log) | Teszt RMSE (log) | Teszt R² | Teszt MAE (HUF) | Teszt MAPE |
|---|---|---|---|---|---|---|
| Lineáris regresszió | 0,401 ± 0,019 | 0,375 | 0,486 | 0,591 | 25 006 045 | 43,1 % |
| Ridge (α=1,0) | 0,401 ± 0,019 | 0,375 | 0,486 | 0,591 | 25 024 844 | 43,1 % |
| **Random Forest** | **0,284 ± 0,013** | **0,261** | **0,390** | **0,737** | **18 738 184** | **30,3 %** |

A Random Forest minden metrikán jobb, mint a lineáris modellek — ez arra
utal, hogy az ár–jellemző kapcsolat nem tisztán lineáris. A bővült
adatkészleten a teljes-adathalmazos kísérlet hibája (MAPE ≈ 30%) már
viszonylag alacsony, de a `telek` és `nyaraló` kategóriák továbbra is más
piaci logikát követnek, és az `area_sqm` jelentése is eltér (telekméret
vs. lakóterület) — ezt teszteli a 2. kísérlet.

### 4.3 2. kísérlet — csak `ház` és `lakás`

| Modell | CV MAE (log, train) | Teszt MAE (log) | Teszt RMSE (log) | Teszt R² | Teszt MAE (HUF) | Teszt MAPE |
|---|---|---|---|---|---|---|
| Lineáris regresszió | 0,375 ± 0,024 | 0,419 | 0,670 | 0,304 | 28 653 183 | 437,6 % |
| Ridge (α=1,0) | 0,375 ± 0,024 | 0,419 | 0,670 | 0,304 | 28 641 462 | 437,4 % |
| **Random Forest** | **0,249 ± 0,017** | **0,294** | **0,583** | **0,474** | **20 791 172** | **458,9 %** |

Meglepő, de magyarázható eredmény: ezen a szűkebb részhalmazon **minden**
modell metrikája rosszabb, mint az 1. kísérletben — ez nem azt jelenti,
hogy a szűkítés rossz ötlet, hanem hogy a teszthalmazba (a véletlenszerű
80/20 felosztás miatt) belekerült egy súlyosan hibás sor: egy `haz` típusú
hirdetés ára **82 000 HUF** egy 141 m²-es ingatlanra (≈580 HUF/m², ami
nyilvánvalóan adatminőségi hiba, hasonlóan az EUR/HUF esethez, ld. 2.4).
Egyetlen ilyen extrém, irreálisan alacsony valós ár a MAPE-et (relatív
hiba) és az R²-t is drasztikusan megronthatja egy ~275 soros
teszthalmazon. Ez pontosan azt indokolja, amire a kiugró-érték-jelölés
készült — ld. 3. kísérlet.

### 4.4 3. kísérlet — kiugró értékek nélkül

| Modell | CV MAE (log, train) | Teszt MAE (log) | Teszt RMSE (log) | Teszt R² | Teszt MAE (HUF) | Teszt MAPE |
|---|---|---|---|---|---|---|
| Lineáris regresszió | 0,364 ± 0,018 | 0,379 | 0,498 | 0,469 | 26 439 019 | 45,3 % |
| Ridge (α=1,0) | 0,364 ± 0,017 | 0,379 | 0,498 | 0,469 | 26 432 280 | 45,3 % |
| **Random Forest** | **0,237 ± 0,012** | **0,250** | **0,346** | **0,743** | **18 945 315** | **26,2 %** |

A kiugró értékek (köztük a fent említett 82 000 HUF-os hibás sor)
kihagyása a Random Forest eredményét tovább javítja, és a 2. kísérletben
látott torzítást is megszünteti (MAPE 458,9% → 26,2%; R² 0,474 → 0,743). A
**lineáris** modell MAPE-je is sokat javul (437,6% → 45,3%), de messze nem
éri el a Random Forest szintjét — ez megerősíti, hogy a fennmaradó hiba nem
csak kiugró értékekből, hanem a modell linearitási korlátjából is adódik.

### 4.5 4. kísérlet — hiperparaméter-keresés `RandomizedSearchCV`-vel

A 3. kísérlet train/test felosztásán, `RandomizedSearchCV`-vel (5-fold CV,
`neg_mean_absolute_error` pontszám, 50 ill. 30 mintavételezett
paraméter-kombináció) hangoltuk a Random Forest és a Ridge
hiperparamétereit, és összevetettük a fix beállítású eredményekkel:

| Modell | Teszt MAE (log) | Teszt RMSE (log) | Teszt R² | Teszt MAE (HUF) | Teszt MAPE |
|---|---|---|---|---|---|
| Random Forest (fix: 300 fa, max. mélység 6) | 0,250 | 0,346 | 0,743 | 18 945 315 | 26,2 % |
| **Random Forest (RandomizedSearchCV)** | **0,216** | **0,322** | **0,778** | **16 630 065** | **22,2 %** |
| Ridge (fix: α=1,0) | 0,379 | 0,498 | 0,469 | 26 432 280 | 45,3 % |
| Ridge (RandomizedSearchCV α) | 0,379 | 0,498 | 0,469 | 26 439 010 | 45,3 % |

A keresés a Random Forestre `n_estimators≈559`, `max_depth≈14`,
`min_samples_leaf=2`, `min_samples_split=2`, `max_features≈0,96`
paramétereket találta a legjobbnak (CV MAE log ≈ 0,211 a train-részen) — ez
egy jóval nagyobb/komplexebb erdő, mint az eredeti fix beállítás (300 fa,
max. mélység 6), és a teszthalmazon is érdemben jobb eredményt ad (R² 0,743
→ 0,778, MAPE 26,2% → 22,2%). Ez arra utal, hogy a bővült (~1300+ soros)
adatkészlet elbír egy komplexebb modellt is túltanulás nélkül — a korábbi,
kisebb adatkészleten (n≈426) választott fix hiperparaméterek már nem
optimálisak.

A **Ridge**-nél a hangolt α (≈0,0013, azaz gyakorlatilag minimális
regularizáció) a keresztvalidáción jobb CV MAE-t ad, de a teszthalmazon
nem változik érdemben az eredmény — ez arra utal, hogy a lineáris modell
hibája itt nem a regularizáció erősségén, hanem magán a linearitási
feltételezésen bukik el (ld. 4.7-4.8).

A továbbiakban (feature-fontosság, hibaanalízis) a hangolt Random
Forest-et tekintjük a **végső modellnek**.

### 4.6 Összehasonlító táblázat (a kísérletek áttekintése)

| Kísérlet | n | Teszt R² (RF) | Teszt MAPE (RF) |
|---|---|---|---|
| 1. Teljes adathalmaz | 1524 | 0,737 | 30,3 % |
| 2. Ház + lakás | 1375 | 0,474 | 458,9 % (1 hibás sor miatt) |
| 3. Ház + lakás, outlier nélkül | 1344 | 0,743 | 26,2 % |
| **4. Ház + lakás, outlier nélkül, hangolt RF** | 1344 | **0,778** | **22,2 %** |

A legjobb beállítás (4. kísérlet, `RandomizedSearchCV`-vel hangolt Random
Forest) a végleges modellünk.

### 4.7 Jellemző-fontosság

A végső (hangolt) Random Forest jellemző-fontosság szerinti sorrendje:

| Jellemző | Fontosság |
|---|---|
| `dist_to_bp_km` | 0,657 |
| `log_area_sqm` | 0,236 |
| `rooms` | 0,061 |
| `type_lakas` | 0,024 |
| `is_budapest` | 0,013 |
| `rooms_missing` | 0,010 |
| `has_coords` | ≈0,000 |

A **Budapest-távolság** és az **alapterület** adja a predikció nagy részét
— ez megfelel a hétköznapi intuíciónak (méret + helyszín dominálja az árat).
Érdekes, hogy a folytonos `dist_to_bp_km` jóval informatívabb, mint a
bináris `is_budapest`: a budapesti kerületek és az agglomeráció közötti
finomabb árkülönbségeket csak a folytonos távolság tudja kifejezni. A
`has_coords` fontossága a koordináták majdnem teljes lefedettsége miatt
mára gyakorlatilag nulla (alig van olyan sor, ahol a flag informatív
lenne).

### 4.8 Hibaanalízis

A legnagyobb abszolút hibájú teszt-előrejelzéseket megvizsgálva a végső
modellnél is azt látjuk, hogy a legnagyobb hibák **drága (150-270 millió
HUF) ingatlanoknál** jelentkeznek, ahol a modell jellemzően **alulbecsüli**
az árat — ez arra utal, hogy a prémium szegmensben a terület és a Budapest-
távolság önmagában nem magyarázza meg az árat (pl. presztízs-tényezők,
felújítottság, kilátás stb., amiket a jelenlegi adatkészlet nem tartalmaz).
Emellett a 4.3-ban bemutatott eset (egyetlen irreálisan alacsony árú sor,
amely egy ~275 soros teszthalmazon 400%+ pontot adott a MAPE-hez) jó
illusztráció arra, hogy **az aggregált metrikák mellett mindig érdemes
megnézni a legnagyobb egyedi hibákat is** — egy aggregált szám (pl. MAPE)
önmagában elfedheti, hogy a hiba nagy részét 1-2 adatminőségi probléma
okozza, nem a modell gyengesége.

---

## 5. Elemzés

### 5.1 Az eredmények értelmezése

A legjobb modell (**`RandomizedSearchCV`-vel hangolt Random Forest,
ház+lakás, kiugró értékek nélkül**) a teszthalmazon **R² ≈ 0,78**,
**átlagos relatív hiba (MAPE) ≈ 22%** eredményt ad. Ez azt jelenti, hogy a
modell az árváltozás nagy részét (kb. 78%-át) meg tudja magyarázni
mindössze két jellemző (terület, Budapest-távolság) és néhány kiegészítő
jellemző (szobaszám, típus) alapján — ami jó kiindulópont, de **egy
átlagos hirdetésnél is ~22%-os relatív eltérésre** kell számítani a
becslés és a valós ár között, ami egy valós használati esetben (pl.
árazási támogatás) még nem elég pontos.

A **modellek közötti különbség** (Random Forest > Ridge ≈ Lineáris
regresszió minden kísérletben) azt mutatja, hogy az ár és a jellemzők
kapcsolata **nemlineáris és/vagy jellemző-kölcsönhatásokat tartalmaz**
(pl. a terület hatása valószínűleg eltér Budapesten és vidéken) — ezt egy
fastruktúra-alapú modell természetesen kezeli, egy lineáris modell csak
explicit interakciós jellemzőkkel tudná. Ezt megerősíti az is, hogy a
`RandomizedSearchCV` a Ridge α-ját a keresztvalidáción javítani tudta, a
teszthalmazon viszont alig változott az eredmény — a lineáris modell
korlátja nem a regularizáció erőssége, hanem a linearitás feltételezése.

A **részhalmazra szűkítés** (1. → 2. kísérlet), a **kiugró értékek
kezelése** (2. → 3. kísérlet) és a **hiperparaméter-hangolás**
(3. → 4. kísérlet) mindegyike érdemben javított, de nem egyenlő mértékben:
a kiugró értékek kezelése hatása volt a legnagyobb (ld. a 2. kísérlet
torzítását, 4.3), ezt követte a hiperparaméter-hangolás (R² 0,743 → 0,778),
a hiperparaméter-választás pedig a bővült adatkészleten már önmagában is
számottevő (+0,035 R², -4 pont MAPE) javulást hozott — ez arra tanít, hogy
nagyobb adatmennyiségnél a **modell komplexitásának hangolása** is egyre
inkább megtérülő lépés, nem csak az adattisztítás.

### 5.2 A modell korlátai

- **Mintaszám-torzítás a portálok között.** Az adatkészlet 72,6%-a
  jofogas.hu-ról származik, és ezen belül erősen koncentrálódik néhány
  településre (Debrecen: a teljes adat ~28%-a, Dunaújváros ~7%) — ez nem
  egy országosan egyenletes minta, hanem a seed-lista/keresési
  beállítások szerint torzított. A budapesti arány emiatt a korábbi
  32,4%-ról 13,3%-ra csökkent, miközben ez nem feltétlenül tükrözi a
  valós piaci arányokat. Ha egy adott portál/település hirdetői
  rendszeresen más áron hirdetnek, ez torzíthatja a tanult
  összefüggéseket, és a modell kevésbé jól generalizál más
  régiókra/portálokra.
- **Néhány, egyedileg nem azonosított adatminőségi hiba lehet még a
  nyers adatban.** Két konkrét esetet is találtunk (az EUR/HUF eset és a
  82 000 HUF-os ház, ld. 2.4 és 4.3), mindkettőt a kiugró-érték-jelölés
  vagy a pénznem-ellenőrzés fogta meg — de ez nem garantálja, hogy minden
  hasonló hiba ki van szűrve, csak hogy a szélsőséges esetek nagy része.
- **Hiányzó, árat befolyásoló jellemzők.** A `condition` (állapot) oszlop
  jelenleg egyáltalán nincs a modellben, noha vélhetően erős ár-jelzés.
  Az emeletszám, energetikai besorolás, felújítás éve, kilátás stb. nem
  része az adatkészletnek.
- **Helyszín-reprezentáció egyszerűsége.** A `dist_to_bp_km` csak a
  Budapest-közelséget fejezi ki; két, Budapesttől egyformán távoli, de
  eltérő árszínvonalú település (pl. egy tóparti üdülőövezet vs. egy
  hátrányos helyzetű vidéki település) között nem tud különbséget tenni.
- **`area_sqm` heterogenitása a teljes adathalmazon.** Ahogy a 4.2-4.3
  pontban bemutattuk, a `telek` típusnál a m² jelentése (földterület)
  nem ugyanaz, mint `ház`/`lakás`-nál (lakóterület) — ezért a végső modell
  tudatosan csak ház+lakás hirdetésekre vonatkozik, **telekre vagy
  üdülőre nem alkalmazható** anélkül, hogy újra meg ne tanítanánk rájuk.
- **Egyetlen időpontbeli pillanatkép.** A hirdetések `scraped_at` ideje
  szűk (kb. 2 hetes) időintervallumra esik, így a modell nem tudja (és
  nem is próbálja) kezelni az árak időbeli alakulását/trendjét.

### 5.3 Lehetséges fejlesztési irányok

1. **Rétegzettebb/kiegyensúlyozottabb adatgyűjtés** — a `fetch`/`parse`
   pipeline folyamatosan futtatható, de érdemes lenne a seed-listát úgy
   alakítani, hogy a portálok és települések aránya ne torzuljon annyira
   egy-egy forrás felé (ld. 5.2) — ez stabilabb, jobban generalizáló
   modellt adna, és a kis mintaszámú típusok (telek, nyaraló, sorház) is
   modellezhetővé válhatnak önállóan.
2. **`condition` és egyéb szöveges jellemzők bevonása** — jelenleg
   kihasználatlan információ.
3. **Településszintű ár-jellemző** (pl. target encoding: a település
   átlagos `price_per_sqm`-je mint jellemző) a `dist_to_bp_km` finomítására.
4. **Szisztematikusabb adatminőség-ellenőrzés** — a jelenlegi kiugró-érték-
   jelölés (1./99. percentilis) és a pénznem-ellenőrzés csak a
   legszélsőségesebb hibákat fogja meg (ld. 4.3, 5.2); érdemes lenne pl.
   ár/m² tartomány-alapú, típusonkénti szabályokat is bevezetni.
5. **Gradiens boosting modellek** (pl. XGBoost/LightGBM) kipróbálása —
   jellemzően jobban teljesítenek, mint a Random Forest, és a
   `RandomizedSearchCV`-s hangolási keretrendszer (ld. 4.5) közvetlenül
   újrahasználható lenne rájuk is.
6. **B) Osztályozás** (ingatlantípus predikció) és **C) Klaszterezés**
   (földrajzi árszegmensek) kiegészítő irányként, amint elég adat áll
   rendelkezésre minden típushoz / településhez.
7. **D) Anomália-detektálás** — a végső regressziós modell reziduumai
   alapján alul-/túlárazott hirdetések jelölése (az EDA notebookban
   tervezett, de a jelen modellezéshez képest is csak ez után
   értelmezhető lépés).

---

## 6. Következtetések

A projekt egy **teljes, reprodukálható adattudományi pipeline-t** épített fel
5 magyar ingatlanportál hirdetéseinek gyűjtésére, egységesítésére,
geokódolására és ár-regressziós modellezésére. A folyamat minden lépése
(adatgyűjtés, EDA, előfeldolgozás, modellezés) dokumentált és
újrafuttatható notebookokban/CLI parancsokban él, ami lehetővé teszi, hogy a
bővülő adatkészlettel a modell is folyamatosan újratanítható/javítható
legyen.

A modellezési kísérletek azt mutatták, hogy:

- egy **Random Forest** modell konzisztensen felülmúlja a lineáris/Ridge
  regressziót, ami nemlineáris ár–jellemző kapcsolatra utal;
- az **adattisztítási döntések** (homogén részhalmazra szűkítés, kiugró
  értékek kezelése) nagy hatással voltak az eredményre — egyetlen hibás
  sor önmagában 400 pontnál is nagyobb MAPE-torzítást okozott egy ~275
  soros teszthalmazon (ld. 4.3);
- a **`RandomizedSearchCV`-vel végzett hiperparaméter-keresés** is
  érdemben javított a bővült adatkészleten (R² 0,743 → 0,778, MAPE 26,2%
  → 22,2%) — a nagyobb adatmennyiség egy komplexebb Random Forestet is
  elbír túltanulás nélkül;
- a legjobb elért eredmény (**R² ≈ 0,78, MAPE ≈ 22%**, ház+lakás
  hirdetéseken, hangolt Random Forest) egy **tartható, de egy valós
  ár-becslő eszközhöz még nem elég pontos** baseline-t ad;
- a **terület** és a **Budapest-távolság** a két domináns jellemző, ami
  megerősíti az ingatlanpiaci "méret + helyszín" intuíciót, de jelzi azt is,
  hogy a modell jelenleg nem használ ki olyan, valószínűleg fontos
  jellemzőket, mint az ingatlan állapota;
- az adatkészlet bővülésével egy **új korlát** is felszínre került: a
  minta mára erősen torzult egy portál (jofogas.hu) és néhány vidéki
  település (elsősorban Debrecen) felé, ami óvatosságra int a modell
  általánosíthatóságával kapcsolatban (ld. 5.2).

A legfontosabb tanulság a következő fázisra: **a modell pontosságának
javítása részben algoritmus-/hiperparaméter-kérdés (ezt a
`RandomizedSearchCV`-s kísérlet is igazolja), de legalább annyira adat-
kérdés is — mind mennyiségben, mind a mintavétel egyenletességében és a
jellemzők körében.**

---

## Függelék — reprodukálhatóság

A dokumentációban bemutatott eredmények a következő, a repóban elérhető
artifaktumokból reprodukálhatók:

- **Adatgyűjtés**: `python3 -m scraper fetch/parse/geocode` (lásd `README.md`).
- **EDA és előfeldolgozás**: `notebooks/01_eda_and_preprocessing.ipynb`
  → `data/properties_preprocessed.csv`.
- **Modellezés és kiértékelés**: `notebooks/02_modeling.ipynb` (a 4. fejezet
  összes táblázata és ábrája ebből a notebookból származik).

Minden véletlenszám-generálást használó lépés (train/test split,
keresztvalidáció, Random Forest, `RandomizedSearchCV`) rögzített
`random_state=42` mellett fut, a futások így determinisztikusan
reprodukálhatók (feltéve, hogy a `data/properties.csv` nem változik a két
futás között — a `data/` mappa gitignore-olt, bővülő nyers adat, így a
pontos számok a jelen dokumentumban egy adott pillanatképre vonatkoznak).
