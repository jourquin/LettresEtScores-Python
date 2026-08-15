#!/usr/bin/env python3
"""Construit un corpus français corroboré par plusieurs sources ouvertes.

Le corpus Morphalou déjà embarqué sert de socle. Une forme absente de ce socle
n'est ajoutée que si elle est attestée, après normalisation et filtrage, par un
nombre minimal de ressources externes distinctes. L'ODS n'est jamais lu et ne
participe donc ni à la sélection ni à la validation.

Le script n'utilise que la bibliothèque standard de Python. Il télécharge les
versions figées absentes de son cache, contrôle leurs empreintes avant lecture
et accepte aussi des fichiers locaux explicites. Il produit une archive ZIP
compatible avec le moteur, un fichier TSV de provenance et un rapport JSON
reproductible.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import sys
import tarfile
import tempfile
import unicodedata
import urllib.request
import zipfile
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


TOOLS_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = TOOLS_DIRECTORY.parent

# Le générateur Morphalou reste la référence pour le format, la normalisation,
# la validation des invariants et l'écriture atomique de l'archive.
if str(TOOLS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIRECTORY))
import build_open_lexicon as base_builder  # noqa: E402


SCRIPT_VERSION = "1.1.0"
CORPUS_NAME = "Lexique français multisource corroboré de Lettres & Scores"
CORPUS_RELEASE = "0.1.0-candidate"
MODIFICATION_DATE = "2026-08-12"
OUTPUT_RESOURCE_NAME = "lexique-francais-multisources.zip"
OUTPUT_MEMBER_NAME = base_builder.OUTPUT_MEMBER_NAME
PROVENANCE_NAME = "MULTISOURCE-PROVENANCE.tsv"
REPORT_NAME = "MULTISOURCE-BUILD-REPORT.json"
NOTICE_NAME = "MULTISOURCE-NOTICE.txt"
DEFAULT_BASE_LEXICON = REPOSITORY_ROOT / "src" / "data" / "lexique-francais.zip"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "src" / "data" / OUTPUT_RESOURCE_NAME
DEFAULT_PROVENANCE_OUTPUT = REPOSITORY_ROOT / "Corpus" / PROVENANCE_NAME
DEFAULT_REPORT_OUTPUT = REPOSITORY_ROOT / "Corpus" / REPORT_NAME
DEFAULT_NOTICE_OUTPUT = REPOSITORY_ROOT / "Corpus" / NOTICE_NAME
DEFAULT_SOURCES_CACHE = REPOSITORY_ROOT / ".cache" / "lexical-sources"
DEFAULT_MINIMUM_ATTESTATIONS = 2
DOWNLOAD_USER_AGENT = (
    "LettresEtScoresMultisourceBuilder/1.1 "
    "(https://github.com/jourquin/LettresEtScores-Python)"
)

LEFFF_ARCHIVE_URL = (
    "https://gitlab.inria.fr/almanach/alexina/lefff/-/"
    "package_files/2570/download"
)
LEFFF_ARCHIVE_SHA256 = (
    "d12ae1d54bba098b37b1a564095e7ff110d5efbac803e066262a54f263b46c49"
)
LEFFF_ARCHIVE_MEMBER = "lefff-3.4.mlex/lefff-3.4.mlex"

UNITEX_COMMIT = "70d73c571038e1a19ad9d77e77ab6d29e6c8ce82"
UNITEX_RAW_BASE_URL = (
    "https://raw.githubusercontent.com/UnitexGramLab/unitex-lingua/"
    f"{UNITEX_COMMIT}/fr/Dela"
)

GRAMMALECTE_ARCHIVE_URL = (
    "https://registry.npmjs.org/dictionary-fr/-/dictionary-fr-3.0.0.tgz"
)
GRAMMALECTE_ARCHIVE_SHA256 = (
    "b20ab69249881bc36b1dcdfbfd2df226660a7cecc95f2cf122714008b491c78e"
)
GRAMMALECTE_AFF_MEMBER = "package/index.aff"
GRAMMALECTE_DIC_MEMBER = "package/index.dic"

LEXIQUE383_DOWNLOAD_URL = (
    "https://raw.githubusercontent.com/SekouDiaoNlp/pylexique/"
    "be08baf1435e7cf56c5672a2611cc6204a970adc/"
    "pylexique/Lexique383/Lexique383.txt"
)


@dataclass(frozen=True)
class SourceMetadata:
    key: str
    name: str
    version: str
    license: str
    canonical_url: str
    expected_files: tuple[tuple[str, str], ...]


SOURCE_METADATA = {
    "lefff": SourceMetadata(
        key="lefff",
        name="Lefff 3.4",
        version="3.4",
        license="CeCILL-L",
        canonical_url=(
            "https://almanach.inria.fr/software_and_resources/Alexina-en.html"
        ),
        expected_files=((
            "mlex",
            "f3da25e58aec161c5ae34d598038dd6304056c2649867ede7e220a74fd34fe12",
        ),),
    ),
    "unitex": SourceMetadata(
        key="unitex",
        name="Unitex DELA français",
        version="unitex-lingua commit 70d73c571038e1a19ad9d77e77ab6d29e6c8ce82",
        license="LGPL-LR",
        canonical_url="https://github.com/UnitexGramLab/unitex-lingua/tree/master/fr",
        expected_files=(
            (
                "dic",
                "6b69cc832e81f345ddd43e41704a47c53348e6a1f10cc1dfc09a19796064aafa",
            ),
            (
                "bin",
                "b7389a4d60148ff663a11276feffede18b6d2143e45f75201cd64f64b92516c5",
            ),
            (
                "inf",
                "152b0e9f63bd7606733458d419d0f4b06ee809fa5aae4023002b1076486f4bc9",
            ),
        ),
    ),
    "grammalecte": SourceMetadata(
        key="grammalecte",
        name="Grammalecte, dictionnaire français classique 7.5",
        version="7.5 (paquet dictionary-fr 3.0.0)",
        license="MPL-2.0",
        canonical_url="https://grammalecte.net/",
        expected_files=(
            (
                "aff",
                "05a735d34c912e4e381ff08ee7c747923ccf5cf9dca81d8467982fa1ca51c2b7",
            ),
            (
                "dic",
                "984e933237bc1224a48f42828233be9b03228260ef67aa8e2bdddcd03a26230d",
            ),
        ),
    ),
    "lexique383": SourceMetadata(
        key="lexique383",
        name="Lexique 3.83",
        version="3.83",
        license="CC BY-SA 4.0",
        canonical_url="https://www.lexique.org/databases/Lexique383/",
        expected_files=((
            "txt",
            "fe2cb931f774d4c44abb92fa785a8425b74f668373012ad22e3980fb1bfea0de",
        ),),
    ),
}


class MultisourceBuildError(base_builder.CorpusBuildError):
    """Erreur contrôlée de format, d'intégrité ou de corroboration."""


