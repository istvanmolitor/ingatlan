# Prezentáció vázlat — 10 perc

*Alapja: `project_dokumentacio.md`. Irányadó időzítés, dia-szám rugalmasan
igazítható; a cél kb. 11-12 dia, hogy diánként ~1 perc jusson.*

---

## 1. dia — Cím (0:00–0:30)

- Projekt címe: "Magyar ingatlanhirdetések ár-becslése"
- Előadó neve, dátum
- Egy mondat: "Hogyan becsülhető egy ingatlan ára 5 portálról gyűjtött
  hirdetések alapján?"

## 2. dia — Probléma és motiváció (0:30–1:30)

- Az ingatlanárak nyilvánosak, de **szétszórtan, portálonként eltérő
  formátumban** érhetők el — nincs egységes, tanításra alkalmas adatkészlet.
- Cél: regressziós modell, amely terület/szobaszám/típus/helyszín alapján
  becsüli az árat.
- Keretezés: ez egy **end-to-end pipeline** demó is (gyűjtés → modellezés),
  nem csak egy modellezési feladat.

*Beszélőpont:* emeld ki, hogy a feladat nem csak "van egy CSV, futtassunk rá
sklearn-t" típusú, hanem a nyers weboldalaktól indul, és az adat időközben
**háromszorozódott** (477 → 1615 nyers sor) — a notebookok ezt a bővülést is
kezelik.

## 3. dia — Adatgyűjtési pipeline (1:30–2:45)

- Diagram/felsorolás: `seed → fetch (HTML/API letöltés) → parse (egységes
  Property DTO, immár `city` mezővel) → geocode (Nominatim, `city`
  fallback-kal) → properties.csv`
- 5 portál, eltérő hozzáférési mód (szerveroldali HTML, JSON-LD, SPA +
  belső API) — rövid említés, hogy ez technikailag nem triviális
  (pl. ingatlan.com Cloudflare-blokkolás).
- Jelenlegi méret: **1615 nyers sor**, ebből **170 duplikátum** (ismételten
  letöltött hirdetés) kiszűrve → **1526 egyedi hirdetés**. Portál-megoszlás:
  jofogas.hu 72,6%, a többi négy portál együtt a maradék.

*Beszélőpont:* ha kérdés jön "miért nincs ingatlan.com", kéznél van a válasz
(bot-védelem). Ha kérdés jön a duplikátumokról: a `fetch` újra rátalálhat
már látott linkekre, ezt a notebook most már explicit módon kiszűri.

## 4. dia — Adatkészlet jellemzői és adatminőség (2:45–4:00)

- Típus-megoszlás: lakás/ház dominál (≈90%), de a **sorház mára 20 elemes**
  (korábban csak 1 volt) — már kezelhető kategória, csak a `beruházás`
  maradt 1 elemes.
- Hiányzó értékek: `rooms` 14,5% (korábban 30,4% volt), koordináta **0%**
  (korábban 3,6% hiányzott — a `city` mezőre eső geokódolási fallback miatt).
- **Két konkrét adatminőségi hiba**: (1) az EUR/HUF eset (ismert, korábbi),
  (2) egy új eset: egy 141 m²-es ház ára **82 000 HUF** (≈580 HUF/m²) — ezt
  a kiugró-érték-szűrés fogja meg, de ld. a 7. dián, milyen hatása volt,
  mire odáig jutottunk.
- Ár/terület erősen jobbra elnyúló eloszlás → log-transzformáció indoklása.

*Beszélőpont:* ez a dia bizonyítja az alapos EDA-t — ha időhiány van, ezt
lehet a leginkább rövidíteni.

## 5. dia — Előfeldolgozás (4:00–4:45)

- Rövid, felsorolás-szerű dia:
  - duplikátumok eldobása (legfrissebb pillanatkép megtartása)
  - hiányzó `rooms` → típuson belüli medián + flag
  - `city` (dedikált mező, nem a szabad szöveges `location`) →
    `is_budapest`, `settlement`, Budapest-kerület
  - koordináta → `dist_to_bp_km` (haversine), ma már majdnem mindig elérhető
  - log-transzformációk, kiugró érték jelölés, one-hot kódolás
