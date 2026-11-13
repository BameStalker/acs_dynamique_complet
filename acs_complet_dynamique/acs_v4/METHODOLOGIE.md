# Méthodologie — version rédigée pour le mémoire

## 3.1 Objectif et hypothèse

La démarche proposée vise à évaluer si une mesure multicritère de la criticité des actifs informatiques peut identifier des ressources importantes mais peu sollicitées, contrairement à un indicateur fondé sur leur fréquence d'apparition dans les journaux d'événements. Le travail distingue la construction du modèle, son implémentation et sa validation expérimentale. L'hypothèse à tester est qu'un score combinant les impacts de confidentialité, d'intégrité et de disponibilité avec l'importance structurelle d'un actif améliore l'identification des actifs prioritaires, lorsque la référence est établie indépendamment des scores du modèle.

## 3.2 Représentation et intégration des actifs

À l'instant t, l'inventaire est représenté par un ensemble V_t d'actifs. Chaque actif est associé à un identifiant stable. Dans le prototype, cet identifiant est dérivé du couple (source, identifiant de source), au moyen d'un UUIDv5. Deux observations portant le même identifiant sont consolidées. Lorsque cet identifiant manque, le nom de l'actif est utilisé dans la source considérée ; ce repli n'est pas robuste à un renommage. Les cas de correspondance incertaine entre sources doivent être soumis à une résolution d'identité supplémentaire avant toute fusion. Lorsqu'un nouvel actif est ajouté, l'ensemble devient V_(t+1)=V_t ∪ {a_new}, puis les relations et les scores sont recalculés. Le prototype réalise ce traitement par réexécution sur l'inventaire mis à jour et ne constitue pas un service d'ingestion temps réel.

## 3.3 Construction des critères

Les dimensions C, I et A mesurent les conséquences de la divulgation, de l'altération et de l'indisponibilité d'un actif. Elles sont évaluées sur une échelle de 1 à 10. Dans la version initiale, ces scores sont renseignés par un expert ou attribués par une grille de profils de rôle. Les profils sont des hypothèses de départ et ne remplacent pas une analyse d'impact métier. Pour éviter de présenter comme observée une information qui ne l'est pas, le système conserve la distinction entre valeurs explicites et valeurs inférées par profil.

L'infrastructure est modélisée par un graphe G_t=(V_t,E_t). Pour cette version, les relations sont considérées non orientées. La centralité de degré normalisée d'un actif i est d_i/(|V_t|-1), pour |V_t|>1. La transformation T_i=1+9 d_i/(|V_t|-1) fournit une note topologique sur [1,10]. Lorsque |V_t|=1, T_i=1. L'ajout d'un actif peut modifier le dénominateur et donc la centralité d'autres actifs, même sans modification de leurs voisins. Une version future devra distinguer dépendances métier et communications techniques, éventuellement par un graphe orienté et pondéré.

## 3.4 Formule ACS et pondération

Pour chaque actif i, ACS_i=w_C C_i+w_I I_i+w_A A_i+w_T T_i, avec w_k≥0 et somme(w_k)=1. Les scores C, I, A et T appartenant à [1,10], ACS_i appartient aussi à [1,10]. La pondération de référence de l'implémentation est (0,35;0,25;0,20;0,20). Elle n'est pas présentée comme issue d'une norme : elle doit être soumise à une validation métier et à une analyse de sensibilité. Trois scénarios sont produits : uniforme (0,25;0,25;0,25;0,25), confidentialité privilégiée (0,35;0,25;0,20;0,20), disponibilité privilégiée (0,20;0,20;0,40;0,20).

## 3.5 Comparateur fondé sur la fréquence

Le prototype calcule, à titre exploratoire, μ_i=E_i/Σ_j E_j et classe les nombres d'événements distincts par ordre croissant. Le rang normalisé r_i/L, où L désigne le nombre de niveaux distincts, sert de comparateur. Cette construction est une **simplification inspirée de l'idée d'une importance fondée sur l'activité** ; elle ne reproduit pas nécessairement le modèle de Kotenko et al. La comparaison avec cet article devra être reformulée et vérifiée sur la base de ses définitions et de son unité d'analyse (types d'objets versus instances).

## 3.6 Protocole d'évaluation

Un jeu de données synthétique de huit actifs permet de vérifier les opérations et de tester des cas particuliers (PKI peu active, sauvegarde, contrôleur de domaine, poste utilisateur). Les résultats illustratifs sont générés par le script. La validation scientifique ultérieure nécessitera un jeu d'observations indépendant, une qualification des actifs par des évaluateurs aveugles aux scores, et une séparation entre la phase de définition des poids/seuils et la phase de test. Une classification binaire critique/non critique sera alors évaluée par précision, rappel et F1 ; des analyses complémentaires examineront les rangs et la stabilité du classement sous différentes pondérations.

## 3.7 Limites et reproductibilité

Les résultats produits par le jeu de données fourni n'établissent pas la supériorité d'ACS. Les profils, le choix des actifs, les dépendances et les étiquettes de référence sont construits à des fins de démonstration. La centralité de degré mesure une connectivité, non une criticité métier démontrée. La résolution d'identité inter-sources, les dépendances dirigées et la validation externe constituent des étapes ultérieures. Le code, les données et les tests sont joints afin de rendre les calculs reproductibles.
