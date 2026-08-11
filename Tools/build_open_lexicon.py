#!/usr/bin/env python3
"""Construit le lexique ouvert embarqué par Lettres & Scores.

Le script n'utilise que la bibliothèque standard de Python. Il télécharge une
version figée de Morphalou 3.1, vérifie son empreinte, applique les règles de
sélection documentées dans Corpus/README.md et produit une archive ZIP
reproductible, directement lisible par la bibliothèque standard de Python.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import tempfile
import unicodedata
import urllib.request
import xml.etree.ElementTree as ElementTree
import zipfile
from collections import Counter
from pathlib import Path
from typing import BinaryIO, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

SOURCE_NAME = "Morphalou 3.1"
SOURCE_VERSION = "3.1"
SOURCE_DOCUMENTATION_DATE = "2016-06"
SOURCE_CITATION_YEAR = 2023
SOURCE_CANONICAL_URL = "https://hdl.handle.net/11403/morphalou/v3.1"
SOURCE_DOWNLOAD_URL = (
    "https://repository.ortolang.fr/api/content/morphalou/4/"
    "Morphalou3.1_formatCSV_toutEnUn.zip"
)
SOURCE_SHA256 = (
    "4fc815cbf17aecdf1b47f6bbc263489a460fd8d11ae17e6b522336c72bd0e333"
)
SOURCE_CSV_MEMBER = (
    "Morphalou3.1_formatCSV_toutEnUn/Morphalou3.1_CSV.csv"
)
SOURCE_DOCUMENTATION_MEMBER = (
    "Morphalou3.1_formatCSV_toutEnUn/LISEZ-MOI.html"
)

CORPUS_NAME = "Lexique français ouvert de Lettres & Scores"
CORPUS_RELEASE = "1.0.0"
MODIFICATION_DATE = "2026-08-09"
OUTPUT_RESOURCE_NAME = "lexique-francais.zip"
OUTPUT_MEMBER_NAME = "lexique-francais.txt"
SCRIPT_VERSION = "2.1.0-zip"
MINIMUM_LENGTH = 2
MAXIMUM_LENGTH = 15
MINIMUM_ORIGIN_COUNT = 2

ALLOWED_CATEGORIES = frozenset(
    {
        "Adjectif qualificatif",
        "Adverbe",
        "Conjonction",
        "Déterminant",
        "Interjection",
        "Nom commun",
        "Nombre",
        "Préposition",
        "Pronom",
        "Verbe",
    }
)

DEFAULT_OUTPUT = REPOSITORY_ROOT / "src" / "data" / OUTPUT_RESOURCE_NAME
DEFAULT_LICENSE_OUTPUT = (
    REPOSITORY_ROOT / "Corpus" / "LICENSE-Morphalou-LGPL-LR.txt"
)
DEFAULT_NOTICE_OUTPUT = REPOSITORY_ROOT / "Corpus" / "NOTICE.txt"
DEFAULT_REPORT_OUTPUT = REPOSITORY_ROOT / "Corpus" / "BUILD-REPORT.json"
DOWNLOAD_USER_AGENT = (
    "LettresEtScoresCorpusBuilder/1.0 "
    "(https://github.com/jourquin/LettresEtScores-Python)"
)


class CorpusBuildError(RuntimeError):
    """Erreur contrôlée de téléchargement ou de format de la source."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def sha256_bytes(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def download_source(destination: Path) -> None:
    request = urllib.request.Request(
        SOURCE_DOWNLOAD_URL,
        headers={"User-Agent": DOWNLOAD_USER_AGENT},
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            with destination.open("wb") as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
    except OSError as error:
        raise CorpusBuildError(
            f"Téléchargement de {SOURCE_NAME} impossible: {error}"
        ) from error


def verify_source(path: Path) -> None:
    actual_hash = sha256_file(path)

    if actual_hash != SOURCE_SHA256:
        raise CorpusBuildError(
            "Empreinte SHA-256 inattendue pour l'archive source: "
            f"{actual_hash} (attendu: {SOURCE_SHA256})"
        )


def normalize_form(raw_form: str) -> tuple[str | None, str | None]:
    expanded = (
        raw_form.casefold()
        .replace("œ", "oe")
        .replace("æ", "ae")
    )

    # Une locution ou une forme ponctuée est rejetée dans son ensemble. Les
    # séparateurs ne sont pas supprimés afin de ne pas fabriquer un nouveau mot.
    if not expanded.isalpha():
        return None, "not_simple"

    letters: list[str] = []

    for character in unicodedata.normalize("NFKD", expanded):
        if unicodedata.combining(character):
            continue

        if "a" <= character <= "z":
            letters.append(character.upper())
        else:
            return None, "unsupported_character"

    word = "".join(letters)

    if len(word) < MINIMUM_LENGTH:
        return None, "too_short"

    if len(word) > MAXIMUM_LENGTH:
        return None, "too_long"

    return word, None


def find_csv_header(reader: Iterable[list[str]]) -> Iterable[list[str]]:
    iterator = iter(reader)

    for row in iterator:
        if len(row) >= 18 and row[0] == "GRAPHIE" and row[9] == "GRAPHIE":
            return iterator

    raise CorpusBuildError("En-tête CSV de Morphalou introuvable.")


def build_word_list(source: BinaryIO) -> tuple[list[str], Counter[str]]:
    text_source = io.TextIOWrapper(
        source,
        encoding="utf-8-sig",
        newline="",
    )
    reader = csv.reader(text_source, delimiter=";")
    rows = find_csv_header(reader)
    statistics: Counter[str] = Counter()
    words: set[str] = set()
    current_category = ""
    current_subcategory = ""

    for row in rows:
        statistics["source_rows"] += 1

        if len(row) < 18:
            statistics["rejected_malformed_rows"] += 1
            continue

        if row[0]:
            current_category = row[2]
            current_subcategory = row[3]

        if current_category not in ALLOWED_CATEGORIES:
            statistics["rejected_unaccepted_category"] += 1
            continue

        if current_subcategory == "abréviation":
            statistics["rejected_abbreviation"] += 1
            continue

        origins = set(row[17].split())

        if len(origins) < MINIMUM_ORIGIN_COUNT:
            statistics["rejected_insufficient_origins"] += 1
            continue

        word, rejection_reason = normalize_form(row[9])

        if rejection_reason is not None:
            statistics[f"rejected_{rejection_reason}"] += 1
            continue

        assert word is not None
        statistics["accepted_rows"] += 1

        if word in words:
            statistics["duplicate_rows"] += 1
        else:
            words.add(word)

    statistics["unique_words"] = len(words)
    return sorted(words), statistics


def extract_license(documentation: BinaryIO) -> str:
    try:
        root = ElementTree.parse(documentation).getroot()
    except ElementTree.ParseError as error:
        raise CorpusBuildError(
            "Documentation XHTML de Morphalou illisible."
        ) from error

    namespace = {"x": "http://www.w3.org/1999/xhtml"}
    license_section = None

    for section in root.findall('.//x:div[@class="sect1"]', namespace):
        anchor = section.find('.//x:a[@id="lgpllr"]', namespace)

        if anchor is not None:
            license_section = section
            break

    if license_section is None:
        raise CorpusBuildError("Texte LGPL-LR absent de la source.")

    paragraphs: list[str] = []

    for element in license_section.iter():
        tag = element.tag.rsplit("}", 1)[-1]

        if tag not in {"h2", "p"}:
            continue

        paragraph = " ".join(" ".join(element.itertext()).split())

        if paragraph:
            paragraphs.append(paragraph)

    header = (
        f"{SOURCE_NAME} — Lesser General Public License for Linguistic "
        "Resources (LGPL-LR)\n\n"
        "Texte extrait de la documentation distribuée avec Morphalou 3.1. "
        "Seuls les espaces et retours à la ligne ont été normalisés.\n"
        f"Source canonique : {SOURCE_CANONICAL_URL}\n"
        f"Archive source SHA-256 : {SOURCE_SHA256}\n\n"
    )
    return header + "\n\n".join(paragraphs) + "\n"


def make_notice() -> str:
    return (
        f"{CORPUS_NAME} {CORPUS_RELEASE}\n\n"
        f"Ressource dérivée de {SOURCE_NAME}, conçue par Marie Tonnelier et "
        "maintenue par l'ATILF (CNRS et Université de Lorraine).\n"
        f"Source canonique : {SOURCE_CANONICAL_URL}\n"
        f"Version de la source : {SOURCE_VERSION}\n"
        f"Documentation des données : {SOURCE_DOCUMENTATION_DATE}\n"
        f"Année de la citation ORTOLANG : {SOURCE_CITATION_YEAR}\n"
        f"Date des modifications : {MODIFICATION_DATE}\n\n"
        "Modifications : sélection des formes attestées par au moins deux "
        "lexiques d'origine ; exclusion des abréviations signalées, des "
        "catégories inconnues, des locutions et formes ponctuées ; "
        "normalisation des accents et ligatures en lettres A-Z ; limitation "
        f"aux longueurs de {MINIMUM_LENGTH} à {MAXIMUM_LENGTH} lettres ; "
        "suppression des doublons et tri alphabétique.\n\n"
        "Cette ressource dérivée est distribuée sous LGPL-LR. Le texte de la "
        "licence figure dans LICENSE-Morphalou-LGPL-LR.txt. Elle est fournie "
        "sans garantie. Elle n'est ni une reproduction de l'ODS ni une "
        "référence "
        "officielle pour les compétitions.\n"
    )


def make_manifest(
    words_contents: bytes,
    statistics: Counter[str],
) -> dict[str, object]:
    return {
        "corpus": {
            "name": CORPUS_NAME,
            "release": CORPUS_RELEASE,
            "modification_date": MODIFICATION_DATE,
            "license": "LGPL-LR",
        },
        "source": {
            "name": SOURCE_NAME,
            "version": SOURCE_VERSION,
            "documentation_date": SOURCE_DOCUMENTATION_DATE,
            "citation_year": SOURCE_CITATION_YEAR,
            "canonical_url": SOURCE_CANONICAL_URL,
            "download_url": SOURCE_DOWNLOAD_URL,
            "sha256": SOURCE_SHA256,
            "csv_member": SOURCE_CSV_MEMBER,
        },
        "selection": {
            "allowed_categories": sorted(ALLOWED_CATEGORIES),
            "exclude_abbreviation_subcategory": True,
            "minimum_distinct_origins": MINIMUM_ORIGIN_COUNT,
            "minimum_length": MINIMUM_LENGTH,
            "maximum_length": MAXIMUM_LENGTH,
            "alphabet": "A-Z",
            "ligatures": {"æ": "AE", "œ": "OE"},
            "remove_diacritics": True,
        },
        "output": {
            "resource": OUTPUT_RESOURCE_NAME,
            "member": OUTPUT_MEMBER_NAME,
            "compression": "ZIP avec DEFLATE niveau 9",
            "uncompressed_size_bytes": len(words_contents),
            "words_sha256": sha256_bytes(words_contents),
            "word_count": statistics["unique_words"],
        },
        "statistics": dict(sorted(statistics.items())),
    }


def validate_words(words: list[str]) -> None:
    """Vérifie les invariants exigés par le moteur Python."""
    previous_word: str | None = None

    for line_number, word in enumerate(words, start=1):
        if not word:
            raise CorpusBuildError(
                f"Forme vide à la ligne {line_number}."
            )

        if not (MINIMUM_LENGTH <= len(word) <= MAXIMUM_LENGTH):
            raise CorpusBuildError(
                f"Longueur invalide à la ligne {line_number}: {word!r}."
            )

        if not word.isascii() or not word.isalpha() or not word.isupper():
            raise CorpusBuildError(
                f"Forme non conforme à A-Z à la ligne {line_number}: "
                f"{word!r}."
            )

        if previous_word is not None and word <= previous_word:
            detail = "doublon" if word == previous_word else "ordre incorrect"
            raise CorpusBuildError(
                f"Lexique non strictement trié ({detail}) à la ligne "
                f"{line_number}: {word!r}."
            )

        previous_word = word


def encode_words(words: list[str]) -> bytes:
    validate_words(words)
    return ("\n".join(words) + "\n").encode("ascii")


def atomic_write_bytes(destination: Path, contents: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
        delete=False,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)
        temporary_file.write(contents)

    try:
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def make_zip_archive(words_contents: bytes) -> bytes:
    """Produit une archive ZIP reproductible contenant le lexique texte."""
    archive_buffer = io.BytesIO()
    member = zipfile.ZipInfo(
        filename=OUTPUT_MEMBER_NAME,
        date_time=(1980, 1, 1, 0, 0, 0),
    )
    member.compress_type = zipfile.ZIP_DEFLATED
    member.create_system = 3
    member.external_attr = 0o644 << 16

    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr(
            member,
            words_contents,
            compress_type=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        )

    return archive_buffer.getvalue()


def write_zip_resource(
    destination: Path,
    words: list[str],
    statistics: Counter[str],
) -> dict[str, object]:
    words_contents = encode_words(words)
    manifest = make_manifest(words_contents, statistics)
    archive_contents = make_zip_archive(words_contents)

    try:
        with zipfile.ZipFile(io.BytesIO(archive_contents)) as archive:
            if archive.namelist() != [OUTPUT_MEMBER_NAME]:
                raise CorpusBuildError(
                    "L’archive générée ne contient pas le membre attendu."
                )
            round_trip = archive.read(OUTPUT_MEMBER_NAME)
    except zipfile.BadZipFile as error:
        raise CorpusBuildError(
            "L’archive ZIP générée ne peut pas être relue."
        ) from error

    if round_trip != words_contents:
        raise CorpusBuildError(
            "La vérification après compression a produit un contenu différent."
        )

    atomic_write_bytes(destination, archive_contents)

    return manifest


def write_text_file(destination: Path, contents: str) -> None:
    atomic_write_bytes(destination, contents.encode("utf-8"))


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPOSITORY_ROOT))
    except ValueError:
        return str(path.resolve())