@dataclass(frozen=True)
class SourceResult:
    metadata: SourceMetadata
    words: frozenset[str]
    statistics: dict[str, int]
    files: dict[str, Path]


def normalize_form(raw_form: str) -> tuple[str | None, str | None]:
    """Normalise une forme avec les mêmes règles que le corpus Morphalou."""
    return base_builder.normalize_form(raw_form.strip())


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise MultisourceBuildError(f"{label} introuvable: {path}")


def verify_file(path: Path, expected_sha256: str, label: str) -> str:
    require_file(path, label)
    actual_sha256 = base_builder.sha256_file(path)
    if actual_sha256 != expected_sha256:
        raise MultisourceBuildError(
            f"Empreinte SHA-256 inattendue pour {label}: {actual_sha256} "
            f"(attendu: {expected_sha256})"
        )
    return actual_sha256


def download_file(
    url: str,
    destination: Path,
    expected_sha256: str,
    label: str,
    allow_download: bool = True,
) -> Path:
    """Télécharge un fichier absent ou invalide, puis le publie atomiquement."""
    if destination.is_file():
        actual_sha256 = base_builder.sha256_file(destination)
        if actual_sha256 == expected_sha256:
            print(f"Source en cache: {destination}")
            return destination
        print(
            f"Cache invalide pour {label} ({actual_sha256}); "
            "nouveau téléchargement."
        )
    if not allow_download:
        raise MultisourceBuildError(
            f"{label} absent ou invalide dans le cache hors ligne: "
            f"{destination}"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": DOWNLOAD_USER_AGENT},
    )
    print(f"Téléchargement de {label}: {url}")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{destination.name}.",
            suffix=".download",
            dir=destination.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            with urllib.request.urlopen(request, timeout=180) as response:
                shutil.copyfileobj(response, temporary_file, length=1024 * 1024)
        verify_file(temporary_path, expected_sha256, label)
        temporary_path.replace(destination)
        destination.chmod(0o644)
    except OSError as error:
        raise MultisourceBuildError(
            f"Téléchargement de {label} impossible: {error}"
        ) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return destination


def extract_tar_member(
    archive_path: Path,
    member_name: str,
    destination: Path,
    expected_sha256: str,
    label: str,
) -> Path:
    """Extrait un membre nommé, sans faire confiance aux chemins de l'archive."""
    if destination.is_file():
        actual_sha256 = base_builder.sha256_file(destination)
        if actual_sha256 == expected_sha256:
            return destination
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            member = archive.getmember(member_name)
            if not member.isfile():
                raise MultisourceBuildError(
                    f"{member_name!r} n'est pas un fichier dans {archive_path}."
                )
            source = archive.extractfile(member)
            if source is None:
                raise MultisourceBuildError(
                    f"Impossible de lire {member_name!r} dans {archive_path}."
                )
            contents = source.read()
    except (KeyError, tarfile.TarError) as error:
        raise MultisourceBuildError(
            f"Archive source invalide ou membre absent: {archive_path}"
        ) from error
    if base_builder.sha256_bytes(contents) != expected_sha256:
        raise MultisourceBuildError(
            f"Empreinte inattendue après extraction de {label}."
        )
    write_public_bytes(destination, contents)
    return destination


def acquire_default_source_files(
    cache_directory: Path,
    allow_download: bool = True,
) -> dict[str, dict[str, Path]]:
    """Résout dans un cache local les quatre distributions source figées."""
    lefff_directory = cache_directory / "lefff-3.4"
    lefff_archive = download_file(
        LEFFF_ARCHIVE_URL,
        lefff_directory / "lefff-3.4-mlex.tar.gz",
        LEFFF_ARCHIVE_SHA256,
        "archive Lefff 3.4",
        allow_download,
    )
    lefff_mlex = extract_tar_member(
        lefff_archive,
        LEFFF_ARCHIVE_MEMBER,
        lefff_directory / "lefff-3.4.mlex",
        dict(SOURCE_METADATA["lefff"].expected_files)["mlex"],
        "Lefff 3.4",
    )

    unitex_directory = cache_directory / "unitex-lingua" / UNITEX_COMMIT
    unitex_hashes = dict(SOURCE_METADATA["unitex"].expected_files)
    unitex_bin = download_file(
        f"{UNITEX_RAW_BASE_URL}/Dela_fr.bin",
        unitex_directory / "Dela_fr.bin",
        unitex_hashes["bin"],
        "Unitex Dela_fr.bin",
        allow_download,
    )
    unitex_inf = download_file(
        f"{UNITEX_RAW_BASE_URL}/Dela_fr.inf",
        unitex_directory / "Dela_fr.inf",
        unitex_hashes["inf"],
        "Unitex Dela_fr.inf",
        allow_download,
    )

    grammalecte_directory = cache_directory / "grammalecte-7.5"
    grammalecte_archive = download_file(
        GRAMMALECTE_ARCHIVE_URL,
        grammalecte_directory / "dictionary-fr-3.0.0.tgz",
        GRAMMALECTE_ARCHIVE_SHA256,
        "archive Grammalecte 7.5",
        allow_download,
    )
    grammalecte_hashes = dict(
        SOURCE_METADATA["grammalecte"].expected_files
    )
    grammalecte_aff = extract_tar_member(
        grammalecte_archive,
        GRAMMALECTE_AFF_MEMBER,
        grammalecte_directory / "index.aff",
        grammalecte_hashes["aff"],
        "Grammalecte index.aff",
    )
    grammalecte_dic = extract_tar_member(
        grammalecte_archive,
        GRAMMALECTE_DIC_MEMBER,
        grammalecte_directory / "index.dic",
        grammalecte_hashes["dic"],
        "Grammalecte index.dic",
    )

    lexique_directory = cache_directory / "lexique-3.83"
    lexique_txt = download_file(
        LEXIQUE383_DOWNLOAD_URL,
        lexique_directory / "Lexique383.txt",
        dict(SOURCE_METADATA["lexique383"].expected_files)["txt"],
        "Lexique 3.83",
        allow_download,
    )
    return {
        "lefff": {"mlex": lefff_mlex},
        "unitex": {"bin": unitex_bin, "inf": unitex_inf},
        "grammalecte": {
            "aff": grammalecte_aff,
            "dic": grammalecte_dic,
        },
        "lexique383": {"txt": lexique_txt},
    }


