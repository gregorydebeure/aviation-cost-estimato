# Aviation Cost Estimator — migration v16 (167 modèles)

Rien n'a été déployé. Ce dossier remplace le paquet v15 : moteur corrigé conservé, base v16, tests, comparaison avant/après.
Tu relis, tu copies sur GitHub, Render redéploie.

## 1. Fichiers à copier sur GitHub

| Fichier / dossier | Action |
|---|---|
| `app.py`, `menkor_engine.py`, `menkor_report.py` | remplacent les versions v15 |
| `data/` (base v16 : `menkor_base_v16.csv` remplace `menkor_base_v15.csv`, + aliases, compléments web, vérification Challenger…) | remplace l'ancien dossier |
| `static/`, `.streamlit/config.toml` | inchangés |
| `tests/`, `tools/`, `migration_before_after.csv` | optionnels |

Aucune nouvelle dépendance.

## 2. Correction d'une erreur de mon compte rendu v15

J'avais écrit que Challenger 604, 605, 650 et Global 6000 « disparaissaient » de la base v15. **C'était faux.** Les trois Challenger étaient dans la base
v15 et sélectionnables ; ils n'étaient « absents » que dans mon script de comparaison, qui rapprochait les noms de l'ancienne application
(« Bombardier Challenger 604 ») du champ `model` de la base (« Challenger 604 ») par égalité exacte. Le script rapproche maintenant par identifiant,
modèle, « constructeur + modèle » ou alias. Résultat : **0 modèle manquant sur les 47 de l'ancienne application**, y compris Global 6000.
Le fichier `13_Challenger_pour_Claude.csv` (`data/challenger_verification.csv`) sert uniquement de contrôle : rien n'est importé deux fois,
chaque identifiant (`challenger_604`, `challenger_605`, `challenger_650`) apparaît une seule fois, source PDF ACC.

## 3. Ce qui change dans v16

1. **167 modèles uniques** = 144 fiches PDF ACC + 2 estimations web partielles + 21 fiches historiques. Base lue par `aircraft_id`.
2. **Global 6000 et Global 7500** (`bombardier_global_6000`, `bombardier_global_7500`) : source *Guardian Jet* (économie) + résumé technique public ACC.
   Marqués « web estimate » partout (liste des modèles, Dashboard, alertes, PDF, CSV). Affichés : URL, **date de consultation 2026-10-18**
   (date de consultation, pas de validité), scénario 300 h/an et 7,54 USD par gallon US, et les hypothèses **à confirmer** : USD (symbole « $ ») et gallon US.
3. **Alias « Global 7000 »** → `bombardier_global_7500` via `aliases_modeles.csv`. Champ « Quick find » dans la barre latérale ; aucun avion supplémentaire,
   aucune spécification du projet initial copiée.
