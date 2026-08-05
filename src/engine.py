"""Moteur de recherche de mots et calcul des points du Scrabble français."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from time import perf_counter
import unicodedata


LETTER_POINTS = {
    **dict.fromkeys("AEILNORSTU", 1),
    **dict.fromkeys("DGM", 2),
    **dict.fromkeys("BCP", 3),
    **dict.fromkeys("FHV", 4),
    **dict.fromkeys("JQ", 8),
    **dict.fromkeys("KWXYZ", 10),
}
POINTS_BY_INDEX = tuple(LETTER_POINTS[chr(65 + index)] for index in range(26))


class RackError(ValueError):
    """Erreur de validation des lettres fournies par l'utilisateur."""


class ConstraintError(ValueError):
    """Erreur de syntaxe dans une contrainte d'expression régulière."""


@dataclass(frozen=True, slots=True)
class Candidate:
    word: str
    length: int
    score: int


@dataclass(frozen=True, slots=True)
class SearchResult:
    longest: tuple[Candidate, ...]
    highest_scoring: tuple[Candidate, ...]
    possible_count: int
    elapsed_seconds: float
    normalized_letters: str
    joker_count: int


@dataclass(frozen=True, slots=True)
class _Entry:
    word: str
    counts: bytes
    base_score: int


def _ascii_letters(value: str) -> str:
    value = value.replace("œ", "oe").replace("Œ", "OE")
    value = value.replace("æ", "ae").replace("Æ", "AE")
    return "".join(
        character
        for character in unicodedata.normalize("NFD", value).upper()
        if not unicodedata.combining(character)
    )


def normalize_rack(raw: str) -> tuple[str, int]:
    """Normalise un tirage et renvoie (lettres, nombre_de_jokers)."""

    normalized = _ascii_letters(raw)
    letters: list[str] = []
    jokers = 0

    for character in normalized:
        if "A" <= character <= "Z":
            letters.append(character)
        elif character in "?*":
            jokers += 1
        elif character.isspace() or character in ",;-_/":
            continue
        else:
            raise RackError(f"Caractère non reconnu : {character!r}")

    tile_count = len(letters) + jokers
    if tile_count < 2:
        raise RackError("Introduisez au moins deux lettres.")
    if tile_count > 15:
        raise RackError("Le tirage ne peut pas dépasser quinze lettres.")
    if jokers > 2:
        raise RackError("Un tirage peut contenir au maximum deux jokers.")

    return "".join(letters), jokers


def compile_constraints(raw: str) -> tuple[re.Pattern[str], ...]:
    """Compile des motifs séparés par « ; », qui devront tous correspondre."""

    patterns: list[re.Pattern[str]] = []
    for raw_pattern in raw.split(";"):
        pattern = raw_pattern.strip()
        if not pattern:
            continue
        try:
            patterns.append(re.compile(pattern, re.IGNORECASE))
        except re.error as exc:
            detail = getattr(exc, "msg", str(exc))
            raise ConstraintError(
                f"Contrainte invalide {pattern!r} : {detail}."
            ) from exc
    return tuple(patterns)


class WordFinder:
    """Index compact d'une liste de mots normalisés A-Z."""

    def __init__(self, word_file: str | Path):
        self.word_file = Path(word_file)
        self._by_length: list[list[_Entry]] = [[] for _ in range(16)]
        self.word_count = 0
        self._load()

    def _load(self) -> None:
        seen: set[str] = set()
        with self.word_file.open("r", encoding="utf8") as stream:
            for line_number, line in enumerate(stream, start=1):
                word = line.strip().upper()
                if not word:
                    continue
                if not 2 <= len(word) <= 15 or not word.isascii() or not word.isalpha():
                    raise ValueError(
                        f"Mot invalide à la ligne {line_number} : {word!r}"
                    )
                if word in seen:
                    continue
                seen.add(word)

                counts = bytearray(26)
                base_score = 0
                for character in word:
                    index = ord(character) - 65
                    counts[index] += 1
                    base_score += POINTS_BY_INDEX[index]
                self._by_length[len(word)].append(
                    _Entry(word, bytes(counts), base_score)
                )

        self.word_count = len(seen)

    @staticmethod
    def _insert_best(
        candidates: list[Candidate],
        candidate: Candidate,
        *,
        key,
        limit: int,
    ) -> None:
        candidates.append(candidate)
        candidates.sort(key=key)
        del candidates[limit:]

    def search(
        self,
        raw_letters: str,
        limit: int = 10,
        raw_constraints: str = "",
    ) -> SearchResult:
        if limit < 1:
            raise ValueError("La limite doit être positive.")

        started = perf_counter()
        letters, jokers = normalize_rack(raw_letters)
        constraints = compile_constraints(raw_constraints)
        rack_counts = [0] * 26
        for character in letters:
            rack_counts[ord(character) - 65] += 1

        longest: list[Candidate] = []
        highest: list[Candidate] = []
        possible_count = 0
        max_length = min(15, len(letters) + jokers)

        for length in range(2, max_length + 1):
            for entry in self._by_length[length]:
                if any(pattern.search(entry.word) is None for pattern in constraints):
                    continue

                missing = 0
                joker_penalty = 0
                for index, required in enumerate(entry.counts):
                    deficit = required - rack_counts[index]
                    if deficit > 0:
                        missing += deficit
                        if missing > jokers:
                            break
                        joker_penalty += deficit * POINTS_BY_INDEX[index]
                else:
                    possible_count += 1
                    candidate = Candidate(
                        entry.word,
                        length,
                        entry.base_score - joker_penalty,
                    )
                    self._insert_best(
                        longest,
                        candidate,
                        key=lambda item: (-item.length, -item.score, item.word),
                        limit=limit,
                    )
                    self._insert_best(
                        highest,
                        candidate,
                        key=lambda item: (-item.score, -item.length, item.word),
                        limit=limit,
                    )

        return SearchResult(
            longest=tuple(longest),
            highest_scoring=tuple(highest),
            possible_count=possible_count,
            elapsed_seconds=perf_counter() - started,
            normalized_letters=letters,
            joker_count=jokers,
        )
