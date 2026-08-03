import tempfile
import unittest
from pathlib import Path

from engine import RackError, WordFinder, normalize_rack


WORDS = """AA
AXE
CHAT
CHATS
JAZZ
TAXI
ZOO
"""


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.word_file = Path(self.temporary.name) / "words.txt"
        self.word_file.write_text(WORDS, encoding="utf8")
        self.finder = WordFinder(self.word_file)

    def tearDown(self):
        self.temporary.cleanup()

    def test_normalization_accepts_accents_and_separators(self):
        self.assertEqual(normalize_rack("ç, h â t ?"), ("CHAT", 1))

    def test_normalization_rejects_too_many_jokers(self):
        with self.assertRaises(RackError):
            normalize_rack("ABC???")

    def test_longest_words(self):
        result = self.finder.search("CHATS")
        self.assertEqual(result.longest[0].word, "CHATS")
        self.assertEqual(result.longest[0].score, 10)
        self.assertGreaterEqual(result.possible_count, 2)

    def test_highest_score(self):
        result = self.finder.search("JAZZ")
        self.assertEqual(result.highest_scoring[0].word, "JAZZ")
        self.assertEqual(result.highest_scoring[0].score, 29)

    def test_joker_scores_zero(self):
        result = self.finder.search("JAZ?")
        jazz = next(item for item in result.highest_scoring if item.word == "JAZZ")
        self.assertEqual(jazz.score, 19)


if __name__ == "__main__":
    unittest.main()

