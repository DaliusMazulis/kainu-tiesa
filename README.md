# KAINŲ TIESA

Nemokamas viešų internetinių kainų stebėjimo bandymas Lietuvoje.

Programėlė: https://daliusmazulis.github.io/kainu-tiesa/

## Kas veikia

- Bendra visiems lankytojams ta pati istorija: `data/observations.json`.
- Paieška be lietuviškų diakritinių ženklų, pagal žodžius ir prekės kodą; parduotuvės filtras ir rikiavimas.
- 30, 90, 365 kalendorinių dienų grafikai bei stebėjimų lentelės. Trūkstamos dienos nepildomos; linija jungiami tik gretimų dienų taškai.
- Parduotuvės skelbiamų akcijų radaras ir atskiras istorijoje pastebėtų atpigimų filtras.
- Asmeninis įrenginio registras su JSON eksportu; ankstesnis `kt-prices` formatas išsaugotas. Asmeniniai įrašai nepublikuojami.
- Telefonams pritaikytas išdėstymas, dideli valdikliai, klaviatūros fokusas.

## Rinkimas ir 0 € infrastruktūra

Vieša GitHub saugykla, standartinis `ubuntu-latest` GitHub Actions vykdytojas, GitHub Pages. Jokių mokamų API, serverių ar paslaugų raktų. Python ir JavaScript be papildomų bibliotekų.

`.github/workflows/prices.yml` kasdien 06:23 UTC (08:23 Lietuvos žiemos laiku, 09:23 vasaros laiku) paleidžia testus, surenka kainas, įrašo istoriją į git ir paskelbia svetainę. Taip pat vyksta po pakeitimo `main`; galima paleisti rankiniu būdu per Actions. Tvarkaraštis nėra garantuotas: GitHub gali vėluoti arba po 60 dienų neveiklumo jį išjungti.

Renkama tik viešų „Rimi“ puslapių imtis pagal penkias paieškas (pienas, kava, sviestas, duona, kiaušiniai), įskaitant viešai rodomas susijusias prekes; tai ne visas parduotuvės katalogas. Vienas pirmasis prekės stebėjimas UTC dienai. Ankstesni įrašai neperrašomi. Senos kainos lieka istorijoje net jei prekė vėliau nebepasiekiama.

## Metodika ir apribojimai

Kaina iš matomo HTML kortelės teksto sutikrinama su viešai pateiktais tos pačios kortelės prekės kodu ir kainos metaduomenimis. Nesutampanti ar trūkstama kaina atmetama. Fiksuojama prekės nuoroda, rinkimo puslapis, laikas, EUR, kainos sąlygos bei puslapio SHA-256. Maiša nėra pilno istorinio puslapio archyvas ar nepriklausomas kainos autentiškumo įrodymas.

Renkamos viešos kainos be lojalumo kortelės. Kortelės, kiekio ir asmeniniai pasiūlymai neįtraukti. Nenaudojamas prisijungimas ar vietos parinkimas. Internetinės kainos gali skirtis nuo fizinės parduotuvės ar pasirinkto pristatymo adreso.

„Skelbiama akcija“ remiasi pardavėjo įprasta kaina tame pačiame puslapyje. Istorinis pokytis lygina naujausią kainą su ankstesnių 30 kalendorinių dienų mūsų stebėjimų minimumu, neįtraukiant naujausio stebėjimo dienos. Tai nėra teisinis vertinimas, garantija ar pilna kainų istorija prieš akcijos pradžią. Visada rodoma turimų dienų aprėptis. Senesnės nei 48 valandų kainos į radarą nepatenka.

`robots.txt` tikrinamas prieš puslapių užklausas; nesėkmės atveju prieiga stabdoma. Tarp užklausų paliekama bent 2 sekundės ir laikomasi didesnio `crawl-delay`. Peradresavimai nefiksuojami kaip kainos ir automatiškai nesekami. 403, 429 ir kiti ribojimai neapeinami; tame šaltinyje daugiau nebandome. `robots.txt` leidimas savaime nereiškia parduotuvės sutartinio leidimo.

Kitų parduotuvių viešos prieigos bandymų rezultatai yra `data/status.json`. Jų kainų parseriai dar neprijungti. Nėra apėjimų, mokamų tarpinių serverių ar išgalvotų pradinių duomenų. Rinkimo sutrikimas nesunaikina ankstesnės istorijos; atnaujinama šaltinio būsena. Svetainė pažymi vėlavimą po 48 valandų.

## Paleidimas ir tikrinimas

```sh
python -m unittest discover -v
node --test test_core.mjs
node --check app.mjs
python collector.py --collect
python -m http.server 8080
```

Atidaryti http://localhost:8080. Testuose naudojami tikri viešo HTML išrašai ir izoliuoti testiniai scenarijai; scenarijų kainos niekada nepatenka į svetainės duomenis. CI nevykdo jokių mokamų užduočių.

## Patikra 2026-11-24

13 Python ir 9 JavaScript testai praėjo. Tiesioginis rinkimas iš 5 „Rimi“ paieškos puslapių sukaupė 189 skirtingų prekių stebėjimus; 21 skelbiama akcija. Istorija prasideda šią dieną, todėl 30/90/365 dienų langai kol kas turi tik vienos dienos taškus.