4. **Ventilation respectée.** Pour les Global web : équipage agrégé (formation non isolée), maintenance en une ligne (cellule/moteur non séparés), assurance coque + RC.
   Champs absents = « non disponible », jamais 0, aucun coût générique. Seuls les postes de périmètre connu sont modifiables (équipage agrégé, hangar, assurance, divers,
   maintenance totale) ; une modification **remplace** le poste (jamais d'ajout). Une modification sur un poste inconnu (formation, cellule, moteur) est ignorée avec message.
5. **Séparation des sources** : les estimations web sont listées dans le tableau de comparaison de flotte (colonne `source_kind`) mais **exclues du graphique**
   (non équivalentes aux rapports ACC). Statuts de provenance `web_extracted` / `assumed` visibles.
6. PDF : ligne « Data source » (type de source, fichier, URL web et date de consultation). CSV : `source_kind`, `source_file`, `web_source_url`, `web_source_consulted`.
7. Moteur v2.1 : toutes les corrections v15 conservées (un seul moteur, pas de double comptage, pas de 0,82, litres, USD/EUR avec taux daté, deux modes).

## 4. Résultats

`python3 -m unittest discover -s tests` → **64 tests, tous OK** (53 v15 mis à jour pour 167 modèles + 11 nouveaux v16).
Nouveaux tests : Challenger présents une seule fois et sélectionnables ; alias Global 7000 sans avion supplémentaire ; totaux Global 6000/7500
(référence = simulation = total publié ; composants = total) ; aucune ventilation inventée ; modification de maintenance qui remplace ;
carburant 512/528 gal US/h → L/h × 1,991857 USD/L ; alertes source/date/hypothèses ; écrans, deux modes, PDF (texte vérifié avec pdftotext) et CSV ;
provenance et contrôles (2 340 contrôles, 376 « REVIEW » conservés) ; 167 modèles × 2 modes sans erreur.
Contrôle des tests par mutation : (a) éditeurs de composants web remplacés par ceux des PDF, (b) alias pointant vers le mauvais avion, (c) date de consultation perdue → les tests échouent à chaque fois.

Chiffres Global (300 h, simulation = référence) : Global 6000 ≈ 5 376 537 USD (17 922 USD/h) ; Global 7500 ≈ 4 983 440 USD (16 611 USD/h).

## 5. Limites restantes

- Streamlit n'est pas installable dans mon environnement : écrans testés avec un simulateur, pas dans un vrai navigateur. Premier passage à faire sur Render/en local
  (sélection, Quick find « Global 7000 », bascule des deux modes, PDF).
- Les fiches web sont indicatives : un seul scénario (300 h, 7,54 USD/gal), USD et gallon US **supposés** ; frais fixes très différents des rapports ACC (non équivalents).
  Dans `migration_before_after.csv`, le Global 6000 passe de ≈3,1 M à ≈7,2 M USD à 380+120 h : ce n'est pas une correction, c'est un autre périmètre de coûts.
- Formation équipage non isolée, split cellule/moteur inconnu pour les Global web ; vitesses de croisière contradictoires entre sources laissées vides (contrôle `cruise_speed_source_consistency` en REVIEW).
- 21 fiches historiques à reconstruire ; aucune date de validité de prix dans les 144 rapports ; tarif charter absent des rapports.
- Conflit G450, Challenger 870C/870CS, « GAL » = gallon US du Challenger 300 et des Global : à confirmer (voir v15).
- Droits de redistribution commerciale de la base à vérifier avant publication ; outil de cotation externe non relié au moteur.

## 6. Ajout : actualisation Menkor (+15 %) et source « Menkor »

- **Actualisation** (case « Update base costs (inflation) » + pourcentage, 15 % par défaut, modifiable) appliquée **avant** toute modification utilisateur, sur :
  maintenance et programmes de maintenance (cellule, moteur/APU ; ligne unique pour les Global web), formation équipage, hangar, handling / taxes en route (ligne « airport fees »).
  **Non modifiés** : carburant, assurance, salaires/frais d'équipage, catering, déplacements équipage, divers.
- Les totaux publiés bougent exactement des mêmes montants que les lignes (composants = total, lignes d'arrondi inchangées, pas de double comptage).
  Une modification manuelle remplace la valeur actualisée. L'identifiant de configuration, le PDF et le CSV portent l'état de l'actualisation.
- **Global (Global 5000, Express, Express XRS)** : formation récurrente = 2 pilotes × 60 000 USD = 120 000 USD/an, prix actuel, **non réinflaté**.
  Hypothèse à confirmer : 2 pilotes par appareil. Global 6000 et 7500 (estimations web) : formation non isolée dans l'équipage, donc non ajustée et non inventée.
- **Source** : « Menkor reference database » dans les écrans, le PDF et le CSV. Le nom du calculateur tiers et son URL ne sont plus affichés (contrôlé sur 167 modèles × 2 modes). Les fichiers internes de `data/` conservent l'origine. Pour les estimations web, l'URL Guardian Jet et la date de consultation restent affichées.
- Fiches historiques : non actualisées (totaux seuls), avec message.

Limites : 15 % uniforme (hypothèse Menkor, pas un indice sourcé) ; la ligne handling/airport fees de la base est faible (ex. Global 5000 : 105 USD/h) et regroupe handling et taxes en route ;
« 3 à 4 ans » est une indication de Greg, les rapports n'ont pas de date ; assurance et salaires non actualisés.
Tests : 73 OK (dont 9 sur l'actualisation, le remplacement par modification manuelle, la formation Global et l'absence de mention ACC), mutation vérifiée.
Publication : voir `PUBLISH_GUIDE_FR.md`.

## 7. Ajout : tarifs charter par modèle (fichier Menkor) et libellés du listing

- **Fichier** `menkor_tarifs_charter.csv` (ton fichier, inchangé, 167 lignes) remplace la grille par catégories (`menkor_charter_rates.csv` et `categorie_charter.csv` sont supprimés du paquet ; ils peuvent être supprimés de GitHub).
- Dans « Charter Pricing » : choix **Référence / Bas / Haut** (si fourchette publiée) ou **tarif personnalisé** (USD ou EUR). Toujours présenté comme une **ESTIMATION** : bandeau + encadré « À propos de cette estimation » (source, modèle de l'annonce, région, date de consultation, notes, carburant / taxes / positionnement), et avertissement dans l'onglet Rentabilité, le PDF et le CSV.
- **Règles du fichier respectées** : `auto_prefill_allowed` = true (117 modèles) → référence présélectionnée ; false (50 : proxys de famille, faible confiance, configuration à vérifier) → tarif personnalisé par défaut + avertissement « Not pre-selected » ; 19 modèles sans prix public (`manual_quote_required`) → saisie manuelle uniquement, jamais 0 ni un autre modèle.
- 7 modèles sont en EUR (A340, ACJ319neo, 737-500/600/700, 767-200ER/300ER) : conversion seulement avec le taux USD → EUR daté.
- Prix = annonces publiques de courtiers : prix client indicatif, pas un devis Menkor, pas un revenu net opérateur ; taxes, frais d'aéroport et positionnement peuvent s'ajouter. L'actualisation des coûts n'est jamais appliquée au prix charter.
- 31 lignes de faible confiance (proxys). Le fichier des aéroports n'est toujours pas utilisé.
- **Listing** : « pdf_acc » / « web_estimate » ne s'affichent plus (« Menkor reference », « Web estimate (partial) », « Historical sheet »).
- Tests : 84 OK.
