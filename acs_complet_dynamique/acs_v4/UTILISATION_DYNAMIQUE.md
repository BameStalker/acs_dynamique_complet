# Script complet ACS — intégration dynamique des actifs

## Lancer (Python 3.9+, sans bibliothèque externe pour les CSV)

Depuis ce dossier :

```bash
python acs_dynamique.py calculer
```

**Ajouter un nouvel actif** :

```bash
python acs_dynamique.py ajouter --nom srv-app-02 --type "Serveur applicatif" --source cloud --source-id vm-9001 --c 6 --i 8 --a 8 --voisins "web-01,db-prod,srv-ad"
```

Le script met à jour l'inventaire et les relations CSV, puis recalcule **tous** les scores. Résultats : `results/acs_dynamique.csv` et `results/variations_acs.csv`.

**Éviter de modifier les données de démonstration** : copiez les CSV dans un autre dossier et utilisez les options `--inventaire chemin.csv --relations chemin.csv` **avant** `ajouter` ou `calculer` :

```bash
python acs_dynamique.py --inventaire data/mon_inventaire.csv --relations data/mes_relations.csv ajouter --nom srv-app-02 --source cloud --source-id vm-9001 --voisins "web-01"
```

Les colonnes d'inventaire sont : `nom,type,source,source_id,evenements_count,confidentialite,integrite,disponibilite,topologie`. Les relations sont des paires `source,cible` désignant **les noms d'actifs** (pas le champ `source` de l'inventaire).

## Modèle

- `ACS=0.35*C+0.25*I+0.20*A+0.20*T`.
- `T=1+9*degre/(n-1)` pour `n>1`; si `n=1`, `T=1`.
- Un nouvel actif modifie les degrés et le dénominateur ; les scores de tous les actifs sont recalculés.
- Les valeurs C/I/A renseignées priment sur les profils par type. Ces profils sont **illustratifs** et nécessitent une validation métier.
- La comparaison par fréquence (`freq_rang_normalise`) est un **proxy**, pas l'algorithme exact de Kotenko.

## Limites

- Pas de découverte réseau ou ingestion en continu : lancement à chaque nouvelle observation.
- Déduplication exacte par `(source, source_id)` ; si `source_id` absent, repli sur `(source, nom)` (fragile en cas de renommage).
- Graphe non orienté et non pondéré, fondé sur des relations renseignées.
- Le script recalcule tout le graphe, ce qui est cohérent pour une expérience mais non optimisé pour un grand parc.
- Ne pas modifier simultanément les CSV depuis plusieurs processus : pas de transaction multi-fichiers ni de verrouillage.
- Les étiquettes d'évaluation livrées dans le projet sont illustratives, non indépendantes.
