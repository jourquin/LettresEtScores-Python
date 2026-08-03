# Lettres & Scores

Petite application graphique en Python qui recherche, à partir des lettres
fournies :

- les mots les plus longs (trois résultats par défaut) ;
- les mots ayant la plus grande valeur au Scrabble français ;
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

## Utilisation

1. Introduisez de 2 à 15 lettres.
2. Utilisez `?` ou `*` pour représenter un joker, au maximum deux.
3. Choisissez le nombre de résultats à afficher, de 1 à 20 (3 par défaut).
4. Cliquez sur **Chercher**.
5. Sélectionnez un résultat puis cliquez sur **Voir la définition**.

Les espaces, virgules, tirets et accents sont acceptés dans la saisie. Les
jokers permettent de compléter un mot mais valent zéro point.

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
définition est trouvée.

## Données et limites

Le fichier `data/mots_francais_jeu.txt` contient 311 721 formes. Il s'agit d'une
liste approchante pour jeu de lettres, pas d'une copie officielle de l'ODS et
pas d'une référence homologuée pour la compétition. La licence du corpus
général est fournie dans `LICENSE_SOURCE.txt`.

## Tests

Depuis le dossier src :

```bash
python3 -m unittest discover -s tests -v
```

Le projet n'utilise aucune dépendance Python externe.

## Documentation technique

Le fonctionnement détaillé du moteur de recherche, du calcul des scores et du
classement des résultats est décrit dans [`ALGORITHME.md`](ALGORITHME.md).
