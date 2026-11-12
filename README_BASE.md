# Base Menkor — 118 avions (12 novembre 2026)
- Source : `source/Menkor_118_avions_carburant_1274_2026-11-12.xlsx` (feuille `Base_123`), recalculé. ACJ319neo / ACJ320neo exclus par le builder.
- Sortie : `menkor_base.csv`. Reconstruction : `python tools/build_base_from_xlsx.py <xlsx> data/menkor_base.csv`.
- Fixe = équipage + formation + hangar + assurance + divers + forfait maintenance. Variable = maintenance + carburant + heures × frais horaires. Budget = fixe + variable.
- Carburant : 1,274 USD/L (482,41 US cents/USG) pour tous ; classeur en USD / 1000 L.
- Global 6000 / 7500 : 350 h, lignes formation, divers, déplacements, catering, redevances = BBJ2 (instruction client).
- 116 avions complets, 2 incomplets. Rien n'est remplacé par zéro.
