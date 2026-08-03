# Liste approchante de mots français pour jeu de lettres

Cette archive contient **311 721 formes uniques**, en majuscules, utilisables
comme point de départ pour un jeu de lettres en français.

Attention : il ne s'agit **pas** d'une copie de l'Officiel du Scrabble (ODS),
ni d'une liste homologuée pour la compétition. Les formes de 4 à 15 lettres
proviennent d'un lexique général et peuvent donc contenir quelques faux
positifs ou omettre certains mots admis par l'ODS.

## Fichiers

- `mots_francais_jeu.txt` : un mot par ligne, sans en-tête.
- `mots_francais_jeu.csv` : colonnes `word,length`, avec en-tête.
- `LICENSE_SOURCE.txt` : licence MIT du corpus général utilisé.

Les deux fichiers de données sont encodés en UTF-8, avec fins de ligne LF.

## Sources utilisées

La liste a été construite à partir des sources suivantes :

1. **`an-array-of-french-words`, version 2.0.0** — corpus général d'environ
   336 000 formes françaises, utilisé pour produire les mots de 4 à 15 lettres.
   Le paquet est distribué sous licence MIT et indique être dérivé de la liste
   de mots du jeu Letterpress.
   - Paquet : https://www.npmjs.com/package/an-array-of-french-words/v/2.0.0
   - Dépôt : https://github.com/words/an-array-of-french-words
2. **Fiche « Mots de 2 et 3 lettres » de Nonuple-Scrabble**, mise à jour en
   février 2024 — utilisée pour établir les 81 mots de deux lettres et les
   639 mots de trois lettres conformes à l'ODS 9.
   - https://antigonedesassociations.montpellier.fr/sites/default/files/documents_telecharges/_fiche_nonuple_02_ods9_mots_de_2_et_3_lettres.pdf
3. **Fédération Française de Scrabble — liste exhaustive des mots de deux
   lettres conforme à l'ODS 9** — utilisée comme source de contrôle pour les
   mots de deux lettres.
   - https://www.ffsc.fr/initiation.php?page=mots-2-lettres

La présence d'une source liée à l'ODS pour les mots courts ne rend pas
l'ensemble de cette liste conforme à l'ODS : les formes de 4 à 15 lettres
restent issues d'un lexique général ouvert.

## Méthode de construction

- extraction des mots de 2 et 3 lettres depuis la fiche publique ODS 9 ;
- extraction des mots de 4 à 15 lettres depuis le corpus général ;
- application des règles de normalisation décrites ci-dessous ;
- dédoublonnage, tri et contrôle du nombre de formes par longueur ;
- génération des versions TXT et CSV, puis vérification de leurs empreintes.

## Création assistée par ChatGPT

Cette liste et ses fichiers d'accompagnement ont été préparés avec l'aide de
**ChatGPT, un outil d'intelligence artificielle développé par OpenAI**.
ChatGPT a notamment aidé à rechercher et documenter les sources, à écrire les
scripts de traitement, à appliquer les règles de normalisation, à effectuer
les contrôles techniques et à produire les fichiers TXT, CSV et README.

ChatGPT n'est pas une source lexicographique : les données lexicales proviennent
des sources énumérées ci-dessus. La liste demeure une ressource approchante et
doit être vérifiée séparément avant tout usage exigeant une conformité stricte
à l'ODS.

## Normalisation

- caractères limités à `A`–`Z` ;
- accents retirés (`É` devient `E`) ;
- ligatures développées (`Œ` devient `OE`, `Æ` devient `AE`) ;
- mots de 2 à 15 lettres seulement ;
- mots avec espace, apostrophe ou trait d'union exclus, sans concaténation ;
- dédoublonnage après normalisation ;
- tri alphabétique.

## Répartition par longueur

| Lettres | Mots |
| ------: | ---: |
| 2 | 81 |
| 3 | 639 |
| 4 | 1 799 |
| 5 | 5 891 |
| 6 | 13 900 |
| 7 | 25 455 |
| 8 | 38 095 |
| 9 | 47 248 |
| 10 | 49 687 |
| 11 | 45 224 |
| 12 | 35 713 |
| 13 | 24 771 |
| 14 | 15 006 |
| 15 | 8 212 |

## Exemple d'importation

Schéma conseillé :

```sql
CREATE TABLE valid_words (
    word VARCHAR(15) PRIMARY KEY,
    length SMALLINT NOT NULL
);
CREATE INDEX valid_words_length_idx ON valid_words (length);
```

PostgreSQL (`psql`) :

```sql
\copy valid_words(word, length) FROM 'mots_francais_jeu.csv' CSV HEADER
```

SQLite (`sqlite3`) :

```text
.mode csv
.import --skip 1 mots_francais_jeu.csv valid_words
```

Pour une simple validation en mémoire, le fichier TXT peut aussi être chargé
dans un ensemble (`Set`, `HashSet`, etc.), ce qui évite une requête SQL par mot.

## Empreintes SHA-256

- TXT : `2b11f11bef4abe570f30d00f161788fd0885f78be3ddf7478b3e6d8942f00877`
- CSV : `b2d425c0f8cc35d03ec18d016ee9115a57c0adead311319d4f91c0814ed33307`