- Eredmény: `properties_preprocessed.csv`, 1525 sor, 45 oszlop.

*Beszélőpont:* egy mondat arról, miért nem imputáltunk koordinátát
(rossz koordináta rosszabb, mint a hiány jelzése) — ma ez már ritkán
releváns, mert a lefedettség majdnem teljes.

## 6. dia — Módszertan: modellek és kísérleti terv (4:45–5:45)

- 3 modell: Lineáris regresszió, Ridge, Random Forest.
- 80/20 train/test + 5-fold CV a train részen.
- 4 egymásra épülő kísérlet:
  1. teljes adathalmaz
  2. csak ház+lakás
  3. ház+lakás, kiugró értékek nélkül
  4. **hiperparaméter-keresés** `sklearn.model_selection.RandomizedSearchCV`-
     vel (Random Forest + Ridge) a 3. kísérlet adatain
- Miért ez a sorrend: a `telek`/`nyaraló` más piaci logikát/skálát
  követ → tesztelni akartuk, mennyit javít a szűkítés, majd hogy a fix
  hiperparaméterek helyett egy keresett beállítás mennyit ad hozzá.

## 7. dia — Eredmények (5:45–7:15)

**Fő táblázat (Random Forest, a 4 kísérlet):**

| Kísérlet | n | R² | MAPE |
|---|---|---|---|
| 1. Teljes adat | 1524 | 0,74 | 30,3% |
| 2. Ház + lakás | 1375 | 0,47 | 458,9%* |
| 3. Ház+lakás, outlier nélkül | 1344 | 0,74 | 26,2% |
| **4. + RandomizedSearchCV** | 1344 | **0,78** | **22,2%** |

\* *a 2. sor extrém MAPE-je egyetlen, irreálisan alacsony árú (82 000 HUF-os)
teszt-sorból adódik — jó illusztráció arra, hogy egy aggregált metrikát egy
hibás sor is tönkreteheti.*

- Random Forest minden kísérletben jobb, mint a lineáris/Ridge regresszió.
- A legnagyobb egyedi torzítást **nem a modell**, hanem **egy adatminőségi
  hiba** okozta (2. kísérlet) — ezt a 3. kísérlet outlier-szűrése oldja meg.
- A hiperparaméter-keresés (4. kísérlet) további, önálló javulást ad.

*Beszélőpont:* ha csak egy számot kell megjegyezni: **R²≈0,78, MAPE≈22%**
a végső (hangolt) modellen.

## 8. dia — Hiperparaméter-keresés `RandomizedSearchCV`-vel (7:15–8:00)

- A fix Random Forest (300 fa, max. mélység 6) helyett `RandomizedSearchCV`
  5-fold CV-vel keresett `n_estimators`, `max_depth`, `min_samples_leaf`,
  `min_samples_split`, `max_features` kombinációt.
- Talált beállítás: **≈559 fa, max. mélység ≈14** — jóval komplexebb, mint
  az eredeti fix választás.
- Eredmény: teszt R² 0,74 → 0,78, MAPE 26,2% → 22,2%.
- A Ridge `alpha`-ját is hangoltuk — a keresztvalidáción javult, a
  teszthalmazon alig: a lineáris modell korlátja nem a regularizáció
  erőssége, hanem a linearitás feltételezése.

*Beszélőpont:* a nagyobb adatmennyiség (1344 sor a korábbi 426 helyett)
elbír egy komplexebb fát túltanulás nélkül — ez a hiperparaméter-keresés
"ingyen" megtalálja, fix beállítással ezt nem tudtuk volna.

## 9. dia — Mi mozgatja a predikciót? (8:00–8:40)

- Feature-fontosság ábra (végső, hangolt Random Forest): `dist_to_bp_km`
  (0,66) és `log_area_sqm` (0,24) dominál, minden más jellemző együtt <10%.
