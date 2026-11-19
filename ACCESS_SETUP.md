# Accès par modèle (v26) — mise en service

Règles validées : Budget individuel 29 € (1 modèle) · Pack Comparaison 59 € (3 modèles) · **14 jours** · modèles modifiables pendant la période · rapports déjà téléchargés conservés · un second pack **s'ajoute** (ne prolonge pas) · Pro 79 €/mois = **10 nouveaux modèles par mois**, non reportés, modèles débloqués conservés tant que Pro est actif · modèle supplémentaire **15 €** (Pro : +1 dans le mois ; pack : +1 pour 14 jours) · Essentiel (15 €/mois) inchangé : tous les modèles.

Garde-fou ajouté (non demandé) : au plus 3 modèles remplacés par 24 h (constante `MAX_MODEL_CHANGES_PER_24H` dans `menkor_access.py`), pour éviter de parcourir toute la base pendant un pack.

## Ordre de mise en service (rien n'est actif tant que l'étape 4 n'est pas faite)
1. Uploader à la racine du dépôt : `app.py`, `menkor_access.py`, `model_access_migration.sql`, `CHANGES_v20.md` (tests facultatifs). Le comportement ne change pas : l'interrupteur est éteint.
2. Dans Supabase (SQL editor), exécuter une fois `model_access_migration.sql` (3 tables, lecture interdite à la clé publique).
3. Vérifier que Render a déjà `STRIPE_SECRET_KEY` et les accès Supabase (déjà le cas).
4. Allumer : variable Render `ACCESS_RULES_ENABLED` = `1`. Retour arrière immédiat : la supprimer ou la mettre à `0`.

## Nettoyage Essentiel (v27)
- Stripe : archiver le produit « Essentiel » (ne pas supprimer). Render : supprimer la variable `STRIPE_PRICE_ESSENTIEL`.

## À savoir avant d'allumer
- Les abonnés Pro actuels n'ont aucun modèle débloqué au départ : ils auront 10 nouveaux modèles le mois de l'activation. Prévenez-les, ou débloquez-leur à la main des lignes dans `access_pro_unlocks` (email, aircraft_id, month = AAAA-MM).
- Le paiement n'a pas de webhook : l'app interroge Stripe à la connexion, toutes les 5 minutes et au bouton « Refresh my purchases ». Un paiement n'ouvre un droit que s'il est payé, du bon montant en EUR, créé par l'app et au même e-mail.
- Non couvert : l'onglet « Compare with similar aircraft » du tableau de bord montre toujours 3 modèles proches de la même catégorie (coûts moyens). Les scénarios sauvegardés et dossiers clients ne sont pas filtrés par modèle. Le PDF « comparatif » utilise les modèles débloqués via la liste filtrée.
- Les tests de l'app utilisent un faux Streamlit : ce n'est pas une validation dans un vrai navigateur. Faire un achat test en Stripe mode test avant d'allumer.