def read_base_lexicon(path: Path) -> list[str]:
    require_file(path, "corpus de base")
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.namelist() != [OUTPUT_MEMBER_NAME]:
                raise MultisourceBuildError(
                    f"Le corpus de base doit contenir uniquement "
                    f"{OUTPUT_MEMBER_NAME!r}."
                )
            contents = archive.read(OUTPUT_MEMBER_NAME)
    except zipfile.BadZipFile as error:
        raise MultisourceBuildError(
            f"Archive ZIP de base invalide: {path}"
        ) from error

    try:
        text = contents.decode("ascii")
    except UnicodeDecodeError as error:
        raise MultisourceBuildError(
            "Le corpus de base contient des caractères hors ASCII."
        ) from error
    if not text.endswith("\n"):
        raise MultisourceBuildError(
            "Le corpus de base ne se termine pas par un retour à la ligne."
        )
    words = text.splitlines()
    base_builder.validate_words(words)
    return words


LEFFF_EXCLUDED_CATEGORIES = frozenset(
    {
        "np",
        "poncts",
        "ponctw",
        "epsilon",
        "meta",
        "sbound",
        "parento",
        "parentf",
    }
)


def load_lefff(path: Path) -> tuple[frozenset[str], dict[str, int]]:
    words: set[str] = set()
    statistics: Counter[str] = Counter()
    with path.open(encoding="utf-8") as source:
        for line in source:
            statistics["source_rows"] += 1
            fields = line.rstrip("\r\n").split("\t")
            if len(fields) < 2:
                statistics["rejected_malformed_rows"] += 1
                continue
            form, category = fields[0], fields[1]
            if (
                category in LEFFF_EXCLUDED_CATEGORIES
                or category.endswith("Pref")
                or category.startswith("suff")
            ):
                statistics["rejected_category"] += 1
                continue
            word, rejection = normalize_form(form)
            if rejection is not None:
                statistics[f"rejected_{rejection}"] += 1
                continue
            assert word is not None
            statistics["accepted_rows"] += 1
            if word in words:
                statistics["duplicate_rows"] += 1
            words.add(word)
    statistics["unique_words"] = len(words)
    return frozenset(words), dict(sorted(statistics.items()))


def find_unescaped(value: str, character: str, start: int = 0) -> int:
    escaped = False
    for index in range(start, len(value)):
        current = value[index]
        if escaped:
            escaped = False
        elif current == "\\":
            escaped = True
        elif current == character:
            return index
    return -1


def split_unescaped(value: str, separator: str) -> list[str]:
    items: list[str] = []
    start = 0
    escaped = False
    for index, current in enumerate(value):
        if escaped:
            escaped = False
        elif current == "\\":
            escaped = True
        elif current == separator:
            items.append(value[start:index])
            start = index + 1
    items.append(value[start:])
    return items


UNITEX_ALLOWED_CATEGORIES = frozenset(
    {
        "A",
        "ADV",
        "CONJC",
        "CONJS",
        "DET",
        "INTJ",
        "N",
        "PREP",
        "PRO",
        "V",
    }
)


def load_unitex(path: Path) -> tuple[frozenset[str], dict[str, int]]:
    words: set[str] = set()
    statistics: Counter[str] = Counter()
    with path.open(encoding="utf-16") as source:
        for line in source:
            statistics["source_rows"] += 1
            line = line.rstrip("\r\n")
            comma = find_unescaped(line, ",")
            dot = find_unescaped(line, ".", comma + 1) if comma >= 0 else -1
            if comma < 0 or dot < 0:
                statistics["rejected_malformed_rows"] += 1
                continue
            codes = line[dot + 1 :].split(":", 1)[0].split("+")
            category = codes[0]
            features = frozenset(codes[1:])
            if category not in UNITEX_ALLOWED_CATEGORIES:
                statistics["rejected_category"] += 1
                continue
            if "NPropre" in features:
                statistics["rejected_proper_name"] += 1
                continue
            word, rejection = normalize_form(line[:comma])
            if rejection is not None:
                statistics[f"rejected_{rejection}"] += 1
                continue
            assert word is not None
            statistics["accepted_rows"] += 1
            if word in words:
                statistics["duplicate_rows"] += 1
            words.add(word)
    statistics["unique_words"] = len(words)
    return frozenset(words), dict(sorted(statistics.items()))


def read_unitex_variable(data: bytes, position: int) -> tuple[int, int]:
    if position >= len(data):
        raise MultisourceBuildError("Fin prématurée du dictionnaire Unitex BIN.")
    first = data[position]
    if first & 0x80 == 0:
        return first, position + 1
    byte_count = (first >> 5) - 2
    if byte_count < 2 or byte_count > 5 or position + byte_count > len(data):
        raise MultisourceBuildError(
            "Entier de longueur variable invalide dans le dictionnaire Unitex."
        )
    value = first & 0x1F
    shifts = (5, 13, 21, 29)
    for index in range(1, byte_count):
        value |= data[position + index] << shifts[index - 1]
    masks = {2: 0x1FFF, 3: 0x1FFFFF, 4: 0x1FFFFFFF, 5: 0xFFFFFFFF}
    return value & masks[byte_count], position + byte_count


def read_unitex_encoded(
    data: bytes,
    position: int,
    encoding: int,
) -> tuple[int, int]:
    if encoding == 3:
        return read_unitex_variable(data, position)
    widths = {0: 2, 1: 3, 2: 4}
    if encoding not in widths:
        raise MultisourceBuildError(
            f"Encodage entier Unitex non pris en charge: {encoding}."
        )
    width = widths[encoding]
    end = position + width
    if end > len(data):
        raise MultisourceBuildError("Fin prématurée du dictionnaire Unitex BIN.")
    return int.from_bytes(data[position:end], "big"), end


