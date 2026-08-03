import unittest

from definitions import _DefinitionParser, _normalized


SAMPLE_HTML = """
<div>
  <h3>Nom commun</h3>
  <ol>
    <li>(Jeux) Première définition.
      <ul><li>Exemple qui ne doit pas être retenu.</li></ul>
    </li>
    <li>Deuxième définition avec <a href="#">un lien</a>.</li>
  </ol>
  <h4>Synonymes</h4>
  <ol><li>Cette autre liste doit être ignorée.</li></ol>
</div>
"""


class DefinitionParserTests(unittest.TestCase):
    def test_accent_insensitive_normalization(self):
        self.assertEqual(_normalized("Été"), "ETE")

    def test_extracts_definitions_but_not_examples(self):
        parser = _DefinitionParser()
        parser.feed(SAMPLE_HTML)
        self.assertEqual(
            parser.definitions,
            [
                "(Jeux) Première définition.",
                "Deuxième définition avec un lien.",
            ],
        )


if __name__ == "__main__":
    unittest.main()
