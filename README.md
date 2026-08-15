# Lettres & Scores

Petite application graphique en Python qui recherche, à partir des lettres
fournies :

- les mots les plus longs (dix résultats par défaut) ;
- les mots ayant la plus grande valeur au Scrabble français ;
- la présence d’un mot dans le corpus local ;
- la définition d'un mot sélectionné, lorsque l'ordinateur est connecté à
  Internet.

## Lancement

Prérequis : **Python 3.10 ou plus récent**, avec Tkinter.

### Windows

Double-cliquez sur `lancer_windows.bat`, ou ouvrez un terminal dans le dossier :

```powershell
py -3 src\app.py
```

### macOS

Dans le Terminal :

```bash
python3 src/app.py
```

Tkinter est normalement fourni avec l'installateur Python de python.org.

### Linux

Dans un terminal :

```bash
./lancer_macos_linux.sh
```

Si Tkinter manque sous Debian ou Ubuntu :

```bash
sudo apt install python3-tk
```

Si Tkinter manque sous RH ou Fedora :

```bash
sudo dnf install python3-tkinter
```

### Choix du corpus

Sans option, l’application charge `src/data/lexique-francais.zip`. L’option
`--corpus` permet de sélectionner une autre archive compatible, par exemple le
corpus multisource candidat :

```bash
python3 src/app.py \
  --corpus src/data/lexique-francais-multisources.zip
```

Sous Windows :

```powershell
py -3 src\app.py --corpus src\data\lexique-francais-multisources.zip
```

Les scripts de lancement transmettent également leurs arguments :

```bash
./lancer_macos_linux.sh \
  --corpus src/data/lexique-francais-multisources.zip
```

Le chemin peut désigner toute archive ZIP contenant un membre
`lexique-francais.txt` au format décrit dans `src/data/README.md`. Un chemin
relatif est interprété depuis le dossier courant.

## Utilisation

1. Introduisez de 2 à 15 lettres dans le champ **Vos lettres**.
2. Utilisez `?` ou `*` pour représenter un joker, au maximum deux.
3. Saisissez éventuellement un ou plusieurs motifs dans le champ
   **Contraintes**.
4. Choisissez le nombre de résultats à afficher, de 1 à 20 (10 par défaut).
5. Cliquez sur **Chercher**.
6. Sélectionnez un résultat puis cliquez sur **Voir la définition**.

Les espaces, virgules, tirets et accents sont acceptés dans la saisie. Les
jokers permettent de compléter un mot mais valent zéro point.

Pour vérifier un mot, laissez **Vos lettres** vide, saisissez le mot entier
dans **Contraintes**, puis cliquez sur **Vérifier**. Dans ce mode, le contenu
est interprété littéralement et non comme une expression régulière. La réponse
indique seulement si la forme figure dans le corpus actif ; elle ne
constitue pas une validation officielle pour une compétition.

### Contraintes de recherche

Les contraintes utilisent la syntaxe courante des expressions régulières,
connue notamment par les utilisateurs de `grep`. Elles sont saisies dans un
champ distinct des lettres disponibles. Elles jouent ce rôle uniquement
lorsque le champ **Vos lettres** contient un tirage ; lorsque celui-ci est vide,
le même champ sert à vérifier un mot exact.

| Motif | Signification |
| --- | --- |
| `a` | le mot doit contenir un `A` |
| `^a` | le mot doit commencer par `A` |
| `e$` | le mot doit se terminer par `E` |
| `^..r` | `R` doit être la troisième lettre |
| `u.$` | `U` doit être l'avant-dernière lettre |
| `^....$` | le mot doit contenir exactement quatre lettres |
| `^.e..$` | le mot doit contenir quatre lettres et la deuxième doit être `E` |
| `^.{5,7}$` | le mot doit contenir entre cinq et sept lettres |
| `^j.r.*a$` | le mot commence par `J`, contient `R` en troisième position et finit par `A` |

Les principaux symboles sont `^` pour le début du mot, `$` pour la fin, `.`
pour exactement une lettre quelconque et `.*` pour zéro ou plusieurs lettres.
Les barres obliques parfois utilisées pour présenter une expression régulière
ne doivent pas être saisies.

Plusieurs motifs peuvent être séparés par un point-virgule. Ils doivent alors
tous correspondre. Les deux saisies suivantes sont donc équivalentes :

```text
^j ; ^..r ; a$
^j.r.*a$
```

Avec les lettres `a, j, u, r, f, o, a`, ces contraintes trouvent notamment
`JURA`.

Une contrainte filtre les résultats, mais n'ajoute jamais de lettre au tirage.
Ainsi, le motif `^c` ne permet de former `CHAT` que si un `C` ou un joker figure
aussi dans le champ **Vos lettres**. Les motifs sont insensibles à la casse.
Une expression invalide est signalée avant le lancement de la recherche.

