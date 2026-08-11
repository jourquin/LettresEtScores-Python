import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from collections import Counter
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "build_open_lexicon.py"
SPEC = importlib.util.spec_from_file_location("build_open_lexicon", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class NormalizeFormTests(unittest.TestCase):
    def test_normalizes_accents_and_ligatures(self):
        self.assertEqual(builder.normalize_form("été"), ("ETE", None))
        self.assertEqual(builder.normalize_form("cœur"), ("COEUR", None))
        self.assertEqual(builder.normalize_form("cæcum"), ("CAECUM", None))

    def test_rejects_non_simple_forms(self):
        self.assertEqual(
            builder.normalize_form("arc-en-ciel"),
            (None, "not_simple"),
        )
        self.assertEqual(
            builder.normalize_form("l'été"),
            (None, "not_simple"),
        )
        self.assertEqual(
            builder.normalize_form("j3"),
            (None, "not_simple"),
        )

    def test_rejects_unsupported_characters_and_lengths(self):
        self.assertEqual(
            builder.normalize_form("µcal"),
            (None, "unsupported_character"),
        )
        self.assertEqual(builder.normalize_form("a"), (None, "too_short"))
        self.assertEqual(
            builder.normalize_form("abcdefghijklmnop"),
            (None, "too_long"),
        )


class ReproducibleResourceTests(unittest.TestCase):
    def test_resource_is_reproducible_and_decodable(self):
        statistics = Counter({"unique_words": 2, "source_rows": 2})

        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.zip"
            second = Path(directory) / "second.zip"

            builder.write_zip_resource(
                first,
                ["CHAT", "CHATS"],
                statistics,
            )
            builder.write_zip_resource(
                second,
                ["CHAT", "CHATS"],
                statistics,
            )

            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(
                    archive.namelist(),
                    ["lexique-francais.txt"],
                )
                self.assertEqual(
                    archive.read("lexique-francais.txt"),
                    b"CHAT\nCHATS\n",
                )

    def test_rejects_unsorted_or_invalid_word_lists(self):
        with self.assertRaises(builder.CorpusBuildError):
            builder.validate_words(["CHATS", "CHAT"])

        with self.assertRaises(builder.CorpusBuildError):
            builder.validate_words(["CHAT", "CHAT"])

        with self.assertRaises(builder.CorpusBuildError):
            builder.validate_words(["ÉTÉ"])

    def test_check_generated_files_uses_report_hashes(self):
        statistics = Counter({"unique_words": 2, "source_rows": 2})

        with tempfile.TemporaryDirectory() as directory:
            resource = Path(directory) / "lexique.zip"
            report_path = Path(directory) / "report.json"
            manifest = builder.write_zip_resource(
                resource,
                ["CHAT", "CHATS"],
                statistics,
            )
            report = {
                **manifest,
                "output": {
                    **manifest["output"],
                    "resource_sha256": builder.sha256_file(resource),
                },
            }
            report_path.write_text(
                json.dumps(report),
                encoding="utf-8",
            )

            checked = builder.check_generated_files(resource, report_path)

            self.assertEqual(checked["word_count"], 2)
            self.assertEqual(
                checked["resource_sha256"],
                builder.sha256_file(resource),
            )


class CommandLineInterfaceTests(unittest.TestCase):
    def test_version_identifies_zip_generator(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--version"],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            completed.stdout.strip(),
            "build_open_lexicon.py 2.1.0-zip",
        )

    def test_non_zip_output_is_rejected(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--output",
                "lexique-francais.deflate",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("doit désigner une archive .zip", completed.stdout)


if __name__ == "__main__":
    unittest.main()
