import tempfile
import unittest
from pathlib import Path

from engine import (
    ConstraintError,
    RackError,
    WordFinder,
    compile_constraints,
    normalize_rack,
)


WORDS = """AA
AB
AC
AD
AE
AF
AG
AH
AI
AJ
AK
AL
AXE
CHAT
CHATS
JAZZ
JURA
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

    def test_default_result_limit_is_ten(self):
        result = self.finder.search("ABCDEFGHIJKLMNO")
        self.assertEqual(len(result.longest), 10)
        self.assertEqual(len(result.highest_scoring), 10)

    def test_semicolon_separated_constraints_are_compiled(self):
        patterns = compile_constraints("^j ; ^..r ; a$")
        self.assertEqual(len(patterns), 3)
        self.assertTrue(all(pattern.search("JURA") for pattern in patterns))

    def test_mandatory_letter_can_be_anywhere(self):
        result = self.finder.search("C,H,A,T,S", raw_constraints="s")
        self.assertEqual([item.word for item in result.longest], ["CHATS"])

    def test_first_and_third_positions_are_enforced(self):
        result = self.finder.search(
            "C,H,A,T,S",
            raw_constraints="^c ; ^..a",
        )
        self.assertGreater(result.possible_count, 0)
        self.assertTrue(
            all(
                item.word.startswith("C") and item.word[2] == "A"
                for item in result.longest
            )
        )

    def test_last_letter_is_enforced(self):
        result = self.finder.search("C,H,A,T,S", raw_constraints="s$")
        self.assertEqual([item.word for item in result.longest], ["CHATS"])

    def test_penultimate_letter_is_enforced(self):
        result = self.finder.search("C,H,A,T,S", raw_constraints="t.$")
        self.assertEqual([item.word for item in result.longest], ["CHATS"])

    def test_exact_length_and_second_letter_are_enforced(self):
        pattern = compile_constraints("^.e..$")[0]
        self.assertIsNotNone(pattern.search("TEST"))
        self.assertIsNone(pattern.search("CHAT"))
        self.assertIsNone(pattern.search("TESTS"))

    def test_combined_example_finds_jura(self):
        result = self.finder.search(
            "A,J,U,R,F,O,A",
            raw_constraints="^j ; ^..r ; a$",
        )
        self.assertEqual([item.word for item in result.longest], ["JURA"])

    def test_constraint_does_not_add_a_tile(self):
        result = self.finder.search("H,A,T", raw_constraints="^c")
        self.assertEqual(result.possible_count, 0)

    def test_invalid_regular_expression_is_rejected(self):
        with self.assertRaises(ConstraintError):
            compile_constraints("^[a")

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
