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
korlátokat a 6. (Elemzés) fejezetben részletezzük.

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

A dokumentáció írásakor a nyers adatkészlet **477 hirdetést** tartalmaz,
portálonkénti megoszlásban:

| Portál | Hirdetések száma |
|---|---|
| jofogas.hu | 129 |
| oc.hu | 127 |
| zenga.hu | 110 |
| ingatlanbazar.hu | 100 |
| dh.hu | 11 |

A `data/properties.csv` oszlopai (a `Property` DTO):

`url, portal, property_id, property_type, condition, title, price, currency,
area_sqm, rooms, location, lat, lon, scraped_at, source_file`

Az `property_type` és `condition` mezők portálonként eltérő elnevezéseket
egységesítenek (pl. `PropertyType` enum: `lakas`, `haz`, `sorhaz`, `telek`,
`nyaralo`, `beruhazas`).

### 2.4 Leíró statisztikák és adatminőség

**Típus szerinti megoszlás:**

| Típus | Darab |
|---|---|
| ház | 232 |
| lakás | 204 |
| nyaraló | 22 |
| telek | 17 |
| sorház | 1 |
| beruházás | 1 |

A `sorház` és `beruházás` kategóriák 1 elemesek — ezek sem tanításra, sem
kiértékelésre nem alkalmasak, a modellezésből kizárjuk őket.

**Hiányzó értékek** (a nyers adatkészleten):

| Oszlop | Hiányzó arány |
|---|---|
| `rooms` | 30,4 % |
| `title` | 7,5 % |
| `lat` / `lon` | 3,6 % |

A `rooms` hiánya nem véletlen: típusonként erősen eltér (`telek`-nél 100%,
`nyaraló`-nál 63,6%, `ház`-nál 22,8%, `lakás`-nál 29,4%) — ez logikus, egy
földterületnek nincs szobaszáma, és a hirdetők kevésbé pontosan adják meg
üdülőknél. A koordináta hiánya portálonként eltérő (`dh.hu`: 27,3%, `oc.hu`:
9,4%, `zenga.hu`: 1,8%, a többi portálnál 0%) — a `dh.hu` API válaszában a
cím néhány esetben kevésbé geokódolható formátumú.

**Ár és terület eloszlása:** mindkettő erősen jobbra elnyúló eloszlású
(pár nagyon drága/nagy ingatlan húzza el az átlagot), ami log-transzformációt
indokol:

| | `price` (HUF) | `area_sqm` (m²) |
|---|---|---|
| medián | 75 000 000 | 80 |
| átlag | 92 953 590 | 350,4 |
| szórás | 85 767 610 | 4 399,6 |
| max | 1 000 000 000 | 95 989 |

Az `area_sqm` rendkívül nagy szórását a **telek** típusú hirdetések
okozzák (földterület m²-ben, ami nagyságrendekkel nagyobb skálán mozog, mint
egy lakás/ház alapterülete) — ez fontos modellezési döntést indokol (ld. 4.2).

**Egy konkrét adatminőségi hiba** is előkerült feltárás közben: egy `oc.hu`
hirdetésnél (`H525602`) a `currency` mező `EUR`, miközben az ár nagyságrendje
(egy 55 m²-es budapesti lakás "86 126 910 EUR"-ért) egyértelműen azt jelzi,
hogy a valós pénznem HUF, és a portál GTM `dataLayer`-jéből valószínűleg egy
másik (ajánlott) hirdetés adata keveredett be. Mivel a helyes értéket nem
tudjuk megbízhatóan rekonstruálni, ezt az 1 sort kiszűrjük (476 sor marad).

**Földrajzi lefedettség:** a koordinátával rendelkező sorok aránya 96,4%
(460/477); a hirdetések 32,4%-a budapesti.

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

1. **Konstans/hibás oszlopok kezelése** — a `currency` oszlop (mindig HUF a
   tisztított adatban) elhagyása; az 1 db `EUR`-ra jelölt, adatminőségi hibás
   sor kiszűrése (ld. 2.4).
2. **`rooms` hiányzó érték kezelése** — típuson belüli mediánnal pótolva
   (egy ház és egy lakás tipikus szobaszáma eltér), `telek`-nél logikus `0`,
   és egy `rooms_missing` jelzőoszlop megtartása, hogy a modell
   megkülönböztethesse a pótolt és az eredeti értéket.
3. **`location` feldolgozása** — szabad szöveges mezőből két jellemző
   kinyerése: `is_budapest` (bináris) és `settlement` (település, portál-
   specifikus string-logikával, mivel pl. a jofogas.hu fordított sorrendben
   adja meg a település/megye részeket). Emellett a budapesti hirdetésekből
   kinyerjük a kerületet (`bp_district`) római és arab számjegyes formátumból
   is.