@dataclass(frozen=True)
class UnitexBinHeader:
    initial_state_offset: int
    state_encoding: int
    inf_number_encoding: int
    character_encoding: int
    offset_encoding: int


def parse_unitex_bin_header(data: bytes) -> UnitexBinHeader:
    if len(data) < 6:
        raise MultisourceBuildError("Dictionnaire Unitex BIN trop court.")
    if data[0] == 0:
        return UnitexBinHeader(4, 0, 1, 0, 1)
    if data[0] != 1:
        raise MultisourceBuildError(
            "Seuls les dictionnaires Unitex BIN classiques sont pris en charge."
        )
    if len(data) < 9:
        raise MultisourceBuildError("En-tête Unitex BIN moderne incomplet.")
    header = UnitexBinHeader(
        initial_state_offset=int.from_bytes(data[5:9], "big"),
        state_encoding=data[1],
        inf_number_encoding=data[2],
        character_encoding=data[3],
        offset_encoding=data[4],
    )
    if header.state_encoding not in {0, 1}:
        raise MultisourceBuildError(
            f"Encodage d'état Unitex non pris en charge: "
            f"{header.state_encoding}."
        )
    if header.initial_state_offset >= len(data):
        raise MultisourceBuildError(
            "Décalage de l'état initial Unitex hors du fichier BIN."
        )
    return header


def read_unitex_inf(path: Path) -> list[list[str]]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        raise MultisourceBuildError("Fichier Unitex INF vide.")
    try:
        declared_count = int(lines[0])
    except ValueError as error:
        raise MultisourceBuildError(
            "Nombre d'entrées absent du fichier Unitex INF."
        ) from error
    code_lines = [split_unescaped(line, ",") for line in lines[1:]]
    if len(code_lines) != declared_count:
        raise MultisourceBuildError(
            f"Nombre de lignes Unitex INF inattendu: {len(code_lines)} "
            f"(attendu: {declared_count})."
        )
    return code_lines


def unitex_code_is_allowed(code: str) -> tuple[bool, str | None]:
    dot = find_unescaped(code, ".")
    if dot < 0:
        return False, "malformed_rows"
    codes = code[dot + 1 :].split(":", 1)[0].split("+")
    if not codes or codes[0] not in UNITEX_ALLOWED_CATEGORIES:
        return False, "category"
    if "NPropre" in codes[1:]:
        return False, "proper_name"
    return True, None


def read_unitex_state(
    data: bytes,
    position: int,
    header: UnitexBinHeader,
) -> tuple[int, int, int | None, list[tuple[str, int]]]:
    if header.state_encoding == 0:
        if position + 2 > len(data):
            raise MultisourceBuildError("État Unitex BIN tronqué.")
        value = int.from_bytes(data[position : position + 2], "big")
        position += 2
        final = not bool(value & 0x8000)
        transition_count = value & 0x7FFF
    else:
        value, position = read_unitex_variable(data, position)
        final = bool(value & 1)
        transition_count = value >> 1

    inf_reference: int | None = None
    if final:
        inf_reference, position = read_unitex_encoded(
            data,
            position,
            header.inf_number_encoding,
        )
    transitions: list[tuple[str, int]] = []
    for _ in range(transition_count):
        character_code, position = read_unitex_encoded(
            data,
            position,
            header.character_encoding,
        )
        destination, position = read_unitex_encoded(
            data,
            position,
            header.offset_encoding,
        )
        try:
            character = chr(character_code)
        except ValueError as error:
            raise MultisourceBuildError(
                f"Caractère Unitex invalide: {character_code}."
            ) from error
        if destination >= len(data):
            raise MultisourceBuildError(
                f"Transition Unitex hors du fichier: {destination}."
            )
        transitions.append((character, destination))
    return position, transition_count, inf_reference, transitions


def load_unitex_binary(
    bin_path: Path,
    inf_path: Path,
) -> tuple[frozenset[str], dict[str, int]]:
    """Lit directement le couple BIN/INF, sans exécutable Unitex externe."""
    data = bin_path.read_bytes()
    header = parse_unitex_bin_header(data)
    inf_codes = read_unitex_inf(inf_path)
    words: set[str] = set()
    statistics: Counter[str] = Counter()
    stack: list[tuple[int, str]] = [(header.initial_state_offset, "")]

    while stack:
        state_position, surface = stack.pop()
        _, _, inf_reference, transitions = read_unitex_state(
            data,
            state_position,
            header,
        )
        if inf_reference is not None:
            if inf_reference >= len(inf_codes):
                raise MultisourceBuildError(
                    f"Référence Unitex INF hors limites: {inf_reference}."
                )
            accepted_surface = False
            for code in inf_codes[inf_reference]:
                statistics["source_rows"] += 1
                allowed, rejection = unitex_code_is_allowed(code)
                if not allowed:
                    assert rejection is not None
                    statistics[f"rejected_{rejection}"] += 1
                    continue
                word, form_rejection = normalize_form(surface)
                if form_rejection is not None:
                    statistics[f"rejected_{form_rejection}"] += 1
                    continue
                assert word is not None
                statistics["accepted_rows"] += 1
                accepted_surface = True
            if accepted_surface:
                word, _ = normalize_form(surface)
                assert word is not None
                if word in words:
                    statistics["duplicate_rows"] += 1
                words.add(word)
        for character, destination in reversed(transitions):
            stack.append((destination, surface + character))

    statistics["unique_words"] = len(words)
    return frozenset(words), dict(sorted(statistics.items()))


def split_long_flags(flags: str) -> tuple[str, ...]:
    if len(flags) % 2:
        raise MultisourceBuildError(
            f"Suite de drapeaux Hunspell longs invalide: {flags!r}"
        )
    return tuple(flags[index : index + 2] for index in range(0, len(flags), 2))


@dataclass(frozen=True)
class AffixRule:
    kind: str
    flag: str
    cross: bool
    strip: str
    add: str
    continuation: tuple[str, ...]
    condition: re.Pattern[str]

    def apply(self, word: str) -> str | None:
        if not self.condition.search(word):
            return None
        if self.kind == "SFX":
            if self.strip and not word.endswith(self.strip):
                return None
            base = word[: -len(self.strip)] if self.strip else word
            return base + self.add
        if self.strip and not word.startswith(self.strip):
            return None
        base = word[len(self.strip) :] if self.strip else word
        return self.add + base


