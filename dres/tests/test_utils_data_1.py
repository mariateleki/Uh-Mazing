# python -m unittest tests.test_utils_data_1

import unittest
import re
from disfluency_removal.utils_data_1 import *

class TestUtilsDataSplit(unittest.TestCase):
    def check_split_filenames(self, items, pattern, split_name):
        regex = re.compile(pattern)
        for fname, _ in items:
            self.assertRegex(fname, regex, f"{fname} incorrectly included in {split_name}")

    def test_train_filenames(self):
        self.check_split_filenames(train_data["disfluent"], r"^sw[23]\d+\.txt$", "train")

    def test_dev_filenames(self):
        self.check_split_filenames(valid_data["disfluent"], r"^sw4[5-9]\d+\.txt$", "dev")

    def test_test_filenames(self):
        self.check_split_filenames(test_data["disfluent"], r"^sw4[0-1]\d+\.txt$", "test")

    def test_no_duplicates_across_splits(self):
        def get_filenames(split_data):
            return set(fname for fname, _ in split_data)

        train_files = get_filenames(train_data["disfluent"])
        dev_files = get_filenames(valid_data["disfluent"])
        test_files = get_filenames(test_data["disfluent"])

        overlaps = {
            "train ∩ dev": train_files & dev_files,
            "train ∩ test": train_files & test_files,
            "dev ∩ test": dev_files & test_files,
        }

        for label, overlap in overlaps.items():
            self.assertEqual(len(overlap), 0, f"Overlap found in {label}: {sorted(overlap)}")
