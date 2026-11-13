# Aviation Cost Estimator — v20 (lots A, B, C)

Aucun déploiement, aucune migration en production, aucun paiement, aucun envoi réel n'ont été effectués. Aucun tarif, abonnement ni configuration de paiement n'a été modifié.

## Lot A — parcours, saisie, résultats (sections 1–9, 12)
Trois parcours (estimer les coûts / simuler le charter / demander un budget spécifique), barre latérale simplifiée, prix moyen du carburant par litre, récapitulatif + bouton unique de confirmation, résultats selon disponibilité, vues client nettoyées (provenance réservée à l'admin), Market Search reformulé (prix unique 300 €, Stripe inchangé).

## Lot B — offre, démo, PDF, étude (sections 10, 11, 13)
- **Démo gratuite** : un seul avion (Falcon 7X), scénario « report reference » (heures et prix carburant du rapport, rien d'inventé), résultats + répartition + aperçu du rapport, étiquetés « Demo ». Plus de « $ 000,000 ». Aucun calcul pour l'avion choisi par un utilisateur Free.
- **Tableau des offres** Free / Essentiel 15 €/mois / Pro 50 €/mois (prix inchangés), uniquement les fonctions existantes, accès direct à l'inscription / l'abonnement existants.
- **PDF modèle v2.0** : p.1 synthèse coûts + résultats opérationnel/économique + hypothèses essentielles + exclusions principales ; p.2 détail, scénarios, lien d'étude ; annexe. Pas de provenance technique, référence de scénario + version du modèle en pied de page. Variante « coûts seuls » sans cartes vides. Les anciens PDF sont invalidés si les hypothèses OU la version du modèle OU le branding changent.
- **Offre d'étude** : « What will this specific aircraft cost you? » / bouton « Request my aircraft budget » ; formulaire court (nom, e-mail, modèle prérempli, statut propriétaire/acquisition **sans réponse présélectionnée**, message). Canal Resend existant ; « transmis » uniquement après réception réelle.

## Lot C — scénarios, comparaison, dossiers, branding, suivi (sections 14–16)
Nouveau module `menkor_store.py`, onglet « 🗂 My scenarios » (Essentiel : scénarios personnels ; Pro : comparaison, dossiers, branding).
- Sauvegarde / nom / recherche par liste / duplication / suppression **avec confirmation** (corbeille récupérable) / purge explicite.
- Chaque scénario stocke toutes les hypothèses, la version de la base et du moteur, la date, la liste des champs saisis par l'utilisateur et un instantané des résultats **tels que sauvegardés**. Au rechargement : avertissement si base/moteur ont changé, jamais de recalcul silencieux ; « Recalculate with the current base » est une action explicite qui affiche l'écart.
- Isolation par propriétaire côté serveur : le propriétaire est l'e-mail authentifié de la session (jamais une saisie), chaque requête filtre `owner_email`, RLS activé sans politique.
- Comparaison Pro de 2–3 avions : hypothèses communes (heures, prix carburant) + ajustements **par avion** étiquetés ; donnée manquante = « not computed », jamais zéro.
- Dossiers clients simples (supprimer un dossier conserve ses scénarios).
- Branding PDF (Pro) : nom + logo PNG/JPEG ≤ 400 Ko validés par signature ; la mention Menkor, hypothèses, limites et exclusions restent.
- **Suivi** : aucun outil d'analytics n'existait dans l'application. Événements anonymes first-party (`events`), liste blanche : `visit, first_simulation, signup, subscription_activated, scenario_saved, report_generated, study_request_received, subscription_cancelled` ; propriétés autorisées : `plan`, `journey`, `source` uniquement. Jamais d'e-mail, nom, message libre, MSN ni contenu de dossier ; identifiant de session aléatoire haché. Dédoublonnage par session (reruns Streamlit). Activation / annulation déduites des vérifications Stripe côté serveur.

## À configurer
| Élément | Détail |
|---|---|
| Migration SQL | `migrations/2026_10_lotC_up.sql` à exécuter vous-même (d'abord sur un projet de test). Retour arrière : `migrations/2026_10_lotC_down.sql` (détruit scénarios/dossiers/profils/événements : exporter avant). |
| Secrets existants | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (stockage + événements), `RESEND_API_KEY`, `ADMIN_EMAIL` / `BUDGET_REQUEST_TO` (formulaire d'étude). |
| Optionnel | `APP_PUBLIC_URL` (lien du PDF / de l'offre ; défaut `https://aviation-cost-estimator.onrender.com`), `EVENTS_ENABLED=0` pour couper le suivi. |
| Sans Supabase | Sauvegarde désactivée avec message explicite ; aucun événement ; rien n'est annoncé comme enregistré. |

## Limites et points ouverts (honnêtes)
- Le suivi n'enregistre PAS le renouvellement d'abonnement (pas de webhooks Stripe dans l'application) ni aucun outil tiers ; il n'y a pas de bannière de consentement existante : les événements sont first-party, sans cookie ni identifiant personnel. À valider côté juridique/DPO selon vos obligations.
- Le tableau de bord d'événements n'est pas fourni : lisez la table `events` dans Supabase.
- « Ouvrir » un scénario ne repeuple pas les champs de la barre latérale : le scénario sauvegardé est consulté, recalculé et comparé dans l'onglet.
- L'isolation est appliquée dans le code serveur (clé de service) et testée avec un faux PostgREST ; elle n'a pas été testée contre un vrai Supabase.
- Les URL de succès/annulation des abonnements Stripe pointent encore vers une ancienne adresse streamlit.app (non modifié) ; à confirmer avec l'adresse publique réelle.
- Les tests UI utilisent `tests/fake_streamlit.py` (enregistreur) : ce n'est PAS une validation en navigateur réel ; aucune vérification mobile/desktop réelle n'a été faite.
- Fonctions Pro (comparaison, dossiers, branding) : à ne pas annoncer commercialement avant votre validation en conditions réelles ; elles ne figurent pas dans le tableau des offres.
- Secrets exposés précédemment (clé Resend, etc.) : à régénérer de votre côté.

## v20.1
- Carburant : la méthode de prix (mon prix moyen / prix du rapport / benchmark régional) se choisit directement dans le bloc « Fuel ». Le benchmark (région + prix modifiable, avertissements conservés) donne un budget et un PDF sans saisir de prix. Par défaut, aucun prix n'est supposé.
- « Entered by you » ne liste plus que les hypothèses réellement saisies (plus les valeurs par défaut).
- Tests : 286 OK.

## v20.2
- Correction : « Delete » affichait un objet interne (Streamlit « magic » sur une expression conditionnelle). Helper `_say()` partout + test AST `tests/magic_scan.py` qui interdit toute expression nue dans `app.py`.
- Cost Master : note « base équipage = 2 pilotes » ; équipage additionnel (mécanicien navigant, personnel de cabine : nombre × salaire annuel, 0 par défaut = rien ajouté) ; « Other maintenance programme » (par heure, vide = non saisi) ; « AOC management fee » à côté de CAMO ; taxes gouvernementales. Amortissement et prêt restent dans la barre latérale (Ownership), rappelés dans Cost Master.
- PDF / écrans clients : retrait des mentions « +15 % », « Menkor cost base », « Economic reference date not documented », « currency assumed » et des 5 lignes d'annexe demandées. Nouvelle note : budget dépendant de chaque avion (MSN, programme de maintenance, événements) ; coûts évoluant avec l'inflation, révision périodique, carburant = moyenne de benchmarks régionaux mondiaux. Le tableau +15 % reste visible pour l'admin seulement.
- Moteur 2.3 (les anciens scénarios sauvegardés sont signalés comme calculés avec une version antérieure). Le « management fee » ne masque plus AOC ni taxes (seulement CAMO/dispatch).
- Tests : 308 OK (enregistreur, pas un navigateur réel).

- v20.2b : champ « Other maintenance programme » sans infobulle (elle masquait le champ voisin) ; frais de gestion uniquement dans Advanced adjustments ; rappel du carburant (méthode, région, prix, burn) dans Variable costs ; libellés des composants raccourcis (plus de « added once »). Tests : 311 OK.

## v20.3 — comparaison : deux modes + scénarios Cost Master
- **A. Indicative model comparison** (inchangée dans son principe) : base moyenne propre à chaque modèle, heures et prix carburant communs, consommation propre à chaque avion, aucun ajustement Cost Master. Périmètre vérifié : la comparaison utilise la base de coûts moyens Menkor **une seule fois** (7X : fixes 611 204 USD = valeur stockée, pas de second +15 %) ; l'original publié (588 918 USD) n'est utilisé qu'en mode « Report reference ». L'écran client dit « average costs » sans nommer de source.
- Règles : champ vide = hypothèse commune ; 0 saisi = vrai zéro (frais fixes conservés, coût/heure « n/a ») ; prix invalide (≤ 0, NaN) = message, jamais de retour silencieux au prix commun. Exceptions par avion dans le panneau fermé « Adjustments ».
- **B. Compare my saved scenarios** : 2–3 scénarios sauvegardés, chacun avec son avion et ses hypothèses, calculés par le même moteur que Cost Master. « Use each scenario’s assumptions » (défaut) ou « Apply common assumptions » (heures, prix carburant, devise d'affichage ; recalcul sur une copie, sauvegardes intactes, valeurs remplacées listées ; heures charter mises à l'échelle proportionnellement).
- **Cost Master** : « Save scenario » (nom + nom/MSN facultatif) puis « Add to comparison » (refusé si le scénario a changé depuis la sauvegarde). Le scénario conserve toutes les hypothèses (équipage additionnel, maintenance, management/AOC/CAMO/dispatch/taxes, coûts par atterrissage, dépréciation et intérêts séparés, devises et taux datés, versions base/moteur). Le MSN est stocké dans le JSON du scénario : **aucune migration SQL**.
- Tableau : heures totales, consommation, prix carburant, fixes, variables, budget d'exploitation, coût par heure, management inclus ou exclu, postes non renseignés ; dépréciation / intérêts / coût économique dans un **tableau séparé**, jamais classés avec le budget d'exploitation ; aucun tri « moins cher ». Phrase « Equal annual hours do not imply equivalent missions or aircraft capabilities. » Export CSV de la comparaison (même lignes que l'écran, versions et référence de comparaison ; la référence change dès qu'une hypothèse change).
- Version base/moteur différente : le scénario est recalculé et signalé, son budget sauvegardé reste affiché en note, jamais remplacé en base.
- Tests : 335 OK (dont 24 nouveaux, `tests/test_v20_lot_e.py`).
- Notes internes admin (« [internal] … ») : petit texte gris en italique (« Admin note · … ») au lieu d'un cadre orange/rouge ; invisibles pour les clients.

## v20.4 — comptes, abonnements, e-mails (voir SETUP_V20_4_FR.md)
- Pass 48 h supprimé (code, boutons, textes). Market Search reste 300 € ; la ligne « $300 » de la frise d'acquisition devient « € 300 ». Tarifs d'abonnement inchangés (15 € / 50 €).
- Mots de passe : scrypt salé (`menkor_accounts.py`), conversion silencieuse des anciens SHA-256 à la connexion, verrouillage 15 min après 5 échecs, message identique compte inconnu / mauvais mot de passe, admin en comparaison à temps constant (+ `ADMIN_PASSWORD_HASH` optionnel).
- RLS activée sur `users` (migration `2026_10_lotD_up.sql`, retour arrière fourni) ; colonnes verrouillage / abonnement ; table `stripe_events` (idempotence).
- Webhook Stripe (Edge Function Supabase) : abonnement, renouvellement, résiliation ; accès pour active / trialing / past_due ; un price id inconnu ne change jamais le plan ; événements produit anonymes (activé / renouvelé / résilié) sans doublon.
- E-mails : confirmation d'inscription à l'utilisateur (nécessite `EMAIL_FROM`, domaine vérifié), notification d'inscription au propriétaire (`SIGNUP_NOTIFY_TO` ou `ADMIN_EMAIL`), confirmation d'abonnement (webhook). Rien n'est annoncé comme envoyé sans réponse 2xx du fournisseur.
- Test corrigé : une date de devis carburant figée (2026-10-20) était devenue périmée ; elle est maintenant relative à la date du jour.
- Tests : 364 Python OK + 12 Node (logique du webhook). Aucun e-mail réel, aucun appel Stripe/Supabase réel.

## v20.4.1 — secrets robustes (correctif)
- Les secrets sont lus d'abord dans `st.secrets`, puis directement dans les variables d'environnement Render (`_secret`). Même si le fichier `.streamlit/secrets.toml` est absent, vide ou en cours d'écriture, SUPABASE_URL / SUPABASE_SERVICE_KEY / ADMIN_* restent lisibles.
- Le pont Render → secrets.toml n'écrit plus le fichier à chaque interaction (seulement s'il change, écriture atomique) et ne dépend plus de la seule variable ADMIN_EMAIL.
- Les variables EMAIL_FROM, SIGNUP_NOTIFY_TO, ADMIN_PASSWORD_HASH, APP_PUBLIC_URL, EVENTS_ENABLED sont maintenant transmises (elles ne l'étaient pas en v20.4).

## v20.5 — Mot de passe oublié
- Sidebar (Login) : « Forgot your password? » → e-mail avec lien `?reset=<jeton>`, valable 60 min, usage unique.
- Jeton signé HMAC (secret optionnel `RESET_SECRET`, sinon dérivé de `SUPABASE_SERVICE_KEY`), lié à l'empreinte du mot de passe actuel : le lien meurt dès qu'il est utilisé ou que le mot de passe change.
- Réponse identique que le compte existe ou non (pas d'énumération) ; 3 demandes max par session.
- Le nouveau mot de passe est haché (scrypt) ; compteur d'échecs et verrouillage remis à zéro.
- Aucune migration SQL. Nécessite `EMAIL_FROM` (domaine vérifié) et `RESEND_API_KEY`.
- 18 nouveaux tests (384 au total, OK).

## v20.6 — Sensitivity › « Compare with similar aircraft »
- Remplace « Fleet Comparison » (filtre Manufacturers, tableau, barres par coût/h) par : avion sélectionné + 3 alternatives de la même catégorie, 4 barres max (budget annuel), sélectionné en doré « Selected aircraft ».
- Catégories : la colonne « Categorie » de la base est le constructeur ; mapping interne explicite par aircraft_id (`SIMILAR_CATEGORIES` dans menkor_engine.py), sans toucher aux données économiques.
- Sélection déterministe (hash avion + candidat + version de base), indépendante des coûts et du scénario ; constructeurs différents en priorité ; uniquement les fiches de référence détaillées (ni estimations web, ni fiches historiques).
- Calcul : `E.similar_comparison` → `compute()` avec un scénario propre (heures totales du scénario actif, prix carburant effectif, même taux daté). Aucune modification Cost Master, frais, hypothèse charter ou coût de possession n'est transféré (l'ancien `fleet_comparison`, inchangé et désormais inutilisé, les laissait passer).
- Bouton « Choose your own comparison » (plan Pro) : positionne My scenarios › Compare aircraft › Indicative model comparison puis clique l'onglet par script (à vérifier en navigateur réel).
- 22 nouveaux tests (406 au total, OK).

### v20.6.1 — Garde-fou prix carburant
- Un prix moyen > 10 par litre (devise saisie) est refusé avec un message explicite (séparateur décimal : 1.038 et non 1038) au lieu de produire un budget absurde. Moteur (`fuel_price_implausible`, prix moyen et devis manuel) et comparateur indicatif. 3 tests ajoutés (409 au total).

## v20.7 — « Your flying cost after charter contribution » (Profitability + Quotation)
- Champ renommé « Owner flight hours / year » (heures propriétaire uniquement ; heures facturées et positionnement inchangés). Libellés associés mis à jour (récapitulatif, seuil, rapport).
- Calcul unique dans le moteur : `owner_flight_indicator(owner_remaining_cost, heures propriétaire)` → `profit["owner_flight"]`. Le solde existant (= −résultat opérationnel : coûts + frais − recettes nettes, commission une seule fois, positionnement inclus) est réutilisé, rien n'est déduit deux fois.
- Reste par heure propriétaire = reste annuel ÷ heures propriétaire uniquement ; n/a si 0 h ; couverture exacte / excédent → « Operating costs fully covered » (reste 0, excédent séparé, jamais de coût horaire négatif).
- Même encadré dans Profitability (sous le résultat opérationnel) et Quotation (sous les indicateurs) ; tarif réellement saisi, indépendant du curseur de marge ; devise et taux daté du scénario. Sans tarif / base de tarif : pas d'encadré, invitation à compléter.
- 17 nouveaux tests (426 au total, OK).

## v20.8 — Google Analytics 4 (G-YN0BMF7S3M)
- Nouveau `menkor_analytics.py` + appel `_inject_ga()` dans `app.py`. Consentement d'abord (rien chargé avant « Accept »), une page_view par chargement de page (garde côté navigateur, insensible aux re-runs Streamlit), URL sans paramètres, aucune donnée personnelle ; `GA_ENABLED=0` / `GA_MEASUREMENT_ID` en variables facultatives.
- 7 tests Python + `tests/ga_browser_check.py` (vrai Chromium, Google simulé, 15 contrôles). Procédure : `GA4_VERIFICATION_FR.md`.

## v20.9 — My scenarios → Compare aircraft → Compare my saved scenarios
- **No common assumptions in this mode**: the "Assumptions" selector and "Apply common assumptions" are gone; the old session keys (`cmp_harm`, `cmp_s_*`) are purged at each render, so no hidden value can alter a result. Each scenario is computed from its own saved assumptions with the common engine; saved scenarios are never modified. Common assumptions remain only in *Indicative model comparison*.
- **Scenario versions**: a scenario saved with another base/calculation version is NOT compared silently. The screen explains it and offers "Recalculate for this comparison" (copy in memory, original untouched).
- **Screen**: scenarios in columns, indicators in rows (main assumptions, results, ownership/economic block only when entered; missing = "n/a"). Owner indicator = the existing engine `owner_flight` (no new formula). Four charts (stacked budget, net revenue vs costs, operating result with zero axis, remaining cost per owner hour — never negative, 0 owner hours = n/a, covered = 0 + surplus shown separately). One stable colour per scenario.
- **PDF "Generate comparison report (PDF)"**: page 1 title/names/key results, charts, then assumptions, all results, exclusions. Same table and chart data as the screen and CSV (`menkor_store.comparison_table`, `comparison_chart_data`). Broker branding, generation date and comparison reference kept. The PDF is invalidated when selection, assumptions, currency/rate, results or branding change.
- **Currency**: one currency (USD, or EUR with a dated rate); without a valid dated rate everything stays in USD. Converted once.
- Files: `app.py`, `menkor_store.py`, `menkor_report.py`, `tests/test_v20_lot_e.py` (2 tests updated), `tests/test_v20_lot_k.py` (20 new tests). Not tested in a real browser.

## v20.10 — +15 % mark-up removed, "Data provenance" panel removed
- `menkor_engine.load_base()` now reads the **original published values** (`original__*` columns) for every line and total: no +15 % anywhere (Custom simulation = published base; Report reference unchanged). No data file is modified: the CSV is untouched, the switch is in the loader.
- Only difference kept: the stated Menkor recurrent-training price (120 000 USD) of Global 5000 / Global Express / Global Express XRS; only the totals that contain that line move by its difference to the published training cost.
- `DB_VERSION` = `v17-167-models-published`: scenarios saved earlier are flagged "other base version" and need the explicit recalculation (originals untouched).
- Screen: the "Menkor cost base — original vs base values" table and the admin "Data provenance" panel are gone; the results CSV no longer carries the `menkor_base_*` adjustment rows.
- Tests rewritten for the new behaviour (no mark-up). 454 tests OK.

## v20.11 — My scenarios → Saved scenarios: folders first
- The broker first sees his **folders as tiles** (name, number of aircraft) plus "No folder"; a click opens the folder, which lists its **aircraft** (model, scenario name, date, annual budget, operating result). "Open" shows the saved data of one aircraft (saved results, saved assumptions, recalculation on demand).
- Rename / move / delete / duplicate moved behind "Open" (and "Folder options" for the folder itself). The separate "Client folders" section is gone: create, rename, delete folders directly in the browser.
- Tick 2–3 aircraft of a folder → "Compare the N selected scenarios" opens Compare aircraft → Compare my saved scenarios.
- Saving: the Folder field offers the existing folders and "＋ New folder…"; it defaults to the folder being browsed / last used.
- Essentiel plan and Pro without folder: flat list with "Open". No data migration (the `folders` table already exists).
- Not included: "Open" displays the saved data; it does not reload the values into the Cost Master inputs. Not tested in a real browser. 467 tests OK.

## v21 — Base Menkor 118 avions (12-13 novembre 2026)
Aucun déploiement ni migration en production. La base précédente (167 avions, majoration de 15 %) est remplacée par la base Menkor.
- **Référence** : `menkor_base.csv` (118 avions). Construit d'abord depuis le classeur `Menkor_118_avions_carburant_1274_2026-11-12.xlsx` avec `tools/build_base_from_xlsx.py`, puis **corrigé à la main le 13/11/2026** (v2). Depuis cette date le CSV est la référence : il n'est plus reproductible par le builder (le classeur est conservé comme archive de la première version).
- **Instructions du 12/11** : ACJ319neo et ACJ320neo retirés ; carburant unique 482,41 US cents/USG = 1,274 USD/L ; Global 6000 et 7500 à 350 h.
- **Corrections du 13/11** : Challenger 601-1A et Hawker 400XPR complétés (**118 avions complets, 0 incomplet**) ; maintenance révisée (Falcon 20 et 2000, Citation III et CJ2, Challenger 850 CS et 870C, G100, G300, G350, G400, G500 ancien, Hawker, Learjet, Lineage…) ; frais d'aéroport relevés pour les gros avions ; 10 avions passent au barème d'équipage 3 ; accents réparés (ils étaient abîmés dans le fichier reçu).
- **Falcon 7X** : fixe 612 713 / variable 2 620 296 / budget 3 233 009 USD.
- **Moteur 2.4 / base `v24-menkor-118-corrected-2026-11-13`** : les scénarios sauvegardés passent par le « Recalculate » explicite ; les avions retirés sont signalés.
- **Marque** : le CSV porte « MENKOR AVIATION LTD » (colonne `report_brand`), mais le code ne lit pas cette colonne ; les PDF affichent toujours « Menkor Aviation GBL » (décision en attente).
- `tools/audit_adjustment.py` supprimé. Tests : 471 OK (faux Streamlit, pas un navigateur réel). L'absence d'avion incomplet est testée avec un cas synthétique (`tests/incomplete_support.py`).

## v24.1 — PDF template 2.1 (13 Nov 2026)
- PDF page 1: new highlighted box "Your cost per flight hour — how charter smooths your costs" (without charter / with charter / charter saves you). Figures come from the engine (`owner_flight`), nothing recomputed in the PDF. Without owner hours: annual amounts are shown, never an invented hour count.
- Annex: heading "Not confirmed" now reads "(for a more accurate budget: <link>)" — link = `study_url` if given, otherwise `BUDGET_URL` in `menkor_report.py`.
- Management fee: the PDF (essential assumptions + annex) states what the user declared: CAMO / dispatch included in the fee (not added again), or not declared (not assumed).
- Engine: `owner_flight_indicator` extended (standalone, saving per hour, % of fixed costs covered). `TEMPLATE_VERSION` = 2.1 (old PDFs are regenerated).
- Tests: 478 OK (fake Streamlit, not a real browser). Nothing deployed.

## v24.2 — one-page PDF summary + pilot crew (13 Nov 2026)
- PDF page 1: the "Main exclusions" bullet box (split across two pages) is replaced by one line pointing to the annex, which keeps the full list. Page 1 now holds the whole summary.
- Cost Master: new "Flight crew (pilots)" block. Number + annual salary per person for pilot in command and first officer (e.g. 2 + 1). It REPLACES the reference crew expense (never added on top); both roles are required (partial entry = explicit error). Stated in the PDF annex and exclusions.
- New `Scenario.pilot_crew`; saved scenarios and comparison flag it. 483 tests OK (fake Streamlit, not a real browser).
