# python -m unittest tests.test_data_generate_kshot

import unittest
import tempfile
import json
import re
from pathlib import Path
from disfluency_removal.data_3_generate_kshot import *

class TestDataGenerateKshot(unittest.TestCase):
    def setUp(self):
        self.k = 3
        self.seed = 42
        self.modes = ["full", "segment"]

    def load_jsonl(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f]

    def test_content_quality(self):
        for mode in self.modes:
            with self.subTest(mode=mode):
                with tempfile.TemporaryDirectory() as tmpdir:
                    generate_kshot_file(k=self.k, seed=self.seed, mode=mode, output_dir=tmpdir)
                    file_path = Path(tmpdir) / f"kshot_k={self.k}_{mode}_train.jsonl"
                    self.assertTrue(file_path.exists())

                    data = self.load_jsonl(file_path)
                    self.assertEqual(len(data), self.k)

                    seen_filenames = set()

                    for entry in data:
                        # Basic field presence and non-empty
                        self.assertIn("filename", entry)
                        self.assertIn("disfluent", entry)
                        self.assertIn("fluent", entry)
                        self.assertTrue(entry["disfluent"].strip(), "Disfluent field is empty")
                        self.assertTrue(entry["fluent"].strip(), "Fluent field is empty")

                        # Filename uniqueness
                        self.assertNotIn(entry["filename"], seen_filenames)
                        seen_filenames.add(entry["filename"])

                        # Mode-specific checks
                        if mode == "full":
                            # Should not contain any SEP tokens
                            self.assertNotRegex(entry["disfluent"], r"<SEP\d+>")
                            self.assertNotRegex(entry["fluent"], r"<SEP\d+>")
                        elif mode == "segment":
                            # Segment content should be plausibly similar
                            dis_words = set(entry["disfluent"].lower().split())
                            fl_words = set(entry["fluent"].lower().split())
                            common = dis_words & fl_words
                            self.assertGreater(len(common), 2, f"Low overlap in segment: {entry['filename']}")

if __name__ == "__main__":
    unittest.main()
