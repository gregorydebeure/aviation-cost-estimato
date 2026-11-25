# Vente, acceptation des conditions, preuves et documents — mise en service (v29)

**Rien n'est déployé.** Tout est éteint par défaut : tant que `LEGAL_FLOW_ENABLED` n'est pas à `1`, l'app se comporte exactement comme avant. Les textes légaux sont des **projets non validés par un avocat** (`status: draft`) : ils ne sont affichés au public que lorsqu'ils sont publiés **et** que toutes les informations vendeur sont renseignées.

## 1. Ce que j'ai trouvé dans l'existant
- **Comptes** : table `users` (Supabase), e-mail + mot de passe haché. Aucune acceptation de conditions à l'inscription.
- **4 chemins de paiement indépendants**, chacun créait sa session Stripe lui-même : abonnement Pro (prix Stripe `STRIPE_PRICE_PRO`), packs d'accès 29 / 59 / 15 € (paiement unique), annonce d'avion 15 €/mois (abonnement), Market Search 600 € (v30 : en euros, montant à confirmer) (paiement unique, e-mail saisi à la main, sans compte).
- **Offres réellement configurées** (lues dans le code, pas retapées) : Budget individuel 29 €, Pack Comparaison 59 € (14 jours), Modèle supplémentaire 15 €, Menkor Pro 79 €/mois (10 nouveaux modèles par mois), Annonce 15 €/mois, Market Search 600 € (v30 : en euros, montant à confirmer). Le « budget d'un avion précis » (dès 490 €) n'a **pas** de paiement en ligne : demande sur devis. Le prix Stripe réel du Pro n'est vérifiable que par l'app au moment de la commande (voir §5).
- **Pas de webhook** : l'app lit Stripe côté serveur (à la connexion, au retour de paiement, toutes les 5 minutes). Le test `tests/webhook_logic.test.mjs` du dépôt mentionne une fonction `supabase/functions/stripe-webhook` et l'offre Essentiel : je n'ai pas ce dossier ; à vérifier de votre côté qu'il n'est plus déployé.
- **Aucune page légale**, aucun pied de page légal. Le pied de page dit « Menkor Aviation GBL » dans les PDF (question « LTD » toujours ouverte).
- **Google Analytics 4** est intégré (`menkor_analytics.py`, « consent first » d'après son commentaire). Je n'ai pas ce fichier ici : je n'ai pas pu vérifier qu'il existe un vrai contrôle de consentement.

## 2. Ce qui a été construit
- **Un seul point d'entrée** pour créer un paiement Stripe (`_stripe_checkout`). Avec le flux activé, il **refuse** tout paiement sans commande enregistrée **avec son acceptation enregistrée** (vérification serveur dans Supabase, pas d'état d'écran). Les 4 anciens chemins y passent ; un test vérifie qu'aucune autre ligne du code ne crée de session Stripe.
- **Parcours de commande** (au-dessus des onglets, depuis chaque bouton d'achat) : Particulier / Professionnel, coordonnées de facturation (TVA/identifiant fiscal facultatif), récapitulatif complet (offre, contenu, durée, règles de crédits, prix, devise, taxes, total, ponctuel ou récurrent, renouvellement, résiliation), documents ouverts dans un nouvel onglet **et** lisibles sur place, case d'acceptation **non cochée**, cases séparées d'exécution immédiate pour les particuliers (non cochées), marketing facultatif et séparé. Français / anglais.
- **Preuve d'acceptation** (3 tables, `legal_migration.sql`) : identifiant client (e-mail), commande, date UTC, langue, version, copie du texte (par empreinte SHA-256, stockée une fois, jamais modifiée), libellé accepté, offre / montant / devise / modalités, références Stripe, demandes d'exécution immédiate, date de fin de conservation. Des déclencheurs SQL interdisent toute modification ; la suppression n'est possible qu'après la date de conservation. Accessible uniquement par la clé serveur (RLS sans politique).
- **Cohérence des montants** : le total affiché, la commande, les paramètres envoyés à Stripe et la session payée sont comparés ; un écart bloque le paiement ou l'activation. Pour le Pro, l'app relit le prix Stripe configuré et refuse s'il diffère de 79 € / mois.
- **Activation seulement après lecture serveur du paiement** (le retour navigateur ne prouve rien), de façon **idempotente** (une session rejouée ne crée ni double commande, ni double crédit, ni double e-mail). Un paiement échoué ou inachevé n'active rien. Une session créée hors du parcours (ancien lien de paiement) n'ouvre aucun accès ; un abonnement Pro souscrit après `LEGAL_FLOW_STARTED_AT` sans commande acceptée n'est pas reconnu (les abonnés existants avant cette date restent Pro).
- **Factures** : générées par Stripe (abonnements : natif ; paiements uniques : `invoice_creation`), une seule série. L'app ne crée aucune facture elle-même, n'en modifie aucune. Corrections et remboursements : note de crédit / remboursement dans Stripe ; l'app les affiche.
- **E-mail de confirmation** (un seul par commande) : offre, montant, devise, période, lien facture, lien « Mes achats et documents », informations de résiliation et de rétractation, **PDF joint** des conditions réellement acceptées + preuve + documents d'information.
- **« 🧾 My purchases and documents »** (bouton dans la barre latérale) : commandes, statut, dates d'accès, abonnement et prochaine échéance, factures et notes de crédit Stripe, PDF des conditions acceptées, remboursements, résiliation en fin de période (uniquement de ses propres abonnements). Tout est filtré par l'e-mail du compte dans la requête.
- **Pages publiques** `?legal=terms|withdrawal|notice|privacy|cookies&lang=fr|en` (sans connexion, PDF téléchargeable avec version et date d'entrée en vigueur), liens au pied de page, à l'inscription et dans la commande. **Inscription gratuite** : case « Conditions d'utilisation » obligatoire, preuve enregistrée **avant** la création du compte.
- **Calculs de coûts : non modifiés.** `menkor_access.py` et `menkor_market.py` : un paramètre optionnel ajouté (`allowed_order_ids`, sans effet s'il est absent).

## 3. Informations qu'il me faut (une seule liste)
Je n'ai rien inventé : tant que ces points manquent, les textes ne peuvent pas être publiés et la commande reste bloquée.

| # | Information | Variable Render |
|---|---|---|
| 1 | Dénomination légale de la société vendeuse (GBL ou LTD ?) | `LEGAL_SELLER_NAME` |
| 2 | Pays d'immatriculation | `LEGAL_SELLER_COUNTRY` |
| 3 | Adresse | `LEGAL_SELLER_ADDRESS` |
| 4 | Numéro d'immatriculation | `LEGAL_SELLER_REG_NUMBER` |
| 5 | Identifiant fiscal pertinent (TVA / tax ID) **ou la mention exacte à imprimer s'il n'y en a pas** | `LEGAL_SELLER_TAX_ID` |
| 6 | E-mail de contact | `LEGAL_CONTACT_EMAIL` |
| 7 | E-mail de réclamation | `LEGAL_COMPLAINTS_EMAIL` |
| 8 | Marchés ciblés (texte imprimé dans les conditions) | `LEGAL_MARKETS` |
| 9 | Droit applicable (texte imprimé) | `LEGAL_GOVERNING_LAW` |
| 10 | Tribunaux compétents (texte imprimé) | `LEGAL_COURTS` |
| 11 | Politique de remboursement : packs, abonnement mensuel entamé, annonce, Market Search / budget (avant et après le début du travail), délais | `LEGAL_REFUND_POLICY` |
| 12 | Politique de résiliation (au-delà de « fin de période payée ») | `LEGAL_CANCELLATION_POLICY` |
| 13 | Taxes : prix TTC / HT / non applicable, et la phrase exacte à afficher avec les prix ; mode `included`, `stripe_tax` ou `not_applicable` | `LEGAL_TAX_NOTE`, `LEGAL_TAX_MODE` |
| 14 | Hébergeur : nom et adresse | `LEGAL_HOST_DETAILS` |
| 15 | Durée de conservation des commandes, preuves et factures (années) | `LEGAL_RETENTION_YEARS` |
| 16 | Date d'entrée en vigueur des textes publiés | dans chaque fichier `legal/*.md` (`effective:`) ou `LEGAL_EFFECTIVE_DATE` |
| 17 | Clients Pro existants : comment les informer des nouvelles conditions | décision |
| 18 | Google Analytics : confirmer qu'un vrai consentement existe (sinon bandeau à ajouter) | décision |

## 4. Mise en service — dans cet ordre, sans rien casser
1. Uploader dans le dépôt (racine + dossier `legal/`) : `app.py`, `menkor_legal.py`, `menkor_orders.py`, `menkor_access.py`, `menkor_market.py`, `legal/` (10 textes + `MANIFEST.json`), `legal_migration.sql`, `LEGAL_SETUP.md`, `CHANGES_v20.md` ; tests facultatifs dans `tests/`. **Effet : aucun** tant que le flux est éteint.
2. Supabase → SQL editor : exécuter **une fois** `legal_migration.sql` (4 tables). C'est vous qui l'exécutez.
3. **Répétition en mode test Stripe** (recommandé, sans vrai paiement) : sur une copie de l'app (ou temporairement), `STRIPE_SECRET_KEY` = clé `sk_test_…`, `STRIPE_PRICE_PRO` = prix test 79 €/mois, variables `LEGAL_*` avec des valeurs d'essai, `LEGAL_FLOW_ENABLED=1`, `LEGAL_FLOW_STARTED_AT` = date/heure ISO du jour (ex. `2026-12-01T00:00:00Z`). Avec une clé de test, les textes en `draft` sont acceptés pour la répétition ; **avec une clé live, jamais**. Carte test `4242 4242 4242 4242`.
4. Production : renseigner les variables du §3, passer les 10 textes en `status: published` avec la date d'entrée en vigueur **après relecture juridique**, puis `LEGAL_FLOW_ENABLED=1` et `LEGAL_FLOW_STARTED_AT`. Retour arrière immédiat : `LEGAL_FLOW_ENABLED=0`.
5. Panneau admin « ⚖ Legal documents & orders (status) » : liste ce qui manque encore et affiche un aperçu des brouillons.
6. Nouvelle version d'un texte : modifier le fichier, **augmenter `version:`**, mettre à jour `legal/MANIFEST.json` (un test refuse un texte modifié sous la même version). Les anciennes commandes gardent leur texte d'origine.

## 5. À configurer chez Stripe
1. **Paramètres de l'entreprise** : nom légal, adresse, e-mail de support (ils figurent sur les factures).
2. **Factures** : numérotation (préfixe / séquence), identifiant fiscal du vendeur dans « Account tax IDs », pied de page, conditions de paiement. Vérifier sur un paiement test qu'un **paiement unique** (pack) produit bien une facture avec PDF.
3. **Taxes** : choisir selon le §3 point 13. Si `stripe_tax` : activer Stripe Tax, enregistrer les juridictions, régler le « tax behavior » du prix Pro en cohérence ; sinon, prix « tout compris » et la phrase du point 13.
4. **Prix Pro** : `STRIPE_PRICE_PRO` doit être 79 EUR / mois récurrent (l'app refuse la commande sinon).
5. **Désactiver** tout *Payment Link*, *Pricing Table* ou *Buy button* existant dans Stripe : ils contournent l'acceptation (l'app n'activerait rien, mais le client paierait sans accès).
6. **E-mails Stripe** (Paramètres → E-mails) : décider si les reçus Stripe restent actifs en plus de notre confirmation. Ils sont utiles tant qu'il n'y a pas de webhook (notre e-mail part quand l'app lit le paiement).
7. **Abonnements** : relances de paiement échoué et délai avant annulation ; rappels de renouvellement si votre droit l'impose.
8. **Remboursement / correction** : toujours depuis Stripe (remboursement ; **note de crédit** pour une facture finalisée, jamais de modification). L'app affiche remboursements et notes de crédit.
9. **E-mail (Resend)** : domaine d'expédition vérifié (`EMAIL_FROM`), les pièces jointes PDF doivent être autorisées.
10. Plus tard (non construit) : un webhook (`checkout.session.completed`, `invoice.paid`, `charge.refunded`, `customer.subscription.updated/deleted`) supprimerait le délai de lecture.

## 6. Résultats des vérifications
Environnement : faux Streamlit, faux Supabase, faux Stripe ; aucun réseau, aucun e-mail, aucun paiement réel. **Ce n'est pas une validation dans un vrai navigateur ni contre le vrai Stripe.**
- **92 nouveaux tests, tous réussis** (`test_legal` 16, `test_orders` 39, `test_orders_app` 37) ; les 63 tests accès / marketplace / prix qui tournent ici sont toujours réussis.
- Suite complète avant / après mes changements : **mêmes 132 échecs des deux côtés** (données et modules du dépôt absents de mon environnement), **aucun échec nouveau**.

| Point demandé | Vérifié par |
|---|---|
| Paiement impossible sans acceptation (côté serveur) | refus sans `terms=True`, libellé exact, bouton sans case → aucune commande ni session Stripe |
| Case non précochée | aucun `value=True` dans le code, cases remises à zéro à chaque commande |
| Pas de contournement par lien direct | les 4 anciennes fonctions refusent sans commande ; une seule fonction crée des sessions (analyse du code) ; commande sans acceptation non payable ; session hors parcours = aucun accès |
| Bonne version des conditions | texte modifié après coup : l'ancienne commande garde sa copie et son empreinte ; modification SQL refusée |
| Cohérence du prix | montants lus dans le code des accès ; paramètres Stripe falsifiés refusés ; prix Stripe du Pro comparé ; session payée de montant différent → pas d'activation |
| Paiement échoué sans activation | session inachevée / impayée / expirée |
| Événements répétés | rejeux sans changement, un seul e-mail, pas de double crédit |
| Confidentialité | autre e-mail : commande, preuve, documents, annulation refusés ; factures filtrées par client Stripe |
| Particulier et professionnel | les deux parcours, TVA facultative, raison sociale exigée pour un pro, boîtes d'exécution immédiate seulement pour les particuliers |
| Renouvellement, résiliation, remboursement | prochaine échéance, résiliation de son propre abonnement seulement, remboursement partiel / total tracé sans réécriture |
| Anglais / français | libellés exacts, récapitulatif et e-mail dans les deux langues |

**Non vérifié** : affichage sur mobile et dans un vrai navigateur ; appels réels à Stripe (paramètres `tax_id_collection`, `customer_update`, `custom_text`, `invoice_creation` à confirmer lors de la répétition en mode test) ; envoi réel d'une pièce jointe par Resend ; `st.radio(index=None)` demande Streamlit ≥ 1.29 (à vérifier dans `requirements.txt`) ; défilement vers le haut à l'ouverture de la commande (script JavaScript, non testé).

## 7. Clauses à faire valider par un juriste (je n'ai fixé aucun droit applicable)
1. Rétractation des particuliers : formulation générale (« si votre droit vous la reconnaît »), mention de l'Union européenne donnée seulement en exemple ; exigence **obligatoire** de la demande d'exécution immédiate pour les particuliers (réglable : `IMMEDIATE_REQUIRED_FOR_CONSUMERS` dans `menkor_orders.py`) ; traitement d'un client professionnel.
2. Modification des conditions pour un abonnement en cours (notification avant application, droit de résilier).
3. Licence et interdictions (extraction massive, redistribution, remplacement de modèles) selon les pays ciblés et les droits sur les bases de données.
4. Limitation de responsabilité ; droit applicable et tribunaux face aux règles impératives des consommateurs.
5. Durée de conservation, transferts hors de votre pays (Stripe, Supabase, Resend, hébergeur, Google), contenu de la politique de confidentialité.
6. Annonces d'avions : rôle d'intermédiaire et responsabilité sur les contenus des annonces.
7. Reconduction automatique des abonnements : informations et rappels exigés selon les pays.
8. Cookies et Google Analytics : consentement.

## 8. Points ouverts et limites connues
- **Sans webhook**, l'activation, l'e-mail de confirmation et la facture dans « Mes achats » apparaissent quand l'app lit Stripe (retour de paiement, prochaine visite, toutes les 5 minutes). Un client qui paie puis ne revient pas reçoit d'abord le reçu / la facture Stripe, et notre e-mail à sa prochaine visite.
- Un **remboursement n'enlève pas** automatiquement l'accès (décision commerciale à prendre) ; il est tracé.
- **Clients Pro existants** : ils gardent l'accès (abonnement antérieur à `LEGAL_FLOW_STARTED_AT`) mais n'ont pas accepté les nouvelles conditions : à traiter (point 17).
- **Suppression** après la durée de conservation : autorisée par la base mais **pas automatisée**.
- Market Search pour un visiteur sans compte : la commande est liée à l'e-mail saisi ; il reçoit la confirmation et la facture Stripe par e-mail, mais ne peut pas ouvrir « Mes achats » sans compte.
- Le pied de page des PDF existants (« Menkor Aviation GBL ») n'est pas modifié.
