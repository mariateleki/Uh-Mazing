# tests/test_utils_prompts.py

import unittest
import os
from pathlib import Path
from disfluency_removal.utils_prompts import (
    load_kshot_examples,
    format_kshot_examples,
    get_prompt,
    EXAMPLES_PREFIX,
    PREFIX,
)

KSHOT_DIR = Path("data/k_shot")


class TestUtilsPromptsWithFiles(unittest.TestCase):
    def test_load_kshot_examples_full(self):
        examples = load_kshot_examples(k=1, use_segment=False)
        self.assertGreater(len(examples), 0)
        self.assertIn("disfluent", examples[0])
        self.assertIn("fluent", examples[0])

    def test_load_kshot_examples_segment(self):
        examples = load_kshot_examples(k=1, use_segment=True)
        self.assertGreater(len(examples), 0)
        self.assertIn("disfluent", examples[0])
        self.assertIn("fluent", examples[0])

    def test_format_kshot_examples(self):
        examples = load_kshot_examples(k=1, use_segment=False)
        formatted = format_kshot_examples(examples)
        self.assertIn("Disfluent:", formatted)
        self.assertIn("Fluent:", formatted)

    def test_get_prompt_with_k_full(self):
        input_text = "Um, okay I think we can go."
        prompt = get_prompt(input_text=input_text, k=1, use_segment=False)
        self.assertIn(EXAMPLES_PREFIX, prompt)
        self.assertIn(PREFIX, prompt)
        self.assertIn(input_text, prompt)

    def test_get_prompt_with_k_segment(self):
        input_text = "Uh, maybe we could leave soon."
        prompt = get_prompt(input_text=input_text, k=1, use_segment=True)
        self.assertIn(EXAMPLES_PREFIX, prompt)
        self.assertIn(PREFIX, prompt)
        self.assertIn(input_text, prompt)

    def test_get_prompt_without_k(self):
        input_text = "Like, I’m not sure."
        prompt = get_prompt(input_text=input_text, k=0, use_segment=True)
        self.assertNotIn(EXAMPLES_PREFIX, prompt)
        self.assertIn(PREFIX, prompt)
        self.assertIn(input_text, prompt)


if __name__ == "__main__":
    unittest.main()
