# Corpus français ouvert

L’application embarque un lexique de **402 448 formes** construit à partir de Morphalou 3.1. Cette ressource remplace l’ancienne liste dérivée de l’ODS9. Elle est indépendante de l’ODS et ne doit pas être présentée comme un lexique officiel de Scrabble ou de compétition.

## Source et licence

| Élément | Valeur |
|---|---|
| Ressource source | Morphalou 3.1 |
| Auteur institutionnel de la citation | ATILF |
| Conception | Marie Tonnelier |
| Dépôt canonique | [ORTOLANG — Morphalou 3.1](https://hdl.handle.net/11403/morphalou/v3.1) |
| Version de dépôt utilisée | `morphalou/4` |
| Date de la documentation des données | juin 2016 |
| Année indiquée par la citation ORTOLANG | 2023 |
| Licence | LGPL-LR |
| SHA-256 de l’archive source | `4fc815cbf17aecdf1b47f6bbc263489a460fd8d11ae17e6b522336c72bd0e333` |

Morphalou 3.1 est un lexique morphologique ouvert du français maintenu par l’ATILF. Il réunit plusieurs lexiques et associe à chaque forme fléchie la liste de ses lexiques d’origine. La ressource source annonce 159 271 lemmes et 976 570 formes fléchies.

Le corpus dérivé reste distribué sous **LGPL-LR**. Le texte complet reproduit depuis la documentation de Morphalou se trouve dans [LICENSE-Morphalou-LGPL-LR.txt](LICENSE-Morphalou-LGPL-LR.txt). La provenance et les modifications sont résumées dans [NOTICE.txt](NOTICE.txt), tandis que les paramètres et empreintes figurent dans [BUILD-REPORT.json](BUILD-REPORT.json).

La licence MIT à la racine du dépôt couvre le code de Lettres & Scores. Elle ne remplace pas la LGPL-LR applicable au corpus dérivé.

Citation recommandée par la fiche de la ressource :

```bibtex
@misc{11403/morphalou/v3.1,
  title = {Morphalou},
  author = {ATILF},
  url = {https://hdl.handle.net/11403/morphalou/v3.1},
  note = {ORTOLANG (Open Resources and TOols for LANGuage)},
  copyright = {Licence Publique Générale Amoindrie GNU
               pour les Ressources linguistiques},
  year = {2023}
}
```

### Redistribution

Pour redistribuer l’application ou le corpus, il faut au minimum conserver les notices, fournir la LGPL-LR et maintenir l’accès à la forme modifiable de la ressource et à sa chaîne de génération. Ce dépôt remplit ces objectifs en publiant la ressource lexicale non chiffrée, le script, le rapport, la notice et la licence.

La licence doit néanmoins être relue par le responsable de toute distribution publique, notamment pour vérifier la compatibilité des conditions de la plateforme de diffusion avec la LGPL-LR. La documentation technique du dépôt facilite cette vérification mais ne constitue pas un avis juridique.

## Règles de construction

Le script ne consulte jamais l’ODS, ni pendant la sélection ni pendant la validation. Il traite uniquement la colonne des formes fléchies du CSV de Morphalou et applique les règles suivantes, dans cet ordre :

1. conserver les catégories lexicales explicites suivantes : adjectif qualificatif, adverbe, conjonction, déterminant, interjection, nom commun, nombre, préposition, pronom et verbe ;
2. exclure les entrées portant la sous-catégorie `abréviation` ;
3. exiger que la forme soit attestée par au moins deux lexiques d’origine dans les métadonnées de Morphalou ;
4. rejeter toute forme contenant un espace, un signe de ponctuation, un trait d’union, une apostrophe, un chiffre ou un autre séparateur ;
5. développer `œ` en `OE` et `æ` en `AE`, supprimer les diacritiques et convertir en majuscules ;
6. ne conserver que les formes composées des lettres `A` à `Z` et longues de 2 à 15 lettres ;
7. supprimer les doublons puis trier selon l’ordre ASCII.

L’exigence de deux lexiques d’origine est un filtre de corroboration, pas une règle linguistique universelle. Elle réduit les entrées isolées et produit un corpus adapté à l’usage de l’application, mais elle peut exclure des mots français valides. Inversement, une forme présente dans le corpus n’est pas nécessairement admise dans un règlement de jeu particulier.

## Résultat de la version 1.0.0

| Mesure | Valeur |
|---|---:|
| Lignes source lues | 976 570 |
| Lignes acceptées avant dédoublonnage | 557 239 |
| Doublons supprimés | 154 791 |
| Formes uniques | 402 448 |
| SHA-256 de `lexique-francais.txt` | `ac58f8941544d0ef759a8b234d46aac4262cbf25af35f33b1d1916575c06c737` |
| SHA-256 de `lexique-francais.zip` | `977df4fb0f2451ef161a8f4892413b794ff87ade4afaceac455587e0362cc1e5` |

Les statistiques détaillées et les paramètres lisibles par machine figurent dans [BUILD-REPORT.json](BUILD-REPORT.json).

## Régénération

Prérequis : Python 3.10 ou ultérieur, sans paquet externe.

Depuis la racine du dépôt :

```bash
python3 Tools/build_open_lexicon.py
```

Le script :

- télécharge l’archive versionnée depuis ORTOLANG dans un dossier temporaire ;
- refuse de continuer si son SHA-256 diffère de l’empreinte attendue ;
- génère `src/data/lexique-francais.zip` ;
- extrait la LGPL-LR dans `Corpus/LICENSE-Morphalou-LGPL-LR.txt` ;
- actualise la notice dans `Corpus/NOTICE.txt` ;
- actualise `Corpus/BUILD-REPORT.json`.

Pour reconstruire hors ligne à partir d’une archive déjà téléchargée :

```bash
python3 Tools/build_open_lexicon.py \
  --source-archive /chemin/vers/Morphalou3.1_formatCSV_toutEnUn.zip
```

Pour contrôler la ressource déjà générée sans téléchargement ni modification :

```bash
python3 Tools/build_open_lexicon.py --check
```

Ce contrôle ouvre l’archive en mémoire, vérifie le format de chaque forme,
l’ordre, l’unicité, le nombre de mots et les empreintes enregistrées dans
`Corpus/BUILD-REPORT.json`.

Le script fixe l’ordre des formes, le nom du membre, son horodatage, ses permissions et le niveau de compression. La version 1.0.0 a été produite avec Python 3.12.13 et zlib 1.3.1. Une autre version de zlib peut théoriquement modifier l’empreinte de l’archive ; l’empreinte du contenu texte permet alors de vérifier que le contenu lexical est identique.

## Format de la ressource embarquée

`src/data/lexique-francais.zip` est une archive ZIP contenant un seul membre nommé `lexique-francais.txt`. Celui-ci contient une forme normalisée par ligne, encodée en ASCII, avec un retour à la ligne final.

L’application le lit directement avec `zipfile.ZipFile`, sans extraction sur le disque. La notice, la licence et le manifeste lisible par machine restent séparés dans `Corpus/` afin d’être consultables directement dans le dépôt et depuis la fenêtre « À propos / Licences ».

Le CSV source de 105 Mo n’est pas versionné : il peut être retéléchargé et son empreinte est contrôlée à chaque construction.

## Validation

Les tests du générateur se lancent avec :

```bash
python3 -m unittest discover -s Tools/tests -v
```

Ils vérifient la normalisation, les rejets principaux, la reproductibilité de l’archive ZIP et sa relecture. Les tests du moteur Python vérifient séparément le chargement direct de la ressource, la recherche et la vérification exacte d’un mot.
