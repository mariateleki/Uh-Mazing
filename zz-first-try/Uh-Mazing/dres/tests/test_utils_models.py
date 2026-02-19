# python -m unittest tests.test_utils_models
import unittest
import torch
import os

import transformers
from transformers import AutoTokenizer
from disfluency_removal.utils_models import *

class TestUtilsModels(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.model_id = "meta-llama/Llama-3.2-3B-Instruct"
        print("\n[SETUP] Loading tokenizer and model...")
        cls.tokenizer, cls.model = load_llama_model(cls.model_id)
        cls.tokenizer.pad_token = cls.tokenizer.eos_token
        cls.device = cls.model.device

    def test_set_all_seeds(self):
        try:
            set_all_seeds(123)
        except Exception as e:
            self.fail(f"set_all_seeds raised an exception: {e}")

    def test_apply_chat_template_does_not_truncate(self):
        long_input = "Hello world. " * 400
        input_struct = [{"role": "user", "content": long_input}]
        input_ids = self.tokenizer.apply_chat_template(
            input_struct, add_generation_prompt=True, return_tensors="pt"
        )
        decoded = self.tokenizer.decode(input_ids[0])
        self.assertIn("Hello world", decoded)
        self.assertGreater(len(input_ids[0]), 1000)

    def test_output_extraction_from_llama_format(self):
        raw_output = (
            "<|start_header_id|>user<|end_header_id|>\n\nDisfluent: I, um, went to the, uh, store.<|eot_id|>"
            "<|start_header_id|>assistant<|end_header_id|>\n\nSure, here's the fluent version: I went to the store.<|eot_id|>"
        )

        # Use same regex as in run_llama_model
        pattern = r"<\|start_header_id\|>assistant<\|end_header_id\|>\n\n(.*?)<\|eot_id\|>"
        match = re.search(pattern, raw_output, re.DOTALL)
        assistant_response = match.group(1).strip() if match else ""

        self.assertIn("I went to the store", assistant_response)
        self.assertNotIn("<|eot_id|>", assistant_response)


if __name__ == "__main__":
    unittest.main()
