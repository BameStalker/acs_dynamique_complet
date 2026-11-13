# ACS v4 — prototype expérimental reproductible

## Corrections apportées à v3

1. **Poids cohérents** : configuration par défaut identique à v3 (0,35/0,25/0,20/0,20), vérification stricte de la somme.
2. **Valeurs DIC** : profils explicites, priorité donnée aux valeurs renseignées individuellement ; le profil sauvegarde a une disponibilité de **9**, choix de scénario à valider par des experts.
3. **Topologie** : calcul réel de la centralité de degré depuis `relations_synthetiques.csv` (relations non orientées) ; si aucun graphe, la valeur `T` fournie est utilisée ; sinon `T=5` neutre, plutôt qu'un score topologique inventé par type.
4. **Identité** : identifiant UUIDv5 stable par `(source,source_id)` et déduplication exacte ; repli par nom au sein de la source, **fragile en cas de renommage**. Pas de fusion automatique inter-sources ni de résolution probabiliste.
5. **Fréquences** : les comptes absents restent absents, et le classement par fréquence est désactivé plutôt que d'imputer arbitrairement 1 000 événements.
6. **Comparaison** : le modèle `freq_rang_normalise` est **un proxy simplifié** de classement des fréquences, **pas une reproduction certifiée de Kotenko**.
7. **Évaluation** : précision/rappel/F1 sur une référence CSV externe ; le fichier fourni est **illustratif et NON indépendant**. Les métriques ne constituent **pas** une validation scientifique.
8. **Sensibilité** : comparaison de trois pondérations et export dédié.
9. **Tests** : 9 tests unitaires exécutés.

## Exécution

Python 3.9+ ; aucune dépendance pour les CSV.

```bash
python acs_v4.py data/inventaire_synthetique.csv --relations data/relations_synthetiques.csv --sensibilite --sortie results/resultats_acs_v4.csv
python acs_v4.py data/inventaire_synthetique.csv --relations data/relations_synthetiques.csv --reference data/reference_illustrative_NON_INDEPENDANTE.csv --sortie results/resultats_acs_v4.csv
python -m unittest discover -s tests -v
```

Pour les fichiers Excel : `pip install pandas openpyxl` puis `python acs_v4.py inventaire.xlsx`.

### Colonnes

Inventaire : `nom,type,source,source_id,evenements_count,confidentialite,integrite,disponibilite,topologie` (dernières colonnes optionnelles). Les données `C,I,A` manquantes sont complétées par profils. Les identifiants source sont fortement recommandés.

Relations : `source,cible` avec noms d'actifs, interprétées comme des **liens non orientés** pour le calcul du degré.

Référence : `nom,critique_reelle` avec `0` ou `1` ; établir les étiquettes sans accès aux résultats ACS.

### Réserves scientifiques

- Les données et les relations livrées sont synthétiques. Le jeu de référence est construit pour illustrer le fonctionnement, pas pour mesurer l'exactitude en situation réelle.
- Les résultats de référence (ACS F1=1,00 ; fréquence F1=0,60) sont **illustratifs et non généralisables** ; ils diffèrent des chiffres d'un prototype antérieur car les données, le graphe et le protocole ont été modifiés.
- L'analyse de centralité ne distingue pas encore les relations « dépend de », « communique avec » ou « héberge » ; elle doit être enrichie de relations orientées et pondérées.
- L'ajout d'actifs est supporté en rechargeant l'inventaire complet et les relations ; il n'existe pas encore de service temps réel ni de persistance transactionnelle.
- Les scores DIC issus des profils et les poids doivent être validés par des experts et testés en sensibilité.
- Les seuils `ACS>=6` et `rang_freq>=0.6` sont préfixés pour la démonstration ; il faut calibrer équitablement les seuils dans une expérience indépendante.
