# Corpus multisource corroboré — candidat 0.1.0

Le fichier `src/data/lexique-francais-multisources.zip` est un **corpus
candidat** construit à partir du lexique Morphalou actuel et de quatre
ressources lexicales ouvertes. Il n'est pas encore utilisé par défaut par
l'application.

Le générateur ne consulte jamais l'ODS. Il conserve les 402 448 formes du
corpus Morphalou puis ajoute uniquement une forme absente de ce socle lorsqu'au
moins **deux sources externes distinctes** la corroborent après filtrage et
normalisation.

## Résultat de la construction de contrôle

| Mesure | Valeur |
|---|---:|
| Formes du socle Morphalou | 402 448 |
| Candidats externes absents du socle | 238 263 |
| Ajouts corroborés par au moins deux sources | 33 695 |
| Formes finales | 436 143 |
| SHA-256 du texte lexical | `a7f4d66f7813ece515ab60c525aeb99683267bd9e7b34f23bb5eed6c59be271e` |
| SHA-256 de l'archive ZIP | `0a8d90819d6b06ec17b2d3f1394ef949e37ebaacf8a6f55085e6f9b9418586fe` |

À titre d'évaluation **postérieure** à la construction, ce corpus contient
11 796 des 57 197 formes ODS9 de 2 à 15 lettres absentes du corpus actuel,
soit 20,62 %. L'ODS n'est pas une entrée du générateur et cette comparaison
n'a sélectionné aucun mot.

## Sources figées

