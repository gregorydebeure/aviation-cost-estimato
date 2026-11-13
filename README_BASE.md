# Base Menkor — 118 avions (13 novembre 2026)
- **Référence : `menkor_base.csv`**, 118 avions, tous complets. Premier build depuis `source/Menkor_118_avions_carburant_1274_2026-11-12.xlsx` (feuille `Base_123`) avec `tools/build_base_from_xlsx.py`, puis corrections manuelles du 13/11 (v2). Le CSV n'est plus reproductible depuis ce classeur.
- Fixe = équipage + formation + hangar + assurance + divers + forfait maintenance. Variable = maintenance + carburant + heures × (déplacements + catering + redevances) + supplément. Budget = fixe + variable.
- Carburant : 1,274 USD/L (482,41 US cents/USG) pour tous.
- Accents : fichier en UTF-8 avec BOM. Ne pas le rouvrir/enregistrer avec un outil qui change l'encodage (cela abîme les accents).
- Si un total devient impossible, `menkor_missing_fields` liste le manque et l'application ne calcule rien (rien n'est remplacé par zéro).
