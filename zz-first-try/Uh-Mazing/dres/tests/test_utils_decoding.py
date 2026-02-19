# python -m unittest tests.test_utils_decoding

import unittest
import torch
import numpy as np

from disfluency_removal.utils_decoding import AdaptiveLogitsProcessor

class TestAdaptiveLogitsProcessor(unittest.TestCase):

    def setUp(self):
        self.batch_size = 2
        self.vocab_size = 10
        self.scores = torch.randn((self.batch_size, self.vocab_size), dtype=torch.float)

    def test_invalid_ada_values(self):
        with self.assertRaises(ValueError):
            AdaptiveLogitsProcessor(-0.1)
        with self.assertRaises(ValueError):
            AdaptiveLogitsProcessor(1.5)
        with self.assertRaises(ValueError):
            AdaptiveLogitsProcessor(0.0)  # per design: ada must be > 0

    def test_invalid_min_tokens_to_keep(self):
        with self.assertRaises(ValueError):
            AdaptiveLogitsProcessor(0.1, min_tokens_to_keep=0)
        with self.assertRaises(ValueError):
            AdaptiveLogitsProcessor(0.1, min_tokens_to_keep="abc")

    def test_min_tokens_retained(self):
        processor = AdaptiveLogitsProcessor(ada=0.5, min_tokens_to_keep=3)
        input_ids = torch.randint(0, self.vocab_size, (self.batch_size, 5))
        processed_scores = processor(input_ids, self.scores.clone())
        retained = (processed_scores != processor.filter_value).sum(dim=1)
        self.assertTrue(torch.all(retained >= 3), "Not enough tokens were retained.")

    def test_tokens_filtered_with_high_ada(self):
        processor = AdaptiveLogitsProcessor(ada=0.99)
        input_ids = torch.randint(0, self.vocab_size, (self.batch_size, 5))
        processed_scores = processor(input_ids, self.scores.clone())
        self.assertTrue((processed_scores == processor.filter_value).any(), "No tokens were filtered with high ada.")

    def test_all_tokens_preserved_with_low_ada(self):
        processor = AdaptiveLogitsProcessor(ada=0.0001)
        input_ids = torch.randint(0, self.vocab_size, (self.batch_size, 5))
        processed_scores = processor(input_ids, self.scores.clone())

        # Check that at least vocab_size - X tokens remain unfiltered (e.g., allow 1-2 removals max)
        retained_tokens = (processed_scores != processor.filter_value).sum(dim=1)
        self.assertTrue(torch.all(retained_tokens >= self.vocab_size - 2), "Too many tokens were filtered.")

    def test_output_shape_and_type(self):
        processor = AdaptiveLogitsProcessor(ada=0.1)
        input_ids = torch.randint(0, self.vocab_size, (self.batch_size, 5))
        processed_scores = processor(input_ids, self.scores.clone())
        self.assertEqual(processed_scores.shape, self.scores.shape)
        self.assertIsInstance(processed_scores, torch.FloatTensor)


if __name__ == "__main__":
    unittest.main()
