# python -m unittest tests/test_process_trees.py

import unittest
import re
from pathlib import Path

class TestDataProcessTrees(unittest.TestCase):
    base_path = Path("data/treebank_3_flat")
    splits = ["train", "dev", "test"]

    def test_fluent_disfluent_parallel_structure(self):
        for split in self.splits:
            fluent_dir = self.base_path / split / "fluent"
            disfluent_dir = self.base_path / split / "disfluent"

            self.assertTrue(fluent_dir.exists(), f"{fluent_dir} does not exist")
            self.assertTrue(disfluent_dir.exists(), f"{disfluent_dir} does not exist")

            fluent_files = sorted(fluent_dir.glob("*.txt"))
            disfluent_files = sorted(disfluent_dir.glob("*.txt"))

            fluent_names = [f.name for f in fluent_files]
            disfluent_names = [f.name for f in disfluent_files]

            self.assertEqual(
                fluent_names, disfluent_names,
                f"Mismatch in filenames for split '{split}'"
            )

    def test_sep_token_alignment(self):
        for split in self.splits:
            fluent_dir = self.base_path / split / "fluent"
            disfluent_dir = self.base_path / split / "disfluent"

            for fluent_file in fluent_dir.glob("*.txt"):
                disfluent_file = disfluent_dir / fluent_file.name
                fluent_text = fluent_file.read_text(encoding="utf-8")
                disfluent_text = disfluent_file.read_text(encoding="utf-8")

                fluent_seps = re.findall(r"<SEP\d+>", fluent_text)
                disfluent_seps = re.findall(r"<SEP\d+>", disfluent_text)

                self.assertEqual(
                    fluent_seps, disfluent_seps,
                    f"Mismatch in SEP tokens in file {fluent_file.name} of split {split}"
                )

    def test_file_not_empty(self):
        for split in self.splits:
            for kind in ["fluent", "disfluent"]:
                for f in (self.base_path / split / kind).glob("*.txt"):
                    content = f.read_text(encoding="utf-8").strip()
                    self.assertTrue(len(content) > 0, f"{f} is empty")

    def test_expected_file_ids_per_split(self):
        split_patterns = {
            "train": re.compile(r"sw[23]\d+\.txt$"),
            "dev": re.compile(r"sw4[5-9]\d+\.txt$"),
            "test": re.compile(r"sw4[0-1]\d+\.txt$"),
        }

        for split, pattern in split_patterns.items():
            fluent_dir = self.base_path / split / "fluent"
            self.assertTrue(fluent_dir.exists(), f"{fluent_dir} missing")

            bad_files = []
            for file in fluent_dir.glob("*.txt"):
                if not pattern.match(file.name):
                    bad_files.append(file.name)

            self.assertFalse(
                bad_files,
                f"Found invalid files in {split} split: {bad_files}"
            )

if __name__ == "__main__":
    unittest.main()
