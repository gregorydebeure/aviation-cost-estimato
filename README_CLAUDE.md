# Menkor - Base v16 : 167 modèles, dont 144 PDF et 2 fiches web partielles

## Mise à jour v16

167 modèles uniques : 144 fiches PDF, 2 fiches web partielles (Global 6000 et Global 7500), 21 historiques. Les 144 anciennes fiches détaillées sont conservées sans modification. Les trois Challenger 604/605/650 étaient déjà dans la v15; les fichiers (1) reçus sont identiques octet par octet, donc aucun nouvel avion n’est ajouté pour eux.

Les deux nouvelles fiches sont des estimations web Guardian Jet avec périmètre distinct des PDF ACC, pas des rapports PDF équivalents. Le Global 7000 est un alias historique du 7500, pas une ligne supplémentaire. 2340 contrôles numériques et de complétude, 376 points REVIEW (370 antérieurs + 4 avertissements de périmètre/unité + 2 divergences de vitesse ACC).

## Fichiers

- 01_avions_details.csv : 146 lignes et 92 colonnes. Les champs de performances, coûts et hypothèses sont normalisés; les valeurs calculées et manquantes sont identifiées dans la provenance. source_model_report conserve le titre du document.
- 02_provenance_champs.csv : chaque valeur avec unité, fichier, page, statut et note. Les champs convertis conservent la valeur et l'unité avant conversion. Ces deux colonnes conservent aussi les zéros physiques invalides du 870C, avec un statut spécifique.
- 03_base_v5_preservee.csv : les 31 modèles et 11 colonnes de l'Excel initial, inchangés.
- 04_base_v16_transition.csv : 167 modèles uniques. Les valeurs historiques sont dans legacy_. Les champs détaillés sont vides pour les 21 modèles sans rapport.
- 05_controles.csv : 2340 contrôles de sommes, répétitions, unités et valeurs physiques. Les différences sont conservées avec leur tolérance.
- 06_inventaire_sources.csv : fichier source, SHA-256, pages, présence d'une galerie et champs numériques invalides/manquants.
- 07_texte_source_par_page.csv : texte des PDF avant conversions impériales, après nettoyage du codage des polices. Cette couche ne remplace pas les illustrations.
- 08_mapping_ancien_schema.csv : correspondances avec les 11 anciennes colonnes et points de vigilance.
- 09_conversions_unites.csv : conversions du Challenger 300, avec valeurs originales, valeurs normalisées, unités et formules.
- illustrations_sources/ : pages de galerie présentes dans les rapports, conservées en PNG. Les nouvelles cotes incluses dans les dessins ne sont pas transcrites automatiquement. Les dix annotations du 7X précédemment vérifiées sont conservées dans drawing_*.

## Format

CSV UTF-8 avec BOM, séparateur virgule, point décimal, aucun séparateur de milliers. Vide signifie donnée absente ou inutilisable, jamais zéro implicite. Charger identifiants et téléphones comme texte. Exemple : pandas.read_csv(path, encoding='utf-8-sig', dtype={'aircraft_id':'string', 'report_contact_phone':'string'}).

Ce dossier nécessite une migration du code : il ne remplace pas directement le fichier actuel de l'application. source_model_report est un ajout au schéma v8; les identifiants historiques sont conservés. Les deux nouvelles colonnes de provenance sont source_value_before_conversion et source_unit_before_conversion.

## Conversions impériales : Challenger 300 et trois Global

Les rapports Challenger 300, Bombardier Global 5000, Global Express et Global Express XRS sont en unités impériales. Conserver les originaux du CSV 09 et de la couche texte. Les chiffres d’exemple ci-dessous concernent le Challenger 300; les mêmes règles sont appliquées séparément aux valeurs de chaque Global. La base utilise :

- 1 US gallon = 3.785411784 L. La source imprime GAL sans préciser US; la convention US est adoptée pour ce rapport américain et reste à confirmer auprès de la source. Le prix 4.25 USD/GAL est divisé par ce facteur, la consommation 286 GAL/h et le volume 100100 GAL sont multipliés par ce facteur. Ne pas lire 4.25 comme USD/L.
- 1 lb = 0.45359237 kg.
- 1 ft = 0.3048 m; les dimensions pieds/pouces sont converties via le nombre total de pouces.
- 1 ft3 = 0.028316846592 m3.
- 1 statute mile = 1.609344 km; 1 MPH = 1.609344 km/h. Les NM et les knots restent distincts des miles et MPH.