| Source | Version | Licence déclarée | Fichier attendu | SHA-256 |
|---|---|---|---|---|
| [Lefff](https://almanach.inria.fr/software_and_resources/Alexina-en.html) | 3.4 | CeCILL-L | `lefff-3.4.mlex` | `f3da25e58aec161c5ae34d598038dd6304056c2649867ede7e220a74fd34fe12` |
| [Unitex DELA français](https://github.com/UnitexGramLab/unitex-lingua/tree/master/fr) | commit `70d73c571038e1a19ad9d77e77ab6d29e6c8ce82` | LGPL-LR | `Dela_fr.dic` décompressé | `6b69cc832e81f345ddd43e41704a47c53348e6a1f10cc1dfc09a19796064aafa` |
| [Grammalecte](https://grammalecte.net/) | dictionnaire 7.5, paquet `dictionary-fr` 3.0.0 | MPL-2.0 | `index.aff` | `05a735d34c912e4e381ff08ee7c747923ccf5cf9dca81d8467982fa1ca51c2b7` |
| Grammalecte | même version | MPL-2.0 | `index.dic` | `984e933237bc1224a48f42828233be9b03228260ef67aa8e2bdddcd03a26230d` |
| [Lexique](https://www.lexique.org/databases/Lexique383/) | 3.83 | CC BY-SA 4.0 | `Lexique383.txt` | `fe2cb931f774d4c44abb92fa785a8425b74f668373012ad22e3980fb1bfea0de` |

Le script refuse une source dont l'empreinte diffère. Une mise à jour de
version doit donc être explicite : examen de la nouvelle licence et du format,
adaptation éventuelle du lecteur, mise à jour de l'empreinte, tests, puis
nouvelle version du corpus.

## Règles de validation automatisée

Les lecteurs propres à chaque source appliquent les règles suivantes avant la
corroboration :

1. exclusion des noms propres explicitement marqués par Lefff ou Unitex ;
2. exclusion des catégories techniques, préfixes et ponctuations ;
3. pour Hunspell, expansion des flexions puis exclusion des entrées marquées
   `KEEPCASE`, `NOSUGGEST` ou interdites ;
4. pour Lexique 3.83, conservation des catégories lexicales explicites ;
5. rejet des locutions, apostrophes, traits d'union, chiffres et formes
   ponctuées ;
6. développement de `œ` en `OE` et de `æ` en `AE`, suppression des
   diacritiques et conversion en majuscules ;
7. conservation exclusive des chaînes `A-Z` de 2 à 15 lettres ;
8. ajout au socle seulement si au moins deux ressources externes distinctes
   contiennent la forme normalisée ;
9. dédoublonnage et tri ASCII strict.

Le fichier [MULTISOURCE-PROVENANCE.tsv](MULTISOURCE-PROVENANCE.tsv) indique,
pour chacune des 33 695 formes ajoutées, le nombre d'attestations et les
sources correspondantes. Le rapport
[MULTISOURCE-BUILD-REPORT.json](MULTISOURCE-BUILD-REPORT.json) conserve les
versions, empreintes, statistiques de rejet, combinaisons de sources et
empreintes des sorties.

## Construction

Le script utilise uniquement la bibliothèque standard de Python. Par défaut,
une seule commande suffit :

```bash
python3 Tools/build_multisource_lexicon.py
```

Les quatre distributions figées sont téléchargées si nécessaire, leur
SHA-256 est vérifié, puis les membres utiles sont extraits dans
`.cache/lexical-sources/`. Lors des exécutions suivantes, les fichiers valides
de ce cache sont réutilisés. Le cache n'est pas versionné.

Le lecteur Unitex parcourt directement les fichiers officiels `Dela_fr.bin` et
`Dela_fr.inf` : l'installation ou la compilation d'Unitex n'est pas requise.
Les fichiers Grammalecte sont extraits du paquet npm
`dictionary-fr@3.0.0`.

Il reste possible de fournir toutes les ressources manuellement :

```bash
python3 Tools/build_multisource_lexicon.py \
  --lefff /sources/lefff-3.4.mlex \
  --unitex-bin /sources/Dela_fr.bin \
  --unitex-inf /sources/Dela_fr.inf \
  --grammalecte-aff /sources/index.aff \
  --grammalecte-dic /sources/index.dic \
  --lexique383 /sources/Lexique383.txt
```

L'ancien mode `--unitex /sources/Dela_fr.dic` reste accepté pour un fichier
préalablement décompressé par Unitex et encodé en UTF-16. Tout fichier fourni
manuellement est soumis à la même vérification SHA-256.

Pour construire sans aucun accès réseau :

```bash
python3 Tools/build_multisource_lexicon.py --no-download
```

Dans ce mode, toutes les sources non fournies explicitement doivent déjà être
présentes et valides dans le cache. Son emplacement peut être changé avec
`--sources-cache /chemin/du/cache`.

Les sorties par défaut sont :

- `src/data/lexique-francais-multisources.zip`, compatible avec le format lu
  par le moteur ;
- `Corpus/MULTISOURCE-PROVENANCE.tsv`, audit mot par mot ;
- `Corpus/MULTISOURCE-BUILD-REPORT.json`, manifeste reproductible ;
- `Corpus/MULTISOURCE-NOTICE.txt`, attribution synthétique.

Leur intégrité se contrôle sans relire les sources :

```bash
python3 Tools/build_multisource_lexicon.py --check
```

Les tests se lancent avec :

```bash
python3 -m unittest discover -s Tools/tests -v
PYTHONPATH=src python3 -m unittest discover -s src/tests -v
```

## Pourquoi le statut reste « candidat »

Deux attestations ne constituent pas une preuve linguistique absolue. Des
ressources peuvent partager des données en amont, un nom propre peut ne pas
être marqué comme tel et une expansion morphologique peut produire une forme
rare ou discutable. Le TSV de provenance est destiné à une révision
éditoriale, notamment par échantillonnage et par analyse des combinaisons de
deux sources.

La validation réalisée par le script est **technique et éditoriale**, pas
juridique. Le corpus combiné fait intervenir LGPL-LR, CeCILL-L, MPL-2.0 et CC
BY-SA 4.0. Avant de remplacer le corpus courant dans une distribution
publique, il faut confirmer les conditions applicables au corpus agrégé,
conserver les textes de licence et attributions nécessaires et vérifier les
obligations de partage à l'identique. Cette documentation ne constitue pas un
avis juridique.
