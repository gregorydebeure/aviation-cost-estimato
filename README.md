# ✈ Aviation Cost Estimator

Application Streamlit de simulation des coûts d'exploitation d'avions d'affaires.

---

## Déploiement rapide sur Streamlit Cloud (gratuit)

### 1. Prérequis
- Compte GitHub : https://github.com
- Compte Streamlit Cloud : https://share.streamlit.io

### 2. Étapes

```bash
# Cloner / créer un dépôt GitHub avec ces fichiers :
#   app.py
#   requirements.txt
#   README.md

# Sur https://share.streamlit.io :
# → "New app" → sélectionner votre repo → main branch → app.py
# → Deploy !
```

### 3. Structure du projet

```
aviation_costs/
├── app.py            # Application principale
├── requirements.txt  # Dépendances Python
└── README.md         # Ce fichier
```

---

## Utilisation locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre sur http://localhost:8501

---

## Format du fichier Excel à importer

Le fichier doit contenir les colonnes suivantes (noms exacts) :

| Colonne                | Description                              | Obligatoire |
|------------------------|------------------------------------------|-------------|
| `Modele`               | Nom de l'appareil                        | ✓           |
| `Couts_Fixes_Annuels`  | Coûts fixes hors équipage (€/an)         | ✓           |
| `Couts_Equipe_Annuels` | Coûts d'équipage annuels (€/an)          | ✓           |
| `Cout_Horaire_Charter` | Coût variable horaire charter (€/h)      | ✓           |
| `Cout_Horaire_Prive`   | Coût variable horaire privé (€/h)        | ✓           |
| `Taux_Charter_EUR_h`   | Tarif charter facturé au client (€/h)    | ✓           |
| `Categorie`            | Catégorie (Light, Midsize, etc.)         | —           |
| `Autonomie_km`         | Autonomie maximale en km                 | —           |
| `Vitesse_Croisiere_km_h` | Vitesse de croisière en km/h           | —           |
| `Passagers_Max`        | Nombre de passagers maximum              | —           |

Un template Excel téléchargeable est disponible directement dans l'onglet **Données** de l'application.

---

## Fonctionnalités

- **Upload** de votre propre base de données Excel/CSV
- **Sélection** par catégorie et modèle d'avion
- **Configuration** des heures charter et privées (sliders)
- **Tableau de bord** : coût total, répartition en donut et barres empilées
- **Simulation de rentabilité** : waterfall financière, taux de couverture
- **Analyse de sensibilité** : courbe résultat net vs heures charter, break-even
- **Comparaison multi-appareils**
- **Export template** Excel pré-rempli

---

## Note sur votre fichier Falcon 900EX (D-CCCC)

Les données de votre budget ont été analysées et intégrées dans le jeu d'exemple :
- Coûts fixes exploitation : 595 915 €/an
- Coûts équipage : 596 942 €/an
- Coût horaire variable charter : 2 272 €/h
- Tarif charter : 5 700 €/h
- Base de calcul : 500 h/an (380h charter + 120h privé)
- Coût total : ~2 329 111 €/an
- Revenu charter projeté : 2 775 150 € → Résultat : +446 038 €
