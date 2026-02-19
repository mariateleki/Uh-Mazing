# python -m disfluency_removal.utils_data_split
# We follow split in section 4: https://aclanthology.org/2020.acl-main.346.pdf

import os
import datetime
import re
import json
from pathlib import Path

from disfluency_removal.utils_dirs import *

# set up timestamp
timestamp = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

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

def split_by_sep(text):
    """Split at all <SEPn> markers, preserving empty segments for alignment and removing extra spaces."""
    normalized = re.sub(r"(<SEP\d+>)(?=<SEP\d+>)", r"\1 ", text)
    segments = re.split(r"<SEP\d+>", normalized)
    return [re.sub(r"\s{2,}", " ", seg).strip() for seg in segments]

def remove_sep_tokens(pairs):
    return [
        (fname, re.sub(r"\s{2,}", " ", re.sub(r"<SEP\d+>", "", text)).strip())
        for fname, text in pairs
    ]

def segment_pairs(disfluent_list, fluent_list):
    segmented = []
    for (df_name, df_text), (fl_name, fl_text) in zip(disfluent_list, fluent_list):
        if df_name != fl_name:
            continue
        df_segs = split_by_sep(df_text)
        fl_segs = split_by_sep(fl_text)
        if len(df_segs) != len(fl_segs):
            continue
        for i, (df_seg, fl_seg) in enumerate(zip(df_segs, fl_segs)):
            seg_name = f"{df_name}::seg{i}"
            segmented.append((seg_name, df_seg.strip(), fl_seg.strip()))
    return segmented

def save_full_split(split_name, data_dict, out_root="data/full"):
    for side in ["disfluent", "fluent"]:
        out_dir = Path(out_root) / split_name / side
        out_dir.mkdir(parents=True, exist_ok=True)
        for fname, text in data_dict[side]:
            file_path = out_dir / fname
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text.strip() + "\n")

def save_segment_split(split_name, segment_data, out_root="data/segments"):
    dis_dir = Path(out_root) / split_name / "disfluent"
    fl_dir = Path(out_root) / split_name / "fluent"
    dis_dir.mkdir(parents=True, exist_ok=True)
    fl_dir.mkdir(parents=True, exist_ok=True)

    for seg_name, dis_text, fl_text in segment_data:
        base_name, seg_id = seg_name.split("::seg")
        fname = f"{base_name}-seg{seg_id}.txt"
        with open(dis_dir / fname, "w", encoding="utf-8") as f:
            f.write(dis_text.strip() + "\n")
        with open(fl_dir / fname, "w", encoding="utf-8") as f:
            f.write(fl_text.strip() + "\n")

# Generate full versions
full_train = {
    "disfluent": remove_sep_tokens(train_data["disfluent"]),
    "fluent": remove_sep_tokens(train_data["fluent"]),
}
full_dev = {
    "disfluent": remove_sep_tokens(valid_data["disfluent"]),
    "fluent": remove_sep_tokens(valid_data["fluent"]),
}
full_test = {
    "disfluent": remove_sep_tokens(test_data["disfluent"]),
    "fluent": remove_sep_tokens(test_data["fluent"]),
}

# Generate segment versions
segment_train = segment_pairs(train_data["disfluent"], train_data["fluent"])
segment_dev = segment_pairs(valid_data["disfluent"], valid_data["fluent"])
segment_test = segment_pairs(test_data["disfluent"], test_data["fluent"])

# Save all
save_full_split("train", full_train)
save_full_split("valid", full_dev)
save_full_split("test", full_test)

save_segment_split("train", segment_train)
save_segment_split("valid", segment_dev)
save_segment_split("test", segment_test)
