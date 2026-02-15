# python -m zscore.zscore
import re
import os
import pandas as pd
from pathlib import Path
import fnmatch
try:
    from icecream import ic
except ImportError:  # optional debug dependency
    def ic(*args, **kwargs):
        return args[0] if args else None

from zscore.utils_evaluate import *
from zscore import tb
from zscore.utils_process_trees import extract_tokens, get_tree_file_path

def extract_speaker(tree):
    """
    Returns 'SpeakerX' if this is a CODE tree, else None.
    """
    if not tree or len(tree) < 2:
        return None

    node = tree[1]

    if node[0] != "CODE":
        return None

    # node = ['CODE', ['SYM', 'SpeakerA1'], ['.', '.']]
    for child in node[1:]:
        if child[0] == "SYM":
            return child[1]

    return None


def evaluate_file(file_path):
    df = pd.read_csv(file_path) # sw2012_A_99, 

    metrics = {"e_p": [], "e_r": [], "e_f": [], "z_e": [], "z_i": [], "z_p": []}

    for _, row in df.iterrows():
        try:
            generated_text = str(row["generated-text"])
            file_id = row["filename"]  # e.g., 'sw2005.mrg'
            speaker_id = row["speaker"]
            turn_id = row["turn"]
            tree_file = get_tree_file_path(file_id)
            trees = tb.read_file(tree_file) # Parse trees and extract tokens and tags

            target_speaker = f"Speaker{speaker_id}{turn_id}"
            current_speaker = None
            speaker_trees = []
            for tree in trees:
                speaker = extract_speaker(tree)

                if speaker is not None:
                    current_speaker = speaker
                    continue  # never collect CODE trees themselves

                if current_speaker == target_speaker:
                    speaker_trees.append(tree)


            disfluent_tokens = []
            disfluent_tags = []

            for tree in speaker_trees:
                _, _, token_tag_pairs = extract_tokens(tree, return_tags=True)
                if token_tag_pairs:
                    tokens, tags = zip(*token_tag_pairs)
                    disfluent_tokens.extend(tokens)
                    disfluent_tags.extend(tags)

            # Run alignment and metric computation
            alignment = align(disfluent_tokens, disfluent_tags, generated_text)
            align_path = os.path.join(os.path.dirname(file_path), "align", f"align__{file_id.replace('.mrg','')}_{speaker_id}_{turn_id}__" + os.path.basename(file_path))
            alignment.to_csv(align_path, index=False)
            print(f"Saved alignment to to {align_path}")

            print(alignment)

            e_p, e_r, e_f = e_prf(alignment)
            z_e, z_i, z_p = z_eip(alignment)

        except Exception as e:
            print(f"Error processing row ({row.get('filename', 'unknown')}): {e}")
            e_p, e_r, e_f, z_e, z_i, z_p = [float("nan")] * 6

        metrics["e_p"].append(e_p)
        metrics["e_r"].append(e_r)
        metrics["e_f"].append(e_f)
        metrics["z_e"].append(z_e)
        metrics["z_i"].append(z_i)
        metrics["z_p"].append(z_p)

    for k, v in metrics.items():
        df[k] = v

    eval_path = os.path.join(os.path.dirname(file_path), "eval__" + os.path.basename(file_path))
    df.to_csv(eval_path, index=False)
    print(f"Saved evaluation to {eval_path}")
