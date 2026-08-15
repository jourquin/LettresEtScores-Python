import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app


class CommandLineTests(unittest.TestCase):
    def test_default_corpus_is_the_open_morphalou_lexicon(self):
        arguments = app.parse_arguments([])

        self.assertEqual(arguments.corpus, app.DEFAULT_CORPUS)
        self.assertEqual(arguments.corpus.name, "lexique-francais.zip")

    def test_corpus_option_accepts_a_relative_path(self):
        arguments = app.parse_arguments(
            ["--corpus", "src/data/lexique-francais-multisources.zip"]
        )

        self.assertEqual(
            arguments.corpus,
            Path("src/data/lexique-francais-multisources.zip"),
        )

    def test_main_passes_the_resolved_corpus_to_the_application(self):
        with tempfile.TemporaryDirectory() as directory:
            corpus_path = Path(directory) / "custom.zip"
            corpus_path.write_bytes(b"fixture")
            with mock.patch.object(app, "App") as application:
                result = app.main(["--corpus", str(corpus_path)])

        self.assertEqual(result, 0)
        application.assert_called_once_with(corpus_path.resolve())
        application.return_value.mainloop.assert_called_once_with()

    def test_main_reports_a_missing_corpus_without_starting_tk(self):
        missing = Path("missing-corpus.zip").resolve()
        with (
            mock.patch.object(app, "App") as application,
            mock.patch.object(app.messagebox, "showerror") as showerror,
        ):
            result = app.main(["--corpus", str(missing)])

        self.assertEqual(result, 1)
        application.assert_not_called()
        showerror.assert_called_once()
        self.assertIn(str(missing), showerror.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