4. **Koordináta-alapú jellemző** — a hiányzó koordinátákat **nem**
   imputáljuk (egy kitalált koordináta rosszabb lenne, mint a hiány jelzése),
   helyette egy `has_coords` flaget és egy folytonos `dist_to_bp_km`
   (haversine-távolság Budapest centrumától) jellemzőt számolunk ott, ahol
   van koordináta.
5. **Transzformációk** — `log_price`, `log_area_sqm` (log1p), valamint
   alternatív célváltozóként `price_per_sqm` és `log_price_per_sqm`.
6. **Kiugró értékek jelölése** — az 1./99. percentilis alapján `price`,
   `area_sqm` és `price_per_sqm` oszlopokon (nem automatikus eldobás, a
   döntést a modellezési notebookra hagyva).
7. **Kategorikus kódolás** — `property_type` és a top-N település
   (`settlement_grouped`, a ritka településeket `"egyeb"` csoportba sorolva)
   one-hot kódolása. A `portal` oszlopot megtartjuk informatívnak, de
   szándékosan **nem** kódoljuk be jellemzőként (adatforrás-zajt vinne a
   modellbe).

Az eredmény a `data/properties_preprocessed.csv` (476 sor, 44 oszlop), ez a
modellezés bemenete.

### 3.3 Modellek és kísérleti terv

A `02_modeling.ipynb` notebookban három modellt hasonlítunk össze:

- **Lineáris regresszió** — egyszerű, interpretálható baseline.
- **Ridge regresszió** (α = 1,0) — a lineáris regresszió regularizált
  változata, a kollineáris jellemzők (pl. one-hot oszlopok) miatti
  instabilitás csökkentésére.
- **Random Forest regresszió** (300 fa, max. mélység 6) — nemlineáris
  kapcsolatok és jellemző-kölcsönhatások kezelésére, valamint mert kis
  adatmennyiségnél kevésbé hajlamos túltanulni, mint egy mélyebb fa vagy
  gradiens boosting.

Minden kísérletnél **80/20 train/test felosztást** használunk (`random_state`
rögzítve a reprodukálhatóságért), a train részen **5-fold keresztvalidációt**
az átlagos hiba és annak szórásának becslésére, a végső kiértékelés pedig a
sosem látott teszthalmazon történik. A lineáris modelleknél a jellemzőket
`StandardScaler`-rel skálázzuk.

Három, egymásra épülő kísérletet futtatunk (indoklás a 4. és 5. fejezetben):

1. **Teljes adathalmaz** (a 2 egy-elemű típus kivételével, n=474).
2. **Szűkített adathalmaz**, csak `ház` + `lakás` (n=435) — homogénebb
   `area_sqm` jelentés és piaci logika.
3. **Kiugró értékek nélkül**, a 2. kísérlet adatain (n=426).

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
| Lineáris regresszió | 0,395 ± 0,053 | 0,419 | 0,550 | 0,588 | 33 381 497 | 53,6 % |
| Ridge (α=1,0) | 0,395 ± 0,053 | 0,418 | 0,549 | 0,589 | 33 326 419 | 53,5 % |
| **Random Forest** | **0,381 ± 0,036** | **0,358** | **0,504** | **0,653** | **29 114 286** | **50,4 %** |

A Random Forest minden metrikán jobb, mint a lineáris modellek — ez arra
utal, hogy az ár–jellemző kapcsolat nem tisztán lineáris. A hiba azonban még
így is nagy (MAPE ≈ 50%): ennek egy feltételezett oka, hogy a `telek` és
`nyaraló` kategóriák más piaci logikát követnek, és az `area_sqm` jelentése
is eltér (telekméret vs. lakóterület) — ezt teszteli a 2. kísérlet.

### 4.3 2. kísérlet — csak `ház` és `lakás`

| Modell | CV MAE (log, train) | Teszt MAE (log) | Teszt RMSE (log) | Teszt R² | Teszt MAE (HUF) | Teszt MAPE |
|---|---|---|---|---|---|---|
| Lineáris regresszió | 0,402 ± 0,048 | 0,355 | 0,452 | 0,553 | 32 204 435 | 39,4 % |
| Ridge (α=1,0) | 0,402 ± 0,048 | 0,355 | 0,452 | 0,553 | 32 238 221 | 39,5 % |
| **Random Forest** | **0,372 ± 0,056** | **0,263** | **0,400** | **0,649** | **26 737 100** | **29,1 %** |

A homogénebb részhalmazra szűkítés minden modellnél javított: a Random
Forest teszt-MAPE-je közel a felére csökkent (50,4% → 29,1%). Ez megerősíti
a feltevést, hogy a `telek`/`nyaraló` hirdetések zajt vittek a modellbe.

### 4.4 3. kísérlet — kiugró értékek nélkül

