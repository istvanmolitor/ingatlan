# Prezentáció vázlat — 10 perc

*Alapja: `project_dokumentacio.md`. Irányadó időzítés, dia-szám rugalmasan
igazítható; a cél kb. 10-12 dia, hogy diánként ~1 perc jusson.*

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
sklearn-t" típusú, hanem a nyers weboldalaktól indul.

## 3. dia — Adatgyűjtési pipeline (1:30–3:00)

- Diagram/felsorolás: `seed → fetch (HTML/API letöltés) → parse (egységes
  Property DTO) → geocode (Nominatim) → properties.csv`
- 5 portál, eltérő hozzáférési mód (szerveroldali HTML, JSON-LD, SPA +
  belső API) — rövid említés, hogy ez technikailag nem triviális
  (pl. ingatlan.com Cloudflare-blokkolás).
- Jelenlegi méret: **477 hirdetés**, portál-megoszlás (kis táblázat vagy
  oszlopdiagram).

*Beszélőpont:* ha kérdés jön "miért nincs ingatlan.com", kéznél van a válasz
(bot-védelem).

## 4. dia — Adatkészlet jellemzői és adatminőség (3:00–4:15)

- Típus-megoszlás (ház/lakás dominál, telek/nyaraló/sorház/beruházás kis
  mintaszám).
- Hiányzó értékek: `rooms` 30%, koordináta 3,6%.
- Egy konkrét **adatminőségi hiba** bemutatása (az EUR/HUF eset) — jó,
  figyelemfelkeltő, "ezt tényleg megtaláltuk az adatban" pillanat.
- Ár/terület erősen jobbra elnyúló eloszlás → log-transzformáció indoklása.

*Beszélőpont:* ez a dia bizonyítja az alapos EDA-t — ha időhiány van, ezt
lehet a leginkább rövidíteni.

## 5. dia — Előfeldolgozás (4:15–5:15)

- Rövid, felsorolás-szerű dia (ne menjünk bele minden lépésbe):
  - hiányzó `rooms` → típuson belüli medián + flag
  - `location` → `is_budapest`, `settlement`, Budapest-kerület
  - koordináta → `dist_to_bp_km` (haversine), nincs mesterséges pótlás
  - log-transzformációk, kiugró érték jelölés, one-hot kódolás
- Eredmény: `properties_preprocessed.csv`, 476 sor, 44 oszlop.

*Beszélőpont:* egy mondat arról, miért nem imputáltunk koordinátát
(rossz koordináta rosszabb, mint a hiány jelzése).

## 6. dia — Módszertan: modellek és kísérleti terv (5:15–6:15)

- 3 modell: Lineáris regresszió, Ridge, Random Forest.
- 80/20 train/test + 5-fold CV a train részen.
- 3 egymásra épülő kísérlet:
  1. teljes adathalmaz
  2. csak ház+lakás
  3. ház+lakás, kiugró értékek nélkül
- Miért ez a sorrend: a `telek`/`nyaraló` más piaci logikát/skálát
  követ → tesztelni akartuk, mennyit javít a szűkítés.

## 7. dia — Eredmények (6:15–7:45)

**Fő táblázat (Random Forest, 3 kísérlet):**

| Kísérlet | n | R² | MAPE |
|---|---|---|---|
| Teljes adat | 474 | 0,65 | 50,4% |
| Ház + lakás | 435 | 0,65 | 29,1% |
| **Ház+lakás, outlier nélkül** | 426 | **0,72** | **27,2%** |

- Random Forest minden kísérletben jobb, mint a lineáris/Ridge regresszió.
- A legnagyobb javulást **nem a modellváltás**, hanem az adattisztítási
  döntések (szűkítés, outlier-kezelés) hozták.

*Beszélőpont:* ha csak egy számot kell megjegyezni: **R²≈0,72, MAPE≈27%**
a végső modellen.

## 8. dia — Mi mozgatja a predikciót? (7:45–8:30)

- Feature-fontosság ábra (Random Forest): `dist_to_bp_km` (0,54) és
  `log_area_sqm` (0,38) dominál, minden más jellemző együtt <10%.
- Predikció vs. valós ár / reziduum ábra — a legnagyobb hibák a drága
  (150-280M Ft) ingatlanoknál, jellemzően **alulbecslés**.

*Beszélőpont:* "méret + helyszín" megerősíti a köznapi intuíciót, de a
prémium szegmensben hiányzik valami (állapot, presztízs) a modellből.

## 9. dia — Korlátok (8:30–9:15)

- Kis adatmennyiség (426 sor, 86 teszt) → bizonytalan metrikák.
- Hiányzó jellemzők: `condition`, emeletszám, energetika, kilátás.
- `dist_to_bp_km` csak Budapest-közelséget fejez ki, nem az adott
  település/övezet saját árszínvonalát.
- A modell **csak ház+lakásra** érvényes, telekre/nyaralóra nem.

## 10. dia — Következő lépések és összefoglalás (9:15–10:00)

- Több adat gyűjtése (folyamatos `fetch`/`parse`).
- `condition` és településszintű ár-jellemző (target encoding) bevonása.
- Gradiens boosting kipróbálása (XGBoost/LightGBM).
- Anomália-detektálás a reziduumok alapján (alul-/túlárazott hirdetések).
- **Egy mondatos zárás:** "Működő, reprodukálható end-to-end pipeline áll
  rendelkezésre; a modell pontosságának javítása jelenleg inkább adat-,
  mint algoritmus-kérdés."

---

## Időzítési tartalék

Ha kifutunk időből: a **4. és 5. dia** (adatminőség, előfeldolgozás részletei)
rövidíthető egyetlen összefoglaló mondatra, mivel a hallgatóság valószínűleg
jobban kíváncsi a modellezési eredményekre (7-8. dia). Ha több idő van:
a 8. dián mutassuk meg a predikció-vs-valós ábrát is, és engedjünk időt egy
rövid demóra (`show_data` parancs vagy a notebook egy cellája élőben).

## Várható kérdések és felkészülés rájuk

- *"Miért nincs ingatlan.com?"* → Cloudflare bot-védelem, 403 hibát ad.
- *"Miért nem imputáltátok a koordinátát?"* → rossz koordináta rosszabb,
  mint a hiány jelzése; helyette `has_coords` flag.
- *"Miért csökkent a lineáris modell R²-je az outlier-szűrés után?"* → a
  kiugró (nagyon drága/olcsó) pontok magyarázták a variancia nagy részét a
  lineáris illesztésnél; ezek elhagyása után a finomabb különbségeket a
  lineáris modell nem tudja jól visszaadni, a Random Forest viszont igen.
- *"Mennyire megbízható a 0,72-es R²?"* → kis teszthalmazon (86 sor) mért
  érték, a keresztvalidációs szórás (±0,03-0,06 MAE-n) jelzi a
  bizonytalanságot — ez korlát, nem végleges állítás.