Les valeurs normalisées conservent neuf décimales au maximum; cela n'augmente pas la précision des données d'origine. Pour reproduire le rapport, privilégier les totaux et unités d'origine. Le contrôle de cohérence NM/km peut signaler un écart causé par les arrondis indépendants des deux distances publiées.

## Challenger 870C / 870CS

Le nom du fichier indique Challenger 870C; le titre du rapport indique Bombardier/Challenger 870CS. Le modèle et aircraft_id gardent le nom du fichier, le titre reste dans source_model_report et le statut indique model_name_and_source_values_review_required. Ne pas fusionner ou renommer automatiquement cette variante sans validation.

Le PDF imprime 00 KG pour maximum takeoff weight, maximum landing weight, basic operating weight et usable fuel weight. Ces quatre valeurs sont physiquement invalides, donc les quatre champs normalisés restent vides. La provenance conserve le zéro imprimé avec invalid_source_placeholder et les quatre contrôles échouent explicitement. Ne pas substituer les masses d'un autre Challenger. Les autres données extraites de ce rapport restent disponibles avec leur provenance.

## Hypothèses et données historiques

Chaque modèle a ses propres reference_annual_hours et reference_fuel_price_usd_per_l. Les rapports contiennent notamment 0.98 USD/L, 0.99 USD/L et 4.25 USD/GAL. Aucune conversion monétaire en EUR n'a été effectuée. Les montants des rapports sont normalisés en USD depuis le symbole $; les devises historiques non explicitement EUR restent à vérifier.

Les dates des rapports/prix ne sont pas fournies. extraction_date est la date de traitement, pas une date de marché. Années de production, flotte active et valeurs moyennes d'occasion restent des informations sources non validées comme actuelles. Une année unique de production (8X : 2016) ne donne pas une année de fin. Les zéros de flotte active sont conservés comme valeurs sources et ne sont pas assimilés aux masses physiques invalides.

Les portées sièges occupés ne sont pas la portée maximale constructeur. Le prix charter, les différences de coûts charter/privé, les prix carburant par aéroport, le financement, la dépréciation et la fiscalité ne sont pas fournis par ces rapports.

La mention Powered By Aircraft Cost Calculator identifie la provenance. Cette extraction ne confirme pas les droits de redistribution commerciale de la base source; vérifier les droits applicables avant publication dans le SaaS.

## Règles pour adapter l'application avec Claude

1. Charger les 144 modèles PDF et les 2 fiches web avec leur statut distinct dans un schéma typé avec unités, devise et provenance. Les 21 autres restent legacy_not_reconstructed. Les variantes proches restent distinctes, notamment 601-1A et 601-3A, 850 et 850 CS.
2. Les totaux annual_fixed_cost_usd incluent crew expense, crew training, hangar, insurance et aircraft miscellaneous. Ne pas ajouter les coûts d'équipage une seconde fois. Pour le 7X, 588918 + 377505 = 966423, correspondant au montant observé dans l'ancien Dashboard : vérifier le risque de double comptage dans le code.
3. Les coûts variables incluent fuel, airframe maintenance, engine/APU maintenance et crew miscellaneous. Les sous-totaux et leurs composants ne se cumulent pas. Crew travel, catering, airport fees et other sont déjà des composants variables.
4. Distinguer reproduction du rapport (totaux sources aux heures de référence) et simulation personnalisée. La consommation et le prix affichés sont arrondis; leurs produits peuvent différer des totaux annuels publiés. Ne pas modifier les sources pour faire disparaître ces écarts.
5. Coût variable hors carburant horaire = (annual_variable_cost_usd - annual_fuel_cost_usd) / reference_annual_hours. Une simulation peut utiliser ce coût hors carburant, le volume consommé et un prix local explicite. Toute personnalisation d'un composant doit remplacer ce composant au lieu de le compter deux fois.
6. Séparer heures volées, heures facturées et vols de positionnement. Aucun coefficient privé arbitraire de 0.82. Séparer carburant consommé et quantité achetée à l'escale, avec unités, fournisseur, prix, devise, validité, taxes et frais.
7. Séparer devise source et devise d'affichage. Demander un taux de change daté avant affichage EUR. Une donnée absente reste indisponible. Un coût horaire à zéro heure doit être non applicable.
8. Utiliser un seul moteur entre Dashboard, Profitability, Sensitivity, Cost Master, Quotation et PDF. Invalider les résultats et PDF dès que leurs hypothèses changent. Expliquer contribution horaire, seuil de rentabilité et taux de couverture.
9. Reprendre les 2340 contrôles et les alertes sources, avec les tolérances documentées. Les 4 contrôles de masses invalides du 870C doivent rester visibles. Le champ review_count compte les contrôles numériques, pas la divergence de nom à traiter séparément.
10. Comparer les résultats avant/après migration et revoir les changements avant déploiement. Ce dossier met à jour la base, pas le site.