| Modell | CV MAE (log, train) | Teszt MAE (log) | Teszt RMSE (log) | Teszt R² | Teszt MAE (HUF) | Teszt MAPE |
|---|---|---|---|---|---|---|
| Lineáris regresszió | 0,371 ± 0,021 | 0,363 | 0,470 | 0,460 | 32 302 663 | 38,7 % |
| Ridge (α=1,0) | 0,371 ± 0,021 | 0,363 | 0,470 | 0,460 | 32 284 382 | 38,7 % |
| **Random Forest** | **0,306 ± 0,036** | **0,249** | **0,339** | **0,719** | **21 339 129** | **27,2 %** |

A kiugró értékek kihagyása a Random Forest eredményét tovább javítja
(R² 0,649 → 0,719; MAPE 29,1% → 27,2%). Érdekesség, hogy a **lineáris**
modell R²-je viszont *csökken* (0,553 → 0,460) — ennek oka, hogy a kiugró
(nagyon drága vagy nagyon olcsó) ingatlanok éppen azok a pontok, amelyek a
lineáris illesztés varianciájának nagy részét magyarázták; ezek elhagyása
után a megmaradt, "átlagos" ingatlanok közötti finomabb árkülönbségeket a
lineáris modell nem tudja jól visszaadni, a Random Forest viszont igen.

### 4.5 Összehasonlító táblázat (Random Forest, a 3 kísérlet)

| Kísérlet | n | Teszt R² | Teszt MAPE |
|---|---|---|---|
| 1. Teljes adathalmaz | 474 | 0,653 | 50,4 % |
| 2. Ház + lakás | 435 | 0,649 | 29,1 % |
| **3. Ház + lakás, outlier nélkül** | 426 | **0,719** | **27,2 %** |

A legjobb beállítás (3. kísérlet, Random Forest) a végleges modellünk.

### 4.6 Jellemző-fontosság

A legjobb modell (3. kísérlet, Random Forest) jellemző-fontosság szerinti
sorrendje:

| Jellemző | Fontosság |
|---|---|
| `dist_to_bp_km` | 0,536 |
| `log_area_sqm` | 0,385 |
| `type_lakas` | 0,043 |
| `rooms` | 0,026 |
| `rooms_missing` | 0,005 |
| `is_budapest` | 0,005 |
| `has_coords` | 0,0003 |

A **Budapest-távolság** és az **alapterület** adja a predikció nagy részét
— ez megfelel a hétköznapi intuíciónak (méret + helyszín dominálja az árat).
Érdekes, hogy a folytonos `dist_to_bp_km` jóval informatívabb, mint a
bináris `is_budapest`: a budapesti kerületek és az agglomeráció közötti
finomabb árkülönbségeket csak a folytonos távolság tudja kifejezni.

### 4.7 Hibaanalízis

A legnagyobb abszolút hibájú teszt-előrejelzéseket megvizsgálva (3. kísérlet,
Random Forest) azt látjuk, hogy a legnagyobb hibák **drága (150-280 millió
HUF) ingatlanoknál** jelentkeznek, ahol a modell jellemzően **alulbecsüli**
az árat — ez arra utal, hogy a prémium szegmensben a terület és a Budapest-
távolság önmagában nem magyarázza meg az árat (pl. presztízs-tényezők,
felújítottság, kilátás stb., amiket a jelenlegi adatkészlet nem tartalmaz).

---

## 5. Elemzés

### 5.1 Az eredmények értelmezése

A legjobb modell (**Random Forest, ház+lakás, kiugró értékek nélkül**) a
teszthalmazon **R² ≈ 0,72**, **átlagos relatív hiba (MAPE) ≈ 27%**
eredményt ad. Ez azt jelenti, hogy a modell az árváltozás nagy részét
(kb. 72%-át) meg tudja magyarázni mindössze két jellemző (terület,
Budapest-távolság) és néhány kiegészítő jellemző (szobaszám, típus)
alapján — ami jó kiindulópont, de **egy átlagos hirdetésnél is ~27%-os
relatív eltérésre** kell számítani a becslés és a valós ár között, ami
egy valós használati esetben (pl. árazási támogatás) még nem elég pontos.

A **modellek közötti különbség** (Random Forest > Ridge ≈ Lineáris
regresszió minden kísérletben) azt mutatja, hogy az ár és a jellemzők
kapcsolata **nemlineáris és/vagy jellemző-kölcsönhatásokat tartalmaz**
(pl. a terület hatása valószínűleg eltér Budapesten és vidéken) — ezt egy
fastruktúra-alapú modell természetesen kezeli, egy lineáris modell csak
explicit interakciós jellemzőkkel tudná.