- Predikció vs. valós ár / reziduum ábra — a legnagyobb hibák a drága
  (150-270M Ft) ingatlanoknál, jellemzően **alulbecslés**.

*Beszélőpont:* "méret + helyszín" megerősíti a köznapi intuíciót, de a
prémium szegmensben hiányzik valami (állapot, presztízs) a modellből.

## 10. dia — Korlátok (8:40–9:15)

- **Új korlát a bővült adaton:** a minta 72,6%-a jofogas.hu-ról jön, és
  erősen koncentrálódik néhány településre (Debrecen ≈28%, Dunaújváros
  ≈7%) — a budapesti arány ezért 32%-ról 13%-ra csökkent. Ez torzíthatja az
  általánosíthatóságot.
- Hiányzó jellemzők: `condition`, emeletszám, energetika, kilátás.
- `dist_to_bp_km` csak Budapest-közelséget fejez ki, nem az adott
  település/övezet saját árszínvonalát.
- A modell **csak ház+lakásra** érvényes, telekre/nyaralóra nem.

## 11. dia — Következő lépések és összefoglalás (9:15–10:00)

- Rétegzettebb/kiegyensúlyozottabb adatgyűjtés (a portál/település-torzítás
  csökkentésére).
- `condition` és településszintű ár-jellemző (target encoding) bevonása.
- Szisztematikusabb adatminőség-ellenőrzés (nem csak percentilis-alapú).
- Gradiens boosting kipróbálása (XGBoost/LightGBM) — a `RandomizedSearchCV`-s
  keret közvetlenül újrahasználható lenne rájuk is.
- Anomália-detektálás a reziduumok alapján (alul-/túlárazott hirdetések).
- **Egy mondatos zárás:** "Működő, reprodukálható end-to-end pipeline áll
  rendelkezésre; a hiperparaméter-hangolás önmagában is érdemben javított,
  de a mintavétel egyenletessége és a hiányzó jellemzők (pl. állapot)
  legalább annyira korlátozzák a pontosságot, mint az algoritmusválasztás."

---

## Időzítési tartalék

Ha kifutunk időből: a **4. és 5. dia** (adatminőség, előfeldolgozás részletei)
rövidíthető egyetlen összefoglaló mondatra, mivel a hallgatóság valószínűleg
jobban kíváncsi a modellezési eredményekre (7-8. dia). Ha több idő van:
a 9. dián mutassuk meg a predikció-vs-valós ábrát is, és engedjünk időt egy
rövid demóra (`show_data` parancs vagy a notebook egy cellája élőben).

## Várható kérdések és felkészülés rájuk

- *"Miért nincs ingatlan.com?"* → Cloudflare bot-védelem, 403 hibát ad.
- *"Miért nem imputáltátok a koordinátát?"* → rossz koordináta rosszabb,
  mint a hiány jelzése; helyette `has_coords` flag (ma már ritkán releváns,
  mert a lefedettség majdnem teljes).
- *"Miért volt a 2. kísérlet ennyire rossz (MAPE 459%)?"* → egyetlen,
  irreálisan alacsony árú (82 000 HUF-os) hirdetés került a teszthalmazba;
  ez megszűnik, amint a 3. kísérletben kiszűrjük a kiugró értékeket.
- *"Mennyit segített a `RandomizedSearchCV`?"* → a fix beállításhoz képest
  R² 0,74 → 0,78, MAPE 26,2% → 22,2% — a bővült adatkészlet elbír egy
  komplexebb (több fás, nagyobb mélységű) Random Forestet is.
- *"Miért torzult a minta Debrecen felé?"* → a seed-lista/keresési
  beállítások miatt a jofogas.hu-ról érkező új hirdetések nagy része egy-két
  vidéki településről jön — ez egy felismert, dokumentált korlát, nem
  szándékos döntés.
- *"Mennyire megbízható a 0,78-as R²?"* → egy ~270 soros teszthalmazon mért
  érték, a keresztvalidációs szórás (±0,01-0,02 MAE-n) jelzi a
  bizonytalanságot — ez korlát, nem végleges állítás.
