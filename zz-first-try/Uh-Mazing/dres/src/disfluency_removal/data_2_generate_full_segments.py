# python -m disfluency_removal.data_2_generate_full_segments

import os
import re
import json
from pathlib import Path

from disfluency_removal.utils_dirs import *
from disfluency_removal.utils_data_1 import *

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

# Make sentences capitalized correctly
def capitalize_after_sentence_end(text):  
    def replacer(match):
        punct = match.group(1)
        char = match.group(2)
        return f"{punct} {char.upper()}"

    text = re.sub(r'^(\s*)([a-z])', lambda m: m.group(1) + m.group(2).upper(), text)
    text = re.sub(r'([.!?])\s+([a-z])', replacer, text)
    return text

# Correct a common punctuation issue: e.g. ". , the" --> ". The"
def fix_all_exact_dot_comma_lowercase(text):  
    return re.sub(r'\. , ([a-z])', lambda m: f'. {m.group(1).upper()}', text)

def fix_all_exact_dot_comma(text):
    return re.sub(r'\. , ', '. ', text)

def fix_bos_comma_space_lowercase(text):
    return re.sub(r'^, ([a-z])', lambda m: m.group(1).upper(), text)

def fix_comma_space_comma_space(text):
    return re.sub(r', , ', ', ', text)

def fluent_text_post_processing(text):
    text = capitalize_after_sentence_end(text)
    text = fix_all_exact_dot_comma_lowercase(text)
    text = fix_all_exact_dot_comma(text)
    text = fix_bos_comma_space_lowercase(text)
    text = fix_comma_space_comma_space(text)
    return text

def post_process_fluent_text(pairs):
    return [
        (fname, fluent_text_post_processing(text))
        for fname, text in pairs
    ]

def post_process_fluent_segments(triplets):
    return [
        (fname, dis_text, fluent_text_post_processing(fl_text))
        for fname, dis_text, fl_text in triplets
    ]

# Save all
save_full_split("train", 
                {"disfluent": remove_sep_tokens(train_data["disfluent"]), 
                 "fluent": post_process_fluent_text(remove_sep_tokens(train_data["fluent"]))
                }
               )
save_full_split("valid", 
                {"disfluent": remove_sep_tokens(valid_data["disfluent"]), 
                 "fluent": post_process_fluent_text(remove_sep_tokens(valid_data["fluent"]))
                }
               )
save_full_split("test", 
                {"disfluent": remove_sep_tokens(test_data["disfluent"]), 
                 "fluent": post_process_fluent_text(remove_sep_tokens(test_data["fluent"]))
                }
               )

train_segments = segment_pairs(train_data["disfluent"], train_data["fluent"])
valid_segments = segment_pairs(valid_data["disfluent"], valid_data["fluent"])
test_segments = segment_pairs(test_data["disfluent"], test_data["fluent"])

save_segment_split("train", post_process_fluent_segments(train_segments))
save_segment_split("valid", post_process_fluent_segments(valid_segments))
save_segment_split("test", post_process_fluent_segments(test_segments))

