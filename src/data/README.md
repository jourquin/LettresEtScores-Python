# Liste de mots utilisée par l'application

L'application attend une archive nommée `ods9.zip` dans ce répertoire. Elle
doit contenir un fichier unique nommé `ods9.txt`, encodé en UTF-8, avec un mot
par ligne.

Le moteur ouvre le ZIP et lit ce fichier directement en mémoire au démarrage :
il ne décompresse rien sur le disque. Les mots de plus de 15 lettres restent
dans l'archive, mais ne sont pas chargés par l'application.

## Contenu attendu

- 416 349 mots uniques ;
- caractères `A` à `Z` uniquement ;
- longueurs de 2 à 21 lettres ;
- 9 221 mots de 16 à 21 lettres ;
- tri alphabétique.

Après filtrage, le moteur indexe 407 128 mots de 2 à 15 lettres, conformément
au contenu de la version papier de l'ODS 9.

## Origine et statut

L'archive fournie séparément a été préparée à partir du fichier `words.js` du
dépôt tiers [`Thecoolsim/ODS9`](https://github.com/Thecoolsim/ODS9), puis
normalisée en un mot par ligne.

Ce dépôt n'est pas une publication officielle de Larousse ou de la FISF et ne
contient pas de licence de redistribution explicite. La liste ne constitue pas
à elle seule une référence homologuée pour la compétition.

