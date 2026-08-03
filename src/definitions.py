"""Accès facultatif aux définitions françaises du Wiktionnaire."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import json
import re
import socket
import ssl
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen


API_URL = "https://fr.wiktionary.org/w/api.php"
USER_AGENT = (
    "LettresEtScores/1.1 "
    "(desktop educational word game; bart.jourquin@gmail.com) Python-urllib"
)

POS_PREFIXES = (
    "adjectif",
    "adverbe",
    "article",
    "conjonction",
    "determinant",
    "formede",
    "interjection",
    "lettre",
    "nomcommun",
    "nompropre",
    "particule",
    "preposition",
    "pronom",
    "symbole",
    "verbe",
)


def _normalized(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFD", value).upper()
        if not unicodedata.combining(character) and "A" <= character <= "Z"
    )


def _plain_heading(value: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", value)).strip()


@dataclass(frozen=True, slots=True)
class DefinitionResult:
    requested_word: str
    title: str
    part_of_speech: str
    definitions: tuple[str, ...]
    url: str


class WiktionaryNetworkError(ConnectionError):
    """Erreur réseau dont le message peut être présenté directement à l'utilisateur."""


class _DefinitionParser(HTMLParser):
    """Extrait les éléments de premier niveau de la première liste ordonnée."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_target_ol = False
        self.finished = False
        self.list_depth = 0
        self.in_item = False
        self.current: list[str] = []
        self.definitions: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "ol":
            if not self.in_target_ol:
                if self.finished:
                    return
                self.in_target_ol = True
                self.list_depth = 1
            else:
                self.list_depth += 1
            return

        if not self.in_target_ol:
            return
        if tag == "ul":
            self.list_depth += 1
        elif tag == "li" and self.list_depth == 1 and not self.in_item:
            self.in_item = True
            self.current = []
        elif self.in_item and tag == "br" and self.list_depth == 1:
            self.current.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if not self.in_target_ol:
            return
        if tag == "li" and self.in_item and self.list_depth == 1:
            text = re.sub(r"\s+", " ", "".join(self.current)).strip()
            text = re.sub(r"\s*\[[0-9]+\]\s*", " ", text).strip()
            if text:
                self.definitions.append(text)
            self.in_item = False
            self.current = []
        elif tag in {"ul", "ol"}:
            self.list_depth -= 1
            if self.list_depth == 0:
                self.in_target_ol = False
                self.finished = True

    def handle_data(self, data: str) -> None:
        if self.in_item and self.list_depth == 1:
            self.current.append(data)


class WiktionaryClient:
    def __init__(self, timeout: float = 8.0, max_attempts: int = 3):
        if max_attempts < 1:
            raise ValueError("Le nombre de tentatives doit être positif.")
        self.timeout = timeout
        self.max_attempts = max_attempts
        self._cache: dict[str, DefinitionResult] = {}

    def _request(self, parameters: dict[str, str]) -> dict:
        query = urlencode({"format": "json", "utf8": "1", **parameters})
        request = Request(
            f"{API_URL}?{query}",
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        for attempt in range(self.max_attempts):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    return json.load(response)
            except HTTPError as exc:
                retryable = exc.code == 429 or 500 <= exc.code < 600
                if retryable and attempt + 1 < self.max_attempts:
                    delay = 0.5 * (2**attempt)
                    if exc.code == 429:
                        try:
                            delay = min(float(exc.headers.get("Retry-After", delay)), 3.0)
                        except (TypeError, ValueError):
                            pass
                    time.sleep(delay)
                    continue
                if exc.code == 429:
                    detail = "trop de requêtes ont été envoyées"
                else:
                    detail = str(exc.reason or "réponse refusée")
                raise WiktionaryNetworkError(
                    f"Le Wiktionnaire a répondu avec l’erreur HTTP {exc.code} "
                    f"({detail})."
                ) from exc
            except (socket.timeout, TimeoutError) as exc:
                if attempt + 1 < self.max_attempts:
                    time.sleep(0.5 * (2**attempt))
                    continue
                raise WiktionaryNetworkError(
                    f"Le Wiktionnaire n’a pas répondu dans les {self.timeout:g} secondes. "
                    "Vérifiez la connexion Internet, puis réessayez."
                ) from exc
            except (URLError, ssl.SSLError) as exc:
                reason = getattr(exc, "reason", exc)
                reason_text = str(reason)
                certificate_error = isinstance(
                    reason, ssl.SSLCertVerificationError
                ) or "CERTIFICATE_VERIFY_FAILED" in reason_text.upper()
                if not certificate_error and attempt + 1 < self.max_attempts:
                    time.sleep(0.5 * (2**attempt))
                    continue
                if certificate_error:
                    message = (
                        "La vérification du certificat SSL a échoué. Sur macOS, "
                        "si Python provient de python.org, exécutez « Install "
                        "Certificates.command » dans le dossier Applications/Python 3.x, "
                        "puis relancez l’application."
                    )
                else:
                    message = (
                        "Erreur réseau lors de la connexion au Wiktionnaire. "
                        "Vérifiez la connexion Internet, le pare-feu et le proxy."
                    )
                raise WiktionaryNetworkError(
                    f"{message}\n\nDétail technique : {reason_text}"
                ) from exc
            except json.JSONDecodeError as exc:
                raise WiktionaryNetworkError(
                    "Le Wiktionnaire a renvoyé une réponse illisible "
                    f"(JSON invalide à la ligne {exc.lineno})."
                ) from exc

        raise AssertionError("Boucle de requête terminée sans résultat.")

    def _candidate_titles(self, word: str) -> list[str]:
        data = self._request(
            {
                "action": "query",
                "list": "search",
                "srsearch": f"intitle:{word.lower()}",
                "srnamespace": "0",
                "srlimit": "10",
            }
        )
        titles = [word.lower()]
        titles.extend(item["title"] for item in data.get("query", {}).get("search", []))

        unique: list[str] = []
        for title in titles:
            if _normalized(title) == word and title not in unique:
                unique.append(title)
        unique.sort(key=lambda title: (title != title.lower(), title != word.lower()))
        return unique

    def _french_section(self, title: str) -> tuple[str, str, str] | None:
        data = self._request(
            {
                "action": "parse",
                "page": title,
                "prop": "sections",
                "redirects": "1",
            }
        )
        parsed = data.get("parse")
        if not parsed:
            return None

        in_french = False
        for section in parsed.get("sections", []):
            level = section.get("level")
            heading = _plain_heading(section.get("line", ""))
            normalized_heading = _normalized(heading).lower()
            if level == "2":
                in_french = normalized_heading == "francais"
                continue
            if in_french and level == "3" and normalized_heading.startswith(POS_PREFIXES):
                return parsed["title"], section["index"], heading
        return None

    def get(self, raw_word: str) -> DefinitionResult:
        word = _normalized(raw_word)
        if not word:
            raise LookupError("Mot vide.")
        if word in self._cache:
            return self._cache[word]

        selected = None
        for candidate_title in self._candidate_titles(word):
            selected = self._french_section(candidate_title)
            if selected:
                break
        if not selected:
            raise LookupError("Aucune définition française n’a été trouvée.")

        canonical_title, section_index, part_of_speech = selected
        data = self._request(
            {
                "action": "parse",
                "page": canonical_title,
                "prop": "text",
                "section": section_index,
                "disableeditsection": "1",
                "redirects": "1",
            }
        )
        html = data.get("parse", {}).get("text", {}).get("*", "")
        parser = _DefinitionParser()
        parser.feed(html)
        definitions = tuple(parser.definitions[:5])
        if not definitions:
            raise LookupError("La page existe, mais sa définition n’a pas pu être extraite.")

        result = DefinitionResult(
            requested_word=word,
            title=canonical_title,
            part_of_speech=part_of_speech,
            definitions=definitions,
            url="https://fr.wiktionary.org/wiki/" + quote(
                canonical_title.replace(" ", "_"), safe="_"
            ),
        )
        self._cache[word] = result
        return result
