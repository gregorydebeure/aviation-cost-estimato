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
