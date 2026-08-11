# Lexique embarqué

L’application attend `lexique-francais.zip` dans ce répertoire. L’archive
contient un membre unique nommé `lexique-francais.txt`, encodé en ASCII, avec
une forme normalisée par ligne.

Le moteur ouvre le ZIP et lit ce membre directement en mémoire au démarrage :
aucun fichier n’est extrait sur le disque.

## Contenu

- 402 448 formes uniques ;
- caractères `A` à `Z` uniquement ;
- longueurs de 2 à 15 lettres ;
- tri alphabétique strict ;
- SHA-256 du texte :
  `ac58f8941544d0ef759a8b234d46aac4262cbf25af35f33b1d1916575c06c737` ;
- SHA-256 de l’archive :
  `977df4fb0f2451ef161a8f4892413b794ff87ade4afaceac455587e0362cc1e5`.

## Origine et statut

Le lexique est dérivé de
[Morphalou 3.1](https://hdl.handle.net/11403/morphalou/v3.1), conçu par Marie
Tonnelier et maintenu par l’ATILF (CNRS et Université de Lorraine). Il est
distribué sous LGPL-LR.

Les règles de sélection, la provenance, les empreintes et les instructions de
régénération sont documentées dans [`../../Corpus/README.md`](../../Corpus/README.md).
La notice et le texte complet de la licence se trouvent également dans
`Corpus/`.

Cette liste n’est ni une reproduction de l’ODS ni une référence officielle
pour les compétitions.