## Continuité des mises à jour

Le doublon 7X(1) déjà identifié est toujours exclu des modèles. Le fichier 20C-5 contient un espace avant .pdf; le nom du modèle est normalisé sans modifier la provenance. Les nouvelles extensions .Pdf sont reconnues sans distinction de casse. Les lots suivants doivent être rapprochés par aircraft_id et source_model_report. Préserver legacy_ et ne pas compter une fiche enrichie comme un nouvel avion.

## Particularités du lot v10

- Les 19 nouveaux modèles sont CJ1, CJ2, CJ2+, CJ3, CJ3+, CJ4, Encore, Excel, III, Latitude, Mustang, Sovereign, Bravo, Jet, V Ultra, I/ISP, Global 5000, Global Express et Global Express XRS.
- Les identifiants des variantes + emploient le suffixe _plus. cessna_citation_cj2 et cessna_citation_cj2_plus sont distincts, comme cj3 et cj3_plus. Ne pas supprimer le signe + avant de créer l'identifiant.
- Les trois Global sont normalisés avec le constructeur Bombardier, conformément au titre de leur rapport. Le fichier et son titre original sont conservés séparément.
- Le fichier cessna Citation SP.pdf porte le titre Cessna Citation I/ISP. Le modèle conserve ce libellé combiné et le statut model_name_review_required. Ne pas conclure qu'il s'agit exclusivement d'un ISP ni le fusionner avec une autre variante sans validation.
- Les trois Global ont été convertis depuis GAL, LBS, pieds/pouces, ft3, SM et MPH. GAL est interprété comme US gallon, convention à confirmer auprès de la source. Tous les originaux et formules sont consignés dans 09_conversions_unites.csv.
- Les hypothèses propres à chaque rapport sont conservées, notamment 250 ou 350 h/an et 0.99, 1.12 USD/L ou 4.25 USD/GAL. Ne pas imposer un prix carburant commun lors de l'import.
- Les différences de casse des fichiers Cessna sont normalisées dans les noms de modèles. Elles ne modifient pas les fichiers sources ni la provenance.

## Particularités du lot v11

Le rapport ERJ-170LR indique un prix moyen d'occasion de 0 USD. La base normalisée laisse average_preowned_price_usd vide et conserve le zéro source dans la provenance avec invalid_source_placeholder. Le statut est source_values_review_required. Ne pas utiliser zéro comme valeur d'acquisition ni inventer une estimation de remplacement. Les coûts d'exploitation et performances du rapport restent disponibles.

Les rapports Dornier 328, ERJ-145ER et ERJ-170LR utilisent 100 h/an. Les autres rapports de ce lot ont leurs propres hypothèses (250 ou 350 h/an) : lire reference_annual_hours, sans imposer la même valeur à tous les avions. Les différences de coûts entre Dornier 328 et 328 Business ne doivent pas être effacées ni considérées comme de simples effets du nombre de sièges.

Le nom Embraer LEGACY 600 est normalisé en Embraer Legacy 600, conformément au titre du rapport. Les espaces avant .pdf de Legacy 450 et Phenom 100 sont supprimés du nom du modèle, mais conservés dans source_file. Les variantes XLS/XLS+, Phenom 100/100EV, Lineage 1000/1000E, Eclipse 500/550 et Dornier 328/328 Business restent distinctes. Les signes + restent encodés dans les identifiants par _plus.

Les cinq premières pièces de ce lot (Cirrus, Dornier et Eclipse) n'avaient pas encore été intégrées à la v10. Chacune est donc ajoutée une seule fois. Pour les prochains lots, rapprocher par identifiant, titre et empreinte du fichier avant ajout ou remplacement.

Le rapport ERJ-170LR indique « 2001 - to present » pour les années de production. L’année de fin reste vide et la mention du rapport est conservée dans la provenance; elle ne confirme pas une production actuelle en 2026.

## Particularités du lot v12 et conflit G450

Les nouvelles fiches couvrent Praetor 600, Flaris LAR01, Fokker 100ER, Gulfstream G100, G150, G200, G280, G300, G350, G400, G450, les deux G500, G550, G650, G650ER, II B, II B Hushkit et II Hushkit.

