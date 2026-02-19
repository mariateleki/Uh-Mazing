# python -m disfluency_removal.utils_data_split

import os
from pathlib import Path

from disfluency_removal.utils_dirs import *

def load_texts_from_directory(directory):
    text_list = []
    for filename in os.listdir(directory):
        if filename.endswith(".txt"):
            with open(os.path.join(directory, filename), 'r') as file:
                content = file.read().strip()
                text_list.append((filename, content))
    return text_list

train_data = {
    "disfluent": load_texts_from_directory(TREEBANK_PROCESSED_DIR / 'train' / 'disfluent'),
    "fluent": load_texts_from_directory(TREEBANK_PROCESSED_DIR / 'train' / 'fluent')
    }
valid_data = {
    "disfluent": load_texts_from_directory(TREEBANK_PROCESSED_DIR / 'dev' / 'disfluent'),
    "fluent": load_texts_from_directory(TREEBANK_PROCESSED_DIR / 'dev' / 'fluent')
    }
test_data = {
    "disfluent": load_texts_from_directory(TREEBANK_PROCESSED_DIR / 'test' / 'disfluent'),
    "fluent": load_texts_from_directory(TREEBANK_PROCESSED_DIR / 'test' / 'fluent')
    }
