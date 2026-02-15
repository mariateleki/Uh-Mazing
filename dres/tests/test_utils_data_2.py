# test_utils_data_2.py

import unittest
import tempfile
import shutil
from pathlib import Path
from disfluency_removal.utils_data_2 import *

class TestUtilsData2(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory structure for tests
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Clean up after each test
        shutil.rmtree(self.test_dir)

    def _create_file(self, directory, filename, content):
        path = Path(directory) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_full_splits(self):
        for split in ['data/full/train', 'data/full/valid', 'data/full/test']:
            with self.subTest(split=split):
                data = load_full_data(split)
                self.assertIn("disfluent", data)
                self.assertIn("fluent", data)
                self.assertEqual(len(data["disfluent"]), len(data["fluent"]))
                for (df_name, _), (fl_name, _) in zip(data["disfluent"], data["fluent"]):
                    self.assertEqual(df_name, fl_name)

    def test_segment_splits(self):
        for split in ['data/segments/train', 'data/segments/valid', 'data/segments/test']:
            with self.subTest(split=split):
                data = load_segment_data(split)
                self.assertTrue(len(data) > 0)
                for seg in data:
                    self.assertEqual(len(seg), 3)
                    self.assertIsInstance(seg[0], str)
                    self.assertIsInstance(seg[1], str)
                    self.assertIsInstance(seg[2], str)

    def test_empty_directory(self):
        empty_path = Path(self.test_dir) / "empty"
        empty_path.mkdir(parents=True)
        (empty_path / "disfluent").mkdir()
        (empty_path / "fluent").mkdir()
        data = load_full_data(empty_path)
        self.assertEqual(data["disfluent"], [])
        self.assertEqual(data["fluent"], [])

    def test_mismatched_segment_filenames(self):
        path = Path(self.test_dir) / "segment_mismatch"
        dis_path = path / "disfluent"
        fl_path = path / "fluent"
        self._create_file(dis_path, "a.txt", "uh I think")
        self._create_file(fl_path, "b.txt", "I think")

        with self.assertRaises(AssertionError):
            load_segment_data(path)

    def test_partial_segment_pair(self):
        path = Path(self.test_dir) / "partial_segment"
        dis_path = path / "disfluent"
        fl_path = path / "fluent"
        self._create_file(dis_path, "only_dis.txt", "uh I mean")
        (fl_path).mkdir(parents=True)

        # Should return no pairs because one side is missing
        data = load_segment_data(path)
        self.assertEqual(data, [])

if __name__ == "__main__":
    unittest.main()