@dataclass(frozen=True)
class HunspellConfiguration:
    rules: dict[str, tuple[AffixRule, ...]]
    need_affix: str | None
    forbidden: str | None
    keep_case: str | None
    no_suggest: str | None


def parse_hunspell_aff(path: Path) -> HunspellConfiguration:
    lines = path.read_text(encoding="utf-8").splitlines()
    directives: dict[str, str] = {}
    headers: dict[tuple[str, str], tuple[bool, int]] = {}
    for line in lines:
        fields = line.split()
        if len(fields) >= 2 and fields[0] in {
            "NEEDAFFIX",
            "FORBIDDENWORD",
            "KEEPCASE",
            "NOSUGGEST",
        }:
            directives[fields[0]] = fields[1]
        if (
            len(fields) == 4
            and fields[0] in {"PFX", "SFX"}
            and fields[2] in {"Y", "N"}
        ):
            try:
                count = int(fields[3])
            except ValueError as error:
                raise MultisourceBuildError(
                    f"En-tête Hunspell invalide: {line!r}"
                ) from error
            headers[(fields[0], fields[1])] = (fields[2] == "Y", count)

    rules: dict[str, list[AffixRule]] = defaultdict(list)
    parsed_counts: Counter[tuple[str, str]] = Counter()
    for line in lines:
        fields = line.split()
        if len(fields) < 5 or fields[0] not in {"PFX", "SFX"}:
            continue
        kind, flag = fields[0], fields[1]
        if fields[2] in {"Y", "N"}:
            continue
        if (kind, flag) not in headers:
            raise MultisourceBuildError(
                f"Règle Hunspell sans en-tête: {line!r}"
            )
        strip = "" if fields[2] == "0" else fields[2]
        add_part = fields[3]
        if "/" in add_part:
            add, continuation_text = add_part.split("/", 1)
            continuation = split_long_flags(continuation_text)
        else:
            add, continuation = add_part, ()
        add = "" if add == "0" else add
        pattern = (
            f"{fields[4]}$" if kind == "SFX" else f"^{fields[4]}"
        )
        try:
            condition = re.compile(pattern)
        except re.error as error:
            raise MultisourceBuildError(
                f"Condition Hunspell invalide: {fields[4]!r}"
            ) from error
        rules[flag].append(
            AffixRule(
                kind=kind,
                flag=flag,
                cross=headers[(kind, flag)][0],
                strip=strip,
                add=add,
                continuation=continuation,
                condition=condition,
            )
        )
        parsed_counts[(kind, flag)] += 1

    for key, (_, expected_count) in headers.items():
        if parsed_counts[key] != expected_count:
            raise MultisourceBuildError(
                f"Bloc Hunspell incomplet {key}: {parsed_counts[key]} "
                f"règles sur {expected_count}."
            )
    return HunspellConfiguration(
        rules={flag: tuple(items) for flag, items in rules.items()},
        need_affix=directives.get("NEEDAFFIX"),
        forbidden=directives.get("FORBIDDENWORD"),
        keep_case=directives.get("KEEPCASE"),
        no_suggest=directives.get("NOSUGGEST"),
    )


def generate_hunspell_forms(
    stem: str,
    flags: tuple[str, ...],
    configuration: HunspellConfiguration,
) -> set[str]:
    flag_set = set(flags)
    forms: set[str] = set()
    if configuration.need_affix not in flag_set:
        forms.add(stem)

    direct: set[tuple[str, tuple[str, ...], str]] = set()
    prefixes: list[tuple[str, bool]] = []
    suffixes: list[tuple[str, bool]] = []
    for flag in flags:
        for rule in configuration.rules.get(flag, ()):
            produced = rule.apply(stem)
            if produced is None:
                continue
            direct.add((produced, rule.continuation, rule.kind))
            if rule.kind == "PFX":
                prefixes.append((produced, rule.cross))
            else:
                suffixes.append((produced, rule.cross))

    # Produits croisés préfixe/suffixe autorisés par les deux blocs.
    for flag in flags:
        for rule in configuration.rules.get(flag, ()):
            if not rule.cross:
                continue
            bases = prefixes if rule.kind == "SFX" else suffixes
            for derived, other_cross in bases:
                if not other_cross:
                    continue
                produced = rule.apply(derived)
                if produced is not None:
                    direct.add((produced, rule.continuation, "BOTH"))

    queue = deque(direct)
    seen = set(direct)
    while queue:
        current, continuation, previous_kind = queue.popleft()
        forms.add(current)
        for flag in continuation:
            for rule in configuration.rules.get(flag, ()):
                if previous_kind == rule.kind and not rule.cross:
                    continue
                produced = rule.apply(current)
                if produced is None:
                    continue
                state = (produced, rule.continuation, rule.kind)
                if state not in seen:
                    seen.add(state)
                    queue.append(state)
    return forms


def load_grammalecte(
    aff_path: Path,
    dic_path: Path,
) -> tuple[frozenset[str], dict[str, int]]:
    configuration = parse_hunspell_aff(aff_path)
    words: set[str] = set()
    statistics: Counter[str] = Counter()
    with dic_path.open(encoding="utf-8") as source:
        header = next(source, "").strip()
        try:
            declared_rows = int(header)
        except ValueError as error:
            raise MultisourceBuildError(
                "Nombre d'entrées absent du dictionnaire Hunspell."
            ) from error
        for line in source:
            statistics["source_rows"] += 1
            entry = line.rstrip("\r\n").split("\t", 1)[0]
            if "/" in entry:
                stem, flag_text = entry.rsplit("/", 1)
                flags = split_long_flags(flag_text)
            else:
                stem, flags = entry, ()
            flag_set = set(flags)
            excluded_directives = (
                ("forbidden", configuration.forbidden),
                ("keep_case", configuration.keep_case),
                ("no_suggest", configuration.no_suggest),
            )
            rejected = False
            for reason, directive_flag in excluded_directives:
                if directive_flag is not None and directive_flag in flag_set:
                    statistics[f"rejected_{reason}"] += 1
                    rejected = True
                    break
            if rejected:
                continue

            for form in generate_hunspell_forms(stem, flags, configuration):
                statistics["generated_rows"] += 1
                word, rejection = normalize_form(form)
                if rejection is not None:
                    statistics[f"rejected_{rejection}"] += 1
                    continue
                assert word is not None
                if word in words:
                    statistics["duplicate_rows"] += 1
                words.add(word)

    statistics["declared_rows"] = declared_rows
    statistics["declared_actual_row_difference"] = (
        declared_rows - statistics["source_rows"]
    )
    statistics["unique_words"] = len(words)
    return frozenset(words), dict(sorted(statistics.items()))


