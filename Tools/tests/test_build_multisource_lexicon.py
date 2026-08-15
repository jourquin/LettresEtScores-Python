import json
import io
import subprocess
import sys
import tarfile
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock


TOOLS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(TOOLS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIRECTORY))

import build_multisource_lexicon as builder
import build_open_lexicon as base_builder


SCRIPT_PATH = TOOLS_DIRECTORY / "build_multisource_lexicon.py"


class SourceLoaderTests(unittest.TestCase):
    def test_lefff_excludes_proper_names_and_normalizes_forms(self):
        contents = (
            "Paris\tnp\tParis\tms\n"
            "cœur\tnc\tcœur\tms\n"
            "mangeaient\tv\tmanger\tP3p\n"
            "arc-en-ciel\tnc\tarc-en-ciel\tms\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lefff.mlex"
            path.write_text(contents, encoding="utf-8")
            words, statistics = builder.load_lefff(path)

        self.assertEqual(words, frozenset({"COEUR", "MANGEAIENT"}))
        self.assertEqual(statistics["rejected_category"], 1)
        self.assertEqual(statistics["rejected_not_simple"], 1)

    def test_unitex_variable_length_values(self):
        fixtures = {
            bytes([0x7F]): 0x7F,
            bytes([0x80 | 0x1F, 0x01]): 0x3F,
            bytes([0xA0 | 0x1F, 0x02, 0x01]): 0x205F,
        }
        for encoded, expected in fixtures.items():
            with self.subTest(encoded=encoded):
                value, position = builder.read_unitex_variable(encoded, 0)
                self.assertEqual(value, expected)
                self.assertEqual(position, len(encoded))

    def test_unitex_excludes_proper_names_and_technical_categories(self):
        contents = (
            "Paris,Paris.N+Hum+NPropre:ms\n"
            "chats,chat.N:mp\n"
            "mangeaient,manger.V:P3p\n"
            "anti,anti.PFX\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unitex.dic"
            path.write_text(contents, encoding="utf-16")
            words, statistics = builder.load_unitex(path)

        self.assertEqual(words, frozenset({"CHATS", "MANGEAIENT"}))
        self.assertEqual(statistics["rejected_proper_name"], 1)
        self.assertEqual(statistics["rejected_category"], 1)

    def test_hunspell_expands_affixes_and_applies_safety_flags(self):
        aff = """\
SET UTF-8
FLAG long
NEEDAFFIX ()
FORBIDDENWORD {}
KEEPCASE ||
NOSUGGEST --
SFX S. Y 1
SFX S. 0 s .
"""
        dic = """\
4
chat/S.
Paris/||
secret/--
arc-en-ciel
"""
        with tempfile.TemporaryDirectory() as directory:
            aff_path = Path(directory) / "fr.aff"
            dic_path = Path(directory) / "fr.dic"
            aff_path.write_text(aff, encoding="utf-8")
            dic_path.write_text(dic, encoding="utf-8")
            words, statistics = builder.load_grammalecte(
                aff_path,
                dic_path,
            )

        self.assertEqual(words, frozenset({"CHAT", "CHATS"}))
        self.assertEqual(statistics["rejected_keep_case"], 1)
        self.assertEqual(statistics["rejected_no_suggest"], 1)
        self.assertEqual(statistics["rejected_not_simple"], 1)


class CorroborationTests(unittest.TestCase):
    @staticmethod
    def make_source(name, words):
        metadata = builder.SourceMetadata(
            key=name.lower(),
            name=name,
            version="test",
            license="test",
            canonical_url="https://example.invalid/",
            expected_files=(),
        )
        return builder.SourceResult(
            metadata=metadata,
            words=frozenset(words),
            statistics={"unique_words": len(words)},
            files={},
        )

    def test_adds_only_forms_seen_in_two_external_sources(self):
        sources = [
            self.make_source("Source A", {"CHAT", "CHIEN", "LION"}),
            self.make_source("Source B", {"CHIEN", "TIGRE"}),
            self.make_source("Source C", {"CHIEN", "LION"}),
        ]
        words, provenance, statistics = builder.corroborate_words(
            ["CHAT", "CHATS"],
            sources,
            minimum_attestations=2,
        )

        self.assertEqual(words, ["CHAT", "CHATS", "CHIEN", "LION"])
        self.assertEqual(
            provenance,
            {
                "CHIEN": ("Source A", "Source B", "Source C"),
                "LION": ("Source A", "Source C"),
            },
        )
        self.assertEqual(statistics["added_word_count"], 2)
        self.assertEqual(statistics["final_word_count"], 4)

    def test_rejects_a_single_source_threshold(self):
        with self.assertRaises(builder.MultisourceBuildError):
            builder.corroborate_words(
                ["CHAT"],
                [self.make_source("Source A", {"CHIEN"})],
                minimum_attestations=1,
            )


class OutputTests(unittest.TestCase):
    @staticmethod
    def make_file_source(directory, name, words):
        source_path = directory / f"{name}.txt"
        source_path.write_text("test\n", encoding="utf-8")
        digest = base_builder.sha256_file(source_path)
        metadata = builder.SourceMetadata(
            key=name.lower(),
            name=name,
            version="test",
            license="Test-License",
            canonical_url="https://example.invalid/",
            expected_files=(("data", digest),),
        )
        return builder.SourceResult(
            metadata=metadata,
            words=frozenset(words),
            statistics={"unique_words": len(words)},
            files={"data": source_path},
        )

    def test_builds_and_checks_reproducible_audit_outputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            base_path = directory / "base.zip"
            base_builder.write_zip_resource(
                base_path,
                ["CHAT", "CHATS"],
                Counter({"unique_words": 2}),
            )
            sources = [
                self.make_file_source(
                    directory,
                    "SourceA",
                    {"CHAT", "CHIEN", "LION"},
                ),
                self.make_file_source(
                    directory,
                    "SourceB",
                    {"CHIEN", "TIGRE"},
                ),
            ]
            output = directory / "multisource.zip"
            provenance = directory / "provenance.tsv"
            report = directory / "report.json"
            notice = directory / "notice.txt"

            generated = builder.build(
                base_path,
                sources,
                2,
                output,
                provenance,
                report,
                notice,
            )
            first_archive = output.read_bytes()
            checked = builder.check_generated_files(
                output,
                provenance,
                report,
            )
            builder.build(
                base_path,
                sources,
                2,
                output,
                provenance,
                report,
                notice,
            )

            self.assertEqual(first_archive, output.read_bytes())
            self.assertEqual(generated["output"]["word_count"], 3)
            self.assertEqual(checked["word_count"], 3)
            self.assertEqual(checked["added_word_count"], 1)
            self.assertEqual(
                provenance.read_text(encoding="utf-8").splitlines(),
                [
                    "word\tattestation_count\tsources",
                    "CHIEN\t2\tSourceA ; SourceB",
                ],
            )
            parsed_report = json.loads(report.read_text(encoding="utf-8"))
            self.assertFalse(parsed_report["validation"]["uses_ods"])


class CommandLineInterfaceTests(unittest.TestCase):
    def test_version(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            completed.stdout.strip(),
            "build_multisource_lexicon.py 1.1.0",
        )

    def test_no_download_requires_a_complete_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--no-download",
                    "--sources-cache",
                    directory,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("absent ou invalide dans le cache", completed.stdout)


class AcquisitionTests(unittest.TestCase):
    def test_valid_cached_download_does_not_use_network(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source.dat"
            destination.write_bytes(b"source fixture")
            expected = base_builder.sha256_file(destination)
            with mock.patch.object(
                builder.urllib.request,
                "urlopen",
                side_effect=AssertionError("network must not be used"),
            ):
                resolved = builder.download_file(
                    "https://example.invalid/source.dat",
                    destination,
                    expected,
                    "fixture",
                )
        self.assertEqual(resolved, destination)

    def test_extracts_only_the_named_tar_member(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "source.tgz"
            contents = b"lexical data\n"
            with tarfile.open(archive_path, "w:gz") as archive:
                info = tarfile.TarInfo("package/data.txt")
                info.size = len(contents)
                archive.addfile(info, io.BytesIO(contents))
                unwanted = tarfile.TarInfo("../outside.txt")
                unwanted.size = 3
                archive.addfile(unwanted, io.BytesIO(b"bad"))
            destination = root / "data.txt"
            resolved = builder.extract_tar_member(
                archive_path,
                "package/data.txt",
                destination,
                base_builder.sha256_bytes(contents),
                "fixture",
            )

            self.assertEqual(resolved.read_bytes(), contents)
            self.assertFalse((root.parent / "outside.txt").exists())


if __name__ == "__main__":
    unittest.main()