Gulfstream G500 (2003-2012 Model) et Gulfstream G500 gardent des identifiants distincts. Les variantes Hushkit restent distinctes. Les noms ne garantissent pas qu'un rapport corresponde à la génération actuellement commercialisée; conserver source_model_report, production_start_report et les hypothèses historiques.

G450.pdf et Gulfstream G450.Pdf décrivent le même modèle avec des montants différents. La fiche principale utilise provisoirement Gulfstream G450.Pdf selon son nom explicite, sans prétendre que cette source est plus récente ou plus exacte. Son statut est source_conflict_review_required. Le fichier 10_conflits_sources_G450.csv contient toutes les différences de champs; la provenance, les contrôles et le texte source conservent les deux versions intégrales séparées par source_file. Ne pas agréger les deux ni les importer comme deux avions. Ne pas interpréter leur différence monétaire comme un taux de change validé. Vérifier la devise et la date auprès de la source avant usage commercial.

Les fichiers 02, 05, 06 et 07 décrivent désormais 145 versions PDF sources pour 144 avions PDF, plus 2 scénarios web économiques et leurs références techniques ACC. Toujours joindre la provenance et les contrôles par aircraft_id ET source_file pour ne pas mélanger les deux G450. source_role dans l'inventaire identifie la version alternate. review_count de la fiche principale ne compte que ses propres contrôles numériques, pas les conflits intersources.

Les montants G450 sont : acquisition 21 469 766 / 24 570 000, budget annuel 1 759 142 / 2 013 162 (source principale / alternative). Les montants restent étiquetés USD d'après le symbole imprimé, sans conversion EUR.

## Particularités du lot v13

Ajout des 12 Hawker : 400XP, 400XPR, 700, 750, 800A, 800SP, 800XP, 800XPi, 850XP, 900XP, 1000 et 4000; des 7 Gulfstream II, II SP, II SP Hushkit, III, IV, IVSP et V; et du Honda HondaJet.

Ces variantes conservent des identifiants distincts. Le nom Hawker 800XPI est normalisé en Hawker 800XPi conformément au titre du rapport, sans modifier le nom du fichier source. L'espace final du fichier Gulfstream II SP .Pdf est retiré du nom normalisé et conservé dans source_file. Le constructeur est Hawker ou Honda selon le titre; aucune attribution automatique à Bombardier.

Tous ces nouveaux rapports expriment les volumes de carburant en litres. Les hypothèses propres à chaque avion, les périodes de production et les coûts imprimés restent conservés. Ils ne sont pas assimilés à des prix de marché actuels. Le conflit des deux sources G450 reste conservé dans le fichier 10 et dans la provenance.

## Particularités du lot v14

Ajout de 15 Learjet : 31, 31A, 31AER, 35A, 36A, 40, 40XR, 45, 45XR, 55, 55C, 60, 60XR, 70 et 75. Les quatre IAI sont 1123 Commodore Jet, Astra SP, Westwind 1 et Westwind 2. Les variantes conservent chacune un identifiant distinct; aucune fusion XR, A ou ER.

Le fichier IAI Westwing 2.Pdf porte le titre IAI Westwind 2 : le nom et aircraft_id sont normalisés en Westwind 2 conformément au document; le nom du fichier reste intact dans source_file. L’espace final du fichier IAI Astra SP .Pdf reste également conservé dans source_file.

Le constructeur est normalisé IAI pour ces quatre rapports et Bombardier pour la gamme Learjet; model et source_model_report conservent Learjet. Cette classification de gamme ne constitue pas une histoire des constructeurs successifs. Tous les nouveaux rapports utilisent le litre pour le carburant. Les hypothèses historiques restent spécifiques à chaque rapport. Le conflit G450 et toutes les alertes antérieures restent conservés.

## Particularités du lot v15

Six modèles ajoutés : Lockheed Jetstar II/731, Mitsubishi Diamond 1A, Nextant 400XT, Nextant 400XTi, Pilatus PC-24 et Sabreliner Sabre 65. Les deux Nextant gardent des identifiants distincts.

Les fichiers Mitsubishi Diamond 1A.Pdf et Mitsubishi Diamond 1A (1).Pdf sont identiques octet par octet (SHA-256 851647c55aadae9c5c322d29bc8f756116f5c452b01f5405ad6f610ef9008448). La copie (1) est exclue de l’extraction et du comptage; le nom original est conservé comme source de la fiche unique.