LEXIQUE_ALLOWED_CATEGORIES = frozenset(
    {
        "ADJ",
        "ADV",
        "ART",
        "AUX",
        "CON",
        "NOM",
        "ONO",
        "PRE",
        "PRO",
        "VER",
    }
)


def load_lexique383(path: Path) -> tuple[frozenset[str], dict[str, int]]:
    words: set[str] = set()
    statistics: Counter[str] = Counter()
    with path.open(encoding="iso-8859-1", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        required = {"1_ortho", "4_cgram"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise MultisourceBuildError(
                "Colonnes 1_ortho et 4_cgram absentes de Lexique 3.83."
            )
        for row in reader:
            statistics["source_rows"] += 1
            category = row["4_cgram"].split(":", 1)[0]
            if category not in LEXIQUE_ALLOWED_CATEGORIES:
                statistics["rejected_category"] += 1
                continue
            word, rejection = normalize_form(row["1_ortho"])
            if rejection is not None:
                statistics[f"rejected_{rejection}"] += 1
                continue
            assert word is not None
            statistics["accepted_rows"] += 1
            if word in words:
                statistics["duplicate_rows"] += 1
            words.add(word)
    statistics["unique_words"] = len(words)
    return frozenset(words), dict(sorted(statistics.items()))


def make_source_result(
    source_key: str,
    files: dict[str, Path],
    loader: Callable[..., tuple[frozenset[str], dict[str, int]]],
) -> SourceResult:
    metadata = SOURCE_METADATA[source_key]
    expected = dict(metadata.expected_files)
    unknown_roles = set(files) - set(expected)
    if not files or unknown_roles:
        raise MultisourceBuildError(
            f"Fichiers invalides pour {metadata.name}: {sorted(files)}."
        )
    for role, path in files.items():
        verify_file(path, expected[role], f"{metadata.name} ({role})")
    ordered_paths = [
        files[role]
        for role, _ in metadata.expected_files
        if role in files
    ]
    words, statistics = loader(*ordered_paths)
    return SourceResult(
        metadata=metadata,
        words=words,
        statistics=statistics,
        files=files,
    )


def corroborate_words(
    base_words: Iterable[str],
    sources: Iterable[SourceResult],
    minimum_attestations: int,
) -> tuple[list[str], dict[str, tuple[str, ...]], dict[str, object]]:
    base_set = set(base_words)
    source_list = list(sources)
    if minimum_attestations < 2:
        raise MultisourceBuildError(
            "La corroboration exige au moins deux attestations externes."
        )
    if minimum_attestations > len(source_list):
        raise MultisourceBuildError(
            f"Seules {len(source_list)} sources sont disponibles pour un "
            f"seuil de {minimum_attestations}."
        )

    attestations: dict[str, list[str]] = defaultdict(list)
    for source in source_list:
        for word in source.words:
            if word not in base_set:
                attestations[word].append(source.metadata.name)

    added_provenance = {
        word: tuple(names)
        for word, names in attestations.items()
        if len(names) >= minimum_attestations
    }
    merged_words = sorted(base_set | set(added_provenance))
    base_builder.validate_words(merged_words)

    exact_combinations: Counter[str] = Counter(
        " + ".join(names) for names in added_provenance.values()
    )
    per_source = {
        source.metadata.name: {
            "normalized_unique_words": len(source.words),
            "added_words_attested": sum(
                source.metadata.name in names
                for names in added_provenance.values()
            ),
            "marginal_validation_contribution": sum(
                source.metadata.name in names
                and len(names) == minimum_attestations
                for names in added_provenance.values()
            ),
        }
        for source in source_list
    }
    statistics: dict[str, object] = {
        "base_word_count": len(base_set),
        "external_candidate_count": len(attestations),
        "added_word_count": len(added_provenance),
        "final_word_count": len(merged_words),
        "minimum_external_attestations": minimum_attestations,
        "per_source": per_source,
        "exact_source_combinations": dict(sorted(exact_combinations.items())),
    }
    return merged_words, dict(sorted(added_provenance.items())), statistics


def encode_provenance(provenance: dict[str, tuple[str, ...]]) -> bytes:
    lines = ["word\tattestation_count\tsources"]
    for word, sources in provenance.items():
        lines.append(f"{word}\t{len(sources)}\t{' ; '.join(sources)}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def make_notice(
    sources: Iterable[SourceResult],
    minimum_attestations: int,
) -> str:
    source_lines = "\n".join(
        f"- {source.metadata.name} ({source.metadata.version}) — "
        f"{source.metadata.license} — {source.metadata.canonical_url}"
        for source in sources
    )
    return (
        f"{CORPUS_NAME} {CORPUS_RELEASE}\n\n"
        "Corpus candidat construit à partir du lexique Morphalou ouvert déjà "
        "embarqué par Lettres & Scores. Une forme nouvelle est ajoutée si "
        f"elle est attestée par au moins {minimum_attestations} sources "
        "externes distinctes après filtrage et normalisation.\n\n"
        "Sources externes :\n"
        f"{source_lines}\n\n"
        "Modifications : exclusion des noms propres explicitement marqués, "
        "catégories techniques, entrées Hunspell KEEPCASE, NOSUGGEST ou "
        "interdites, locutions et formes ponctuées ; développement des "
        "ligatures, suppression des diacritiques, conversion en A-Z, "
        "limitation à 2–15 lettres, corroboration, dédoublonnage et tri.\n\n"
        "L'ODS n'est jamais consulté. La corroboration est un filtre "
        "éditorial automatisé, pas une certification linguistique ni un avis "
        "juridique. Toute redistribution doit conserver les attributions et "
        "respecter cumulativement les conditions applicables à chaque source. "
        "La compatibilité exacte du corpus combiné doit être validée avant une "
        "publication publique.\n"
    )


def source_report(source: SourceResult) -> dict[str, object]:
    expected = dict(source.metadata.expected_files)
    return {
        "name": source.metadata.name,
        "version": source.metadata.version,
        "license": source.metadata.license,
        "canonical_url": source.metadata.canonical_url,
        "files": {
            role: {
                "file_name": path.name,
                "sha256": base_builder.sha256_file(path),
                "expected_sha256": expected[role],
            }
            for role, path in sorted(source.files.items())
        },
        "statistics": source.statistics,
    }


def build(
    base_lexicon: Path,
    sources: list[SourceResult],
    minimum_attestations: int,
    output: Path,
    provenance_output: Path,
    report_output: Path,
    notice_output: Path,
) -> dict[str, object]:
    base_words = read_base_lexicon(base_lexicon)
    merged_words, provenance, validation_statistics = corroborate_words(
        base_words,
        sources,
        minimum_attestations,
    )
    words_contents = base_builder.encode_words(merged_words)
    archive_contents = base_builder.make_zip_archive(words_contents)
    provenance_contents = encode_provenance(provenance)

    write_public_bytes(output, archive_contents)
    write_public_bytes(provenance_output, provenance_contents)
    write_public_text(notice_output, make_notice(sources, minimum_attestations))

    report: dict[str, object] = {
        "corpus": {
            "name": CORPUS_NAME,
            "release": CORPUS_RELEASE,
            "modification_date": MODIFICATION_DATE,
            "status": "candidate",
            "licenses": sorted(
                {"LGPL-LR", *(source.metadata.license for source in sources)}
            ),
        },
        "base": {
            "resource": base_builder.display_path(base_lexicon),
            "resource_sha256": base_builder.sha256_file(base_lexicon),
            "word_count": len(base_words),
            "license": "LGPL-LR",
        },
        "sources": [source_report(source) for source in sources],
        "validation": {
            "policy": "minimum distinct external source attestations",
            "minimum_external_attestations": minimum_attestations,
            "uses_ods": False,
            "exclude_explicit_proper_names": True,
            "exclude_hunspell_keepcase": True,
            "exclude_hunspell_nosuggest": True,
            "alphabet": "A-Z",
            "minimum_length": base_builder.MINIMUM_LENGTH,
            "maximum_length": base_builder.MAXIMUM_LENGTH,
            **validation_statistics,
        },
        "output": {
            "resource": base_builder.display_path(output),
            "member": OUTPUT_MEMBER_NAME,
            "compression": "ZIP avec DEFLATE niveau 9",
            "resource_sha256": base_builder.sha256_bytes(archive_contents),
            "words_sha256": base_builder.sha256_bytes(words_contents),
            "uncompressed_size_bytes": len(words_contents),
            "word_count": len(merged_words),
            "provenance": base_builder.display_path(provenance_output),
            "provenance_sha256": base_builder.sha256_bytes(
                provenance_contents
            ),
            "added_word_count": len(provenance),
        },
    }
    report_text = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    write_public_text(report_output, report_text)
    return report


def write_public_bytes(destination: Path, contents: bytes) -> None:
    """Écrit atomiquement un artefact destiné à être versionné et relu."""
    base_builder.atomic_write_bytes(destination, contents)
    destination.chmod(0o644)


def write_public_text(destination: Path, contents: str) -> None:
    write_public_bytes(destination, contents.encode("utf-8"))


def check_generated_files(
    resource_path: Path,
    provenance_path: Path,
    report_path: Path,
) -> dict[str, object]:
    checked = base_builder.check_generated_files(resource_path, report_path)
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        expected_provenance_hash = report["output"]["provenance_sha256"]
        expected_added_count = report["output"]["added_word_count"]
        expected_base_count = report["base"]["word_count"]
        minimum_attestations = report["validation"][
            "minimum_external_attestations"
        ]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise MultisourceBuildError(
            f"Rapport multisource incomplet: {report_path}"
        ) from error
    require_file(provenance_path, "fichier de provenance")
    actual_provenance_hash = base_builder.sha256_file(provenance_path)
    if actual_provenance_hash != expected_provenance_hash:
        raise MultisourceBuildError(
            "Empreinte du fichier de provenance inattendue: "
            f"{actual_provenance_hash} (attendu: {expected_provenance_hash})"
        )
    if checked["word_count"] != expected_base_count + expected_added_count:
        raise MultisourceBuildError(
            "Le total du corpus ne correspond pas au socle et aux ajouts: "
            f"{checked['word_count']} != {expected_base_count} + "
            f"{expected_added_count}."
        )
    try:
        with zipfile.ZipFile(resource_path) as archive:
            corpus_words = frozenset(
                archive.read(OUTPUT_MEMBER_NAME).decode("ascii").splitlines()
            )
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError) as error:
        raise MultisourceBuildError(
            "Impossible de relire le corpus pendant le contrôle de provenance."
        ) from error
    with provenance_path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        if reader.fieldnames != ["word", "attestation_count", "sources"]:
            raise MultisourceBuildError(
                "En-tête du fichier de provenance invalide."
            )
        previous_word: str | None = None
        added_count = 0
        for row in reader:
            word = row["word"]
            normalized, rejection = normalize_form(word)
            if rejection is not None or normalized != word:
                raise MultisourceBuildError(
                    f"Forme de provenance invalide: {word!r}."
                )
            if word not in corpus_words:
                raise MultisourceBuildError(
                    f"Forme de provenance absente du corpus: {word!r}."
                )
            if previous_word is not None and word <= previous_word:
                raise MultisourceBuildError(
                    "Le fichier de provenance n'est pas strictement trié."
                )
            try:
                attestation_count = int(row["attestation_count"])
            except ValueError as error:
                raise MultisourceBuildError(
                    f"Nombre d'attestations invalide pour {word!r}."
                ) from error
            listed_sources = row["sources"].split(" ; ")
            if (
                attestation_count != len(listed_sources)
                or attestation_count < minimum_attestations
            ):
                raise MultisourceBuildError(
                    f"Provenance incohérente pour {word!r}."
                )
            previous_word = word
            added_count += 1
    if added_count != expected_added_count:
        raise MultisourceBuildError(
            f"Nombre de provenances inattendu: {added_count} "
            f"(attendu: {expected_added_count})."
        )
    return {
        **checked,
        "added_word_count": added_count,
        "provenance_sha256": actual_provenance_hash,
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Construit un corpus candidat en corroborant plusieurs ressources "
            "lexicales ouvertes, sans consulter l'ODS."
        )
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {SCRIPT_VERSION}",
    )
    parser.add_argument("--base-lexicon", type=Path, default=DEFAULT_BASE_LEXICON)
    parser.add_argument("--lefff", type=Path, help="fichier lefff-3.4.mlex")
    parser.add_argument(
        "--unitex",
        type=Path,
        help="ancien mode: Dela_fr.dic décompressé, encodé en UTF-16",
    )
    parser.add_argument("--unitex-bin", type=Path, help="fichier Dela_fr.bin")
    parser.add_argument("--unitex-inf", type=Path, help="fichier Dela_fr.inf")
    parser.add_argument("--grammalecte-aff", type=Path)
    parser.add_argument("--grammalecte-dic", type=Path)
    parser.add_argument(
        "--lexique383",
        type=Path,
        help="Lexique383.txt encodé en ISO-8859-1",
    )
    parser.add_argument(
        "--minimum-attestations",
        type=int,
        default=DEFAULT_MINIMUM_ATTESTATIONS,
    )
    parser.add_argument(
        "--sources-cache",
        type=Path,
        default=DEFAULT_SOURCES_CACHE,
        help=(
            "cache des distributions téléchargées (défaut: "
            ".cache/lexical-sources)"
        ),
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help=(
            "interdit le réseau; les sources non fournies doivent déjà être "
            "valides dans --sources-cache"
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--provenance-output",
        type=Path,
        default=DEFAULT_PROVENANCE_OUTPUT,
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=DEFAULT_REPORT_OUTPUT,
    )
    parser.add_argument(
        "--notice-output",
        type=Path,
        default=DEFAULT_NOTICE_OUTPUT,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="vérifie les sorties existantes sans relire les sources",
    )
    return parser.parse_args()


def collect_sources(arguments: argparse.Namespace) -> list[SourceResult]:
    custom_files: dict[str, dict[str, Path]] = {}
    if arguments.lefff is not None:
        custom_files["lefff"] = {"mlex": arguments.lefff}

    unitex_binary_paths = (arguments.unitex_bin, arguments.unitex_inf)
    if arguments.unitex is not None and any(
        path is not None for path in unitex_binary_paths
    ):
        raise MultisourceBuildError(
            "--unitex ne peut pas être combiné avec --unitex-bin/--unitex-inf."
        )
    if any(path is not None for path in unitex_binary_paths):
        if not all(path is not None for path in unitex_binary_paths):
            raise MultisourceBuildError(
                "--unitex-bin et --unitex-inf doivent être fournis ensemble."
            )
        assert arguments.unitex_bin is not None
        assert arguments.unitex_inf is not None
        custom_files["unitex"] = {
            "bin": arguments.unitex_bin,
            "inf": arguments.unitex_inf,
        }
    elif arguments.unitex is not None:
        custom_files["unitex"] = {"dic": arguments.unitex}

    grammalecte_paths = (
        arguments.grammalecte_aff,
        arguments.grammalecte_dic,
    )
    if any(path is not None for path in grammalecte_paths):
        if not all(path is not None for path in grammalecte_paths):
            raise MultisourceBuildError(
                "--grammalecte-aff et --grammalecte-dic doivent être "
                "fournis ensemble."
            )
        assert arguments.grammalecte_aff is not None
        assert arguments.grammalecte_dic is not None
        custom_files["grammalecte"] = {
            "aff": arguments.grammalecte_aff,
            "dic": arguments.grammalecte_dic,
        }
    if arguments.lexique383 is not None:
        custom_files["lexique383"] = {"txt": arguments.lexique383}

    missing_sources = set(SOURCE_METADATA) - set(custom_files)
    default_files: dict[str, dict[str, Path]] = {}
    if missing_sources:
        default_files = acquire_default_source_files(
            arguments.sources_cache,
            allow_download=not arguments.no_download,
        )
    resolved_files = {**default_files, **custom_files}
    loaders: dict[
        str,
        Callable[..., tuple[frozenset[str], dict[str, int]]],
    ] = {
        "lefff": load_lefff,
        "grammalecte": load_grammalecte,
        "lexique383": load_lexique383,
    }
    sources: list[SourceResult] = []
    for source_key in SOURCE_METADATA:
        files = resolved_files[source_key]
        if source_key == "unitex":
            loader = load_unitex if "dic" in files else load_unitex_binary
        else:
            loader = loaders[source_key]
        sources.append(make_source_result(source_key, files, loader))
    return sources


def main() -> int:
    arguments = parse_arguments()
    if arguments.output.suffix.lower() != ".zip":
        print("Erreur: --output doit désigner une archive .zip.")
        return 2

    print(f"Générateur multisource {SCRIPT_VERSION}")
    print(f"Sortie candidate: {arguments.output}")
    try:
        if arguments.check:
            checked = check_generated_files(
                arguments.output,
                arguments.provenance_output,
                arguments.report_output,
            )
            print(
                f"Corpus valide: {checked['word_count']} formes, dont "
                f"{checked['added_word_count']} ajouts corroborés."
            )
            print(f"SHA-256: {checked['resource_sha256']}")
            return 0

        sources = collect_sources(arguments)
        if len(sources) < arguments.minimum_attestations:
            raise MultisourceBuildError(
                f"Le seuil de {arguments.minimum_attestations} attestations "
                f"exige au moins autant de sources; {len(sources)} fournie(s)."
            )
        report = build(
            base_lexicon=arguments.base_lexicon,
            sources=sources,
            minimum_attestations=arguments.minimum_attestations,
            output=arguments.output,
            provenance_output=arguments.provenance_output,
            report_output=arguments.report_output,
            notice_output=arguments.notice_output,
        )
    except (MultisourceBuildError, OSError, UnicodeError) as error:
        print(f"Erreur: {error}")
        return 1

    output = report["output"]
    assert isinstance(output, dict)
    print(
        f"{output['word_count']} formes écrites, dont "
        f"{output['added_word_count']} ajouts corroborés."
    )
    print(f"SHA-256: {output['resource_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