Le bouton **?**, situé à droite du champ **Contraintes**, ouvre une aide
intégrée qui reprend les principaux symboles et une série d'exemples. Il n'est
donc pas nécessaire de consulter ce fichier pendant l'utilisation du jeu.

## À propos et licences

Le bouton **À propos / Licences** ouvre une fenêtre à onglets défilables qui
présente la version de l’application, le nom du corpus actif, sa provenance,
sa notice et les informations de licence disponibles. Elle fournit également
les liens vers Morphalou et vers la forme modifiable du corpus.

## Règles de calcul

L'application applique la valeur française des lettres :

- 1 point : A, E, I, L, N, O, R, S, T, U ;
- 2 points : D, G, M ;
- 3 points : B, C, P ;
- 4 points : F, H, V ;
- 8 points : J, Q ;
- 10 points : K, W, X, Y, Z.

Les bonus du plateau et la prime de 50 points ne sont pas appliqués, car
l'application ne connaît ni la grille ni les lettres déjà posées.

## Définitions

La recherche de mots fonctionne entièrement hors ligne. Une requête n'est
envoyée au Wiktionnaire français que lorsque vous demandez explicitement une
définition. Comme la liste de jeu est dépourvue d'accents, la forme affichée par
le Wiktionnaire peut rétablir une graphie accentuée.

En cas de problème réseau, l'application effectue plusieurs tentatives et
affiche la cause détectée (délai dépassé, erreur HTTP, certificat SSL, proxy,
etc.). Elle peut ensuite ouvrir une recherche directe dans le navigateur.

La barre située en bas à gauche est un indicateur d'activité : elle apparaît
uniquement pendant le chargement, une recherche de mots ou une demande de
définition. Elle ne représente ni un pourcentage ni le nombre de mots chargés.

Les définitions sont fournies au mieux : certains mots rares ou certaines
formes conjuguées peuvent ne pas disposer d'une définition directement
extractible. Le bouton ouvrant la page source reste disponible lorsqu'une
définition est trouvée. Les extraits consultés sur le Wiktionnaire restent
disponibles sous CC BY-SA 4.0, sauf mention contraire ; ils ne sont pas inclus
dans le corpus local.

## Données, licence et limites

Par défaut, l’application ouvre directement
`src/data/lexique-francais.zip` et lit son membre
`lexique-francais.txt` sans l’extraire sur le disque. Le moteur indexe alors
402 448 formes uniques en majuscules ASCII, de 2 à 15 lettres. L’option
`--corpus` permet de charger une autre archive compatible, notamment
`src/data/lexique-francais-multisources.zip`, qui contient 436 143 formes.

Le corpus a été construit à partir de
[Morphalou 3.1](https://hdl.handle.net/11403/morphalou/v3.1), conçu par Marie
Tonnelier et maintenu par l’ATILF (CNRS et Université de Lorraine). Les formes
ont été filtrées, normalisées, dédoublonnées et triées selon la méthode décrite
dans [`Corpus/README.md`](Corpus/README.md). Le corpus dérivé reste distribué
sous LGPL-LR ; sa [notice](Corpus/NOTICE.txt), sa
[licence](Corpus/LICENSE-Morphalou-LGPL-LR.txt) et son
[rapport de construction](Corpus/BUILD-REPORT.json) sont fournis dans le dépôt.

La licence MIT à la racine couvre le code de l’application, pas le corpus. Le
lexique n’est ni une reproduction de l’ODS ni une référence officielle ou
homologuée pour les compétitions. Les résultats sont fournis sans garantie
d’exhaustivité ni d’exactitude.

## Régénération du corpus

Le générateur n’utilise que la bibliothèque standard de Python :

```bash
python3 Tools/build_open_lexicon.py
```

Il télécharge une version figée de Morphalou, contrôle son SHA-256 et régénère
l’archive, la notice, la licence et le rapport. Pour contrôler les fichiers
déjà présents sans téléchargement ni modification :

```bash
python3 Tools/build_open_lexicon.py --check
```

Le corpus multisource candidat se construit ensuite avec :

```bash
python3 Tools/build_multisource_lexicon.py
```

Ce second générateur télécharge ou réutilise dans son cache Lefff, Unitex
DELA, Grammalecte et Lexique 3.83, vérifie leurs empreintes et produit le
corpus ainsi que son rapport et son fichier de provenance. La procédure
détaillée figure dans
[`Corpus/MULTISOURCE-README.md`](Corpus/MULTISOURCE-README.md).

## Tests

Depuis la racine du dépôt :

```bash
PYTHONPATH=src python3 -m unittest discover -s src/tests -v
```

Depuis la racine, les tests du générateur se lancent avec :

```bash
python3 -m unittest discover -s Tools/tests -v
```

Le projet n'utilise aucune dépendance Python externe.

## Documentation technique

Le fonctionnement détaillé du moteur de recherche, du calcul des scores et du
classement des résultats est décrit dans [`ALGORITHME.md`](ALGORITHME.md).