A **részhalmazra szűkítés** (1. → 2. kísérlet) és a **kiugró értékek
kezelése** (2. → 3. kísérlet) hatása nagyobb volt, mint a modellváltás
hatása — ez arra tanít, hogy jelen adatmennyiségnél **az adattisztítási/
-szűkítési döntések legalább annyira fontosak, mint a modellválasztás**.

### 5.2 A modell korlátai

- **Kis adatmennyiség.** A végső modell n=426 soron tanul/tesztel (ebből
  csak 86 sor a teszthalmaz) — ez a 80/20 split mellett egy igen kicsi
  teszthalmaz, a metrikák (különösen a kísérletek közötti kis különbségek)
  bizonytalansága nagy. A keresztvalidációs szórás (CV MAE std) is ezt
  jelzi: a Random Forest-nél 0,036-0,057 közötti, ami a 0,25-0,38-as
  átlagos hibához képest nem elhanyagolható.
- **Hiányzó, árat befolyásoló jellemzők.** A `condition` (állapot) oszlop
  jelenleg egyáltalán nincs a modellben, noha vélhetően erős ár-jelzés.
  Az emeletszám, energetikai besorolás, felújítás éve, kilátás stb. nem
  része az adatkészletnek.
- **Helyszín-reprezentáció egyszerűsége.** A `dist_to_bp_km` csak a
  Budapest-közelséget fejezi ki; két, Budapesttől egyformán távoli, de
  eltérő árszínvonalú település (pl. egy tóparti üdülőövezet vs. egy
  hátrányos helyzetű vidéki település) között nem tud különbséget tenni.
- **Adatforrás-torzítás.** Az 5 portál eltérő arányban van jelen
  (jofogas.hu és oc.hu együtt az adat ~54%-a, dh.hu csak 11 sor) — ha egy
  portál hirdetői rendszeresen más áron/más régiókban hirdetnek, ez
  torzíthatja a tanult összefüggéseket.
- **`area_sqm` heterogenitása a teljes adathalmazon.** Ahogy a 4.2-4.3
  pontban bemutattuk, a `telek` típusnál a m² jelentése (földterület)
  nem ugyanaz, mint `ház`/`lakás`-nál (lakóterület) — ezért a végső modell
  tudatosan csak ház+lakás hirdetésekre vonatkozik, **telekre vagy
  üdülőre nem alkalmazható** anélkül, hogy újra meg ne tanítanánk rájuk.
- **Egyetlen időpontbeli pillanatkép.** A hirdetések `scraped_at` ideje
  szűk időintervallumra esik, így a modell nem tudja (és nem is próbálja)
  kezelni az árak időbeli alakulását/trendjét.

### 5.3 Lehetséges fejlesztési irányok

1. **Több adat gyűjtése** — a `fetch`/`parse` pipeline folyamatosan
   futtatható, több száz/ezer hirdetésnél stabilabb, megbízhatóbb modell
   várható, és a kis mintaszámú típusok (telek, nyaraló) is modellezhetővé
   válhatnak önállóan.
2. **`condition` és egyéb szöveges jellemzők bevonása** — jelenleg
   kihasználatlan információ.
3. **Településszintű ár-jellemző** (pl. target encoding: a település
   átlagos `price_per_sqm`-je mint jellemző) a `dist_to_bp_km` finomítására.
4. **Gradiens boosting modellek** (pl. XGBoost/LightGBM) kipróbálása —
   jellemzően jobban teljesítenek, mint a Random Forest, bár kis
   adatmennyiségnél a túltanulás kockázata nagyobb, ezért alapos
   keresztvalidáció/regularizáció szükséges.
5. **B) Osztályozás** (ingatlantípus predikció) és **C) Klaszterezés**
   (földrajzi árszegmensek) kiegészítő irányként, amint elég adat áll
   rendelkezésre minden típushoz / településhez.
6. **D) Anomália-detektálás** — a végső regressziós modell reziduumai
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
  értékek kezelése) nagyobb hatással voltak az eredményre, mint a
  modellválasztás;
- a legjobb elért eredmény (**R² ≈ 0,72, MAPE ≈ 27%**, ház+lakás
  hirdetéseken) egy **tartható, de egy valós ár-becslő eszközhöz még nem
  elég pontos** baseline-t ad;
- a **terület** és a **Budapest-távolság** a két dominás jellemző, ami
  megerősíti az ingatlanpiaci "méret + helyszín" intuíciót, de jelzi azt is,
  hogy a modell jelenleg nem használ ki olyan, valószínűleg fontos
  jellemzőket, mint az ingatlan állapota.

A legfontosabb tanulság a következő fázisra: **a modell pontosságának
javítása jelenleg inkább adat- (mennyiség, jellemzők) kérdés, mint
algoritmus-választási kérdés.**

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
keresztvalidáció, Random Forest) rögzített `random_state=42` mellett fut, a
futások így determinisztikusan reprodukálhatók.