Lockheed Jetstar II_731 est normalisé en Lockheed Jetstar II/731 selon le titre du rapport; le fichier source conserve son nom. Le rapport combine II/731 : cette fiche ne permet pas de créer deux variantes séparées. Tous les nouveaux rapports utilisent les litres pour le carburant. Les noms des cinq constructeurs sont normalisés depuis les titres, sans attribution à Bombardier. Les coûts et hypothèses restent historiques et propres à chaque rapport. Le conflit G450 et les alertes antérieures sont préservés.

Le rapport Lockheed Jetstar II/731 imprime un prix moyen d’occasion de 0 USD. Le champ normalisé est laissé vide, avec le zéro source et le statut invalid_source_placeholder conservés dans la provenance. Aucune estimation de remplacement n’est inventée.

## Intégration v16 pour Claude — à lire en priorité

1. Challenger 604, 605 et 650 existent déjà dans 01 et 04, IDs challenger_604, challenger_605 et challenger_650. Leur suppression dans la migration est une erreur de chargement ou de rapprochement, pas un manque de PDF. 13_Challenger_pour_Claude.csv fournit ces trois lignes complètes pour diagnostic, sans les réimporter une deuxième fois.
2. 11_complements_web_Global.csv donne les URL et les catégories originales des nouvelles fiches. Date de consultation : 2026-10-18; validité effective inconnue. USD supposé depuis $. US gallon supposé pour cette source américaine. Ne pas masquer ces hypothèses.
3. 12_aliases_modeles.csv rattache Global 7000 à bombardier_global_7500. Le moteur doit résoudre cet alias avant la sélection et ne pas compter deux avions.
4. Les deux scénarios Guardian Jet utilisent 300 h/an et 7.54 USD/gallon. Les totaux, le carburant et la maintenance proviennent de ce seul scénario. Ne pas mélanger avec les totaux ACC en ligne (autres heures, hypothèses et valeurs). Les coûts fixes de Guardian Jet diffèrent fortement des anciens rapports : afficher la source et permettre validation opérateur, sans les déclarer équivalents à ACC.
5. La rubrique Crew est agrégée; le traitement de la formation n’est pas documenté. annual_crew_training_fixed_usd reste vide. Ne pas compléter avec zéro et ne pas ajouter de formation générique. Maintenance moyenne sur cinq ans et programme moteurs sont distincts; la ventilation cellule/APU/crew miscellaneous ACC reste vide. Le moteur doit calculer le coût global depuis les totaux, sans exiger que toutes les sous-catégories ACC soient renseignées. Les modifications de composants ne sont possibles que si leur périmètre est connu; une modification remplace le poste, jamais un ajout au total.
6. Les coûts et volumes annuels carburant sont dérivés de la consommation, du prix et de 300 h : ils ne sont pas présentés comme montants annuels imprimés. Les formules et conversions sont tracées dans 02 et 09. Le coût carburant horaire conserve les centimes calculés; l’affichage web est arrondi au dollar.
7. Les portées sièges occupés/ferry, dimensions cabine, plafond, passagers et distances publiées dans les résumés ACC publics sont intégrés avec une provenance distincte des coûts Guardian Jet. Les masses et les vitesses normales contradictoires restent vides. Une portée commerciale constructeur ne remplace pas seats_full_range_nm. Les fiches web sont donc utilisables comme scénarios économiques indicatifs, avec limites visibles, pas comme fiches techniques complètes ni outils de préparation du vol.
8. 07_texte_source_par_page.csv et les illustrations restent réservés aux PDF. Aucune page HTML complète n’est recopiée. Les URL, faits chiffrés, unités et catégories utiles sont conservés dans 11 et la provenance; le schéma existant de 01/04 reste inchangé (92 colonnes détaillées).

Source primaire pour le changement de nom : GE Aerospace, « Passport, Catalyst making news at EBACE », 29 mai 2018, https://www.geaerospace.com/news/articles/product/passport-catalyst-making-news-ebace.

## fuel_regional_benchmarks.csv (separate from the aircraft base)
Weekly regional jet fuel benchmarks, IATA Fuel Price Monitor (Platts data, published under licence from S&P Global Energy). Week ending 2026-10-09.
`price_us_cents_per_us_gallon` is the source figure; the application computes USD/L = cents / 100 / 3.785411784 at full precision (3 decimals displayed only).
These are REFINERY market benchmarks, not into-wing prices: no regional mark-up is added. Not a real-time feed, not an annual average, not a forecast.
The licence/terms of use were not reviewed: automated or commercial redistribution is NOT cleared. Update with `tools/update_fuel_benchmarks.py`.
