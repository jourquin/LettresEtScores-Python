# Lettres & Scores

Petite application graphique en Python qui recherche, à partir des lettres
fournies :

- les mots les plus longs (dix résultats par défaut) ;
- les mots ayant la plus grande valeur au Scrabble français ;
- les mots de 16 à 21 lettres utiles pour préparer un coup du Benjamin ;
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

1. Introduisez de 2 à 21 lettres dans le champ **Vos lettres**.
2. Utilisez `?` ou `*` pour représenter un joker, au maximum deux.
3. Saisissez éventuellement un ou plusieurs motifs dans le champ
   **Contraintes**.
4. Choisissez le nombre de résultats à afficher, de 1 à 20 (10 par défaut).
5. Cliquez sur **Chercher**.
6. Sélectionnez un résultat puis cliquez sur **Voir la définition**.

Les espaces, virgules, tirets et accents sont acceptés dans la saisie. Les
jokers permettent de compléter un mot mais valent zéro point.

Dans les deux listes de résultats, les mots de plus de 15 lettres apparaissent
en rouge afin de les distinguer immédiatement.

### Contraintes de recherche

Les contraintes utilisent la syntaxe courante des expressions régulières,
connue notamment par les utilisateurs de `grep`. Elles sont saisies dans un
champ distinct des lettres disponibles.

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

L'application ouvre directement `src/data/ods9.zip` au démarrage et lit le
fichier `ods9.txt` qu'il contient sans l'extraire sur le disque. L'archive
contient 416 349 formes uniques en majuscules ASCII, de 2 à 21 lettres, dont
9 221 formes de plus de 15 lettres.

Cette liste a été préparée à partir du dépôt tiers
[`Thecoolsim/ODS9`](https://github.com/Thecoolsim/ODS9). Ce dépôt n'est pas une
publication officielle de Larousse ou de la FISF et ne fournit pas de licence
de redistribution explicite. Elle ne constitue pas à
elle seule une référence homologuée pour la compétition.

## Tests

Depuis le dossier src :

```bash
python3 -m unittest discover -s tests -v
```

Le projet n'utilise aucune dépendance Python externe.

## Documentation technique

Le fonctionnement détaillé du moteur de recherche, du calcul des scores et du
classement des résultats est décrit dans [`ALGORITHME.md`](ALGORITHME.md).