def build(
    source_archive: Path,
    output: Path,
    license_output: Path,
    notice_output: Path,
    report_output: Path,
) -> dict[str, object]:
    if not source_archive.is_file():
        raise CorpusBuildError(
            f"Archive source introuvable: {source_archive}"
        )

    verify_source(source_archive)

    try:
        with zipfile.ZipFile(source_archive) as source_zip:
            with source_zip.open(SOURCE_CSV_MEMBER) as csv_source:
                words, statistics = build_word_list(csv_source)

            with source_zip.open(
                SOURCE_DOCUMENTATION_MEMBER
            ) as documentation:
                license_text = extract_license(documentation)
    except (KeyError, zipfile.BadZipFile) as error:
        raise CorpusBuildError(
            "L'archive source ne présente pas la structure attendue."
        ) from error

    manifest = write_zip_resource(
        output,
        words,
        statistics,
    )
    write_text_file(license_output, license_text)
    write_text_file(notice_output, make_notice())

    report = {
        **manifest,
        "output": {
            **manifest["output"],
            "resource": display_path(output),
            "resource_sha256": sha256_file(output),
        },
    }
    report_text = (
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    write_text_file(report_output, report_text)
    return report


def check_generated_files(
    resource_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Contrôle une ressource existante sans télécharger la source."""
    if not resource_path.is_file():
        raise CorpusBuildError(f"Archive ZIP introuvable: {resource_path}")

    if not report_path.is_file():
        raise CorpusBuildError(
            f"Rapport de construction introuvable: {report_path}"
        )

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        output_metadata = report["output"]
        expected_word_count = output_metadata["word_count"]
        expected_words_hash = output_metadata["words_sha256"]
        expected_resource_hash = output_metadata["resource_sha256"]
        expected_uncompressed_size = output_metadata.get(
            "uncompressed_size_bytes"
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CorpusBuildError(
            f"Rapport de construction illisible: {report_path}"
        ) from error
    except (KeyError, TypeError) as error:
        raise CorpusBuildError(
            f"Rapport de construction incomplet: {report_path}"
        ) from error

    try:
        archive_contents = resource_path.read_bytes()
        with zipfile.ZipFile(io.BytesIO(archive_contents)) as archive:
            if archive.namelist() != [OUTPUT_MEMBER_NAME]:
                raise CorpusBuildError(
                    f"L’archive doit contenir uniquement {OUTPUT_MEMBER_NAME!r}."
                )
            words_contents = archive.read(OUTPUT_MEMBER_NAME)
    except zipfile.BadZipFile as error:
        raise CorpusBuildError(
            f"Archive ZIP invalide: {resource_path}"
        ) from error

    try:
        text = words_contents.decode("ascii")
    except UnicodeDecodeError as error:
        raise CorpusBuildError(
            "Le corpus décompressé contient des caractères hors ASCII."
        ) from error

    if not text.endswith("\n"):
        raise CorpusBuildError(
            "Le corpus décompressé ne se termine pas par un retour à la ligne."
        )

    words = text.splitlines()
    validate_words(words)

    actual_resource_hash = sha256_bytes(archive_contents)
    actual_words_hash = sha256_bytes(words_contents)

    if len(words) != expected_word_count:
        raise CorpusBuildError(
            f"Nombre de formes inattendu: {len(words)} "
            f"(attendu: {expected_word_count})."
        )

    if (
        expected_uncompressed_size is not None
        and len(words_contents) != expected_uncompressed_size
    ):
        raise CorpusBuildError(
            f"Taille décompressée inattendue: {len(words_contents)} octets "
            f"(attendu: {expected_uncompressed_size})."
        )

    if actual_words_hash != expected_words_hash:
        raise CorpusBuildError(
            "Empreinte du texte lexical inattendue: "
            f"{actual_words_hash} (attendu: {expected_words_hash})."
        )

    if actual_resource_hash != expected_resource_hash:
        raise CorpusBuildError(
            "Empreinte de la ressource compressée inattendue: "
            f"{actual_resource_hash} (attendu: {expected_resource_hash})."
        )

    return {
        "word_count": len(words),
        "words_sha256": actual_words_hash,
        "resource_sha256": actual_resource_hash,
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Construit le lexique ouvert de Lettres & Scores à partir de "
            "Morphalou 3.1."
        )
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {SCRIPT_VERSION}",
    )
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--source-archive",
        type=Path,
        help=(
            "archive Morphalou déjà téléchargée ; si omise, la source "
            "officielle est téléchargée temporairement"
        ),
    )
    source_group.add_argument(
        "--check",
        action="store_true",
        help=(
            "vérifie la ressource et le rapport existants sans télécharger "
            "Morphalou ni modifier de fichier"
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--license-output",
        type=Path,
        default=DEFAULT_LICENSE_OUTPUT,
    )
    parser.add_argument(
        "--notice-output",
        type=Path,
        default=DEFAULT_NOTICE_OUTPUT,
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=DEFAULT_REPORT_OUTPUT,
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    if arguments.output.suffix.lower() != ".zip":
        print(
            "Erreur: --output doit désigner une archive .zip."
        )
        return 2

    print(f"Générateur {SCRIPT_VERSION}")
    print(f"Sortie ZIP: {arguments.output}")

    try:
        if arguments.check:
            checked = check_generated_files(
                arguments.output,
                arguments.report_output,
            )
            print(
                f"Corpus valide: {checked['word_count']} formes dans "
                f"{arguments.output}"
            )
            print(f"SHA-256: {checked['resource_sha256']}")
            return 0

        if arguments.source_archive is not None:
            report = build(
                arguments.source_archive,
                arguments.output,
                arguments.license_output,
                arguments.notice_output,
                arguments.report_output,
            )
        else:
            with tempfile.TemporaryDirectory(
                prefix="lettres-et-scores-corpus-"
            ) as temporary_directory:
                source_archive = Path(temporary_directory) / "morphalou.zip"
                print(f"Téléchargement de {SOURCE_DOWNLOAD_URL}")
                download_source(source_archive)
                report = build(
                    source_archive,
                    arguments.output,
                    arguments.license_output,
                    arguments.notice_output,
                    arguments.report_output,
                )
    except (CorpusBuildError, OSError) as error:
        print(f"Erreur: {error}")
        return 1

    print(
        f"{report['output']['word_count']} formes écrites dans "
        f"{arguments.output}"
    )
    print(f"SHA-256: {report['output']['resource_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
