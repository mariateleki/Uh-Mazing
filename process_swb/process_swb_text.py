# python process_swb/process_swb_text.py

import os
import re
import csv

# --------------------------------------------------
# Config
# --------------------------------------------------

SPEAKER_RE = re.compile(r'<Speaker([A-Z])(\d+)>\s*[.,]?\s*')

FIELDNAMES = [
    "file",
    "speaker",
    "turn",
    "text_fluent",
    "text_disfluent",
    "keep"
]

# --------------------------------------------------
# Speaker segmentation
# --------------------------------------------------

def segment_by_speaker(text):
    """
    Split text into [(speaker, turn, text), ...]
    Works even if multiple speakers occur on one line.
    """
    segments = []
    matches = list(SPEAKER_RE.finditer(text))

    for i, m in enumerate(matches):
        speaker, turn = m.groups()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        segment_text = text[start:end].strip()
        segments.append((speaker, int(turn), segment_text))

    return segments

# --------------------------------------------------
# File-level parsing (FIXED)
# --------------------------------------------------

def parse_parallel_files(fluent_path, disfluent_path, file_id):
    rows = []

    with open(fluent_path, "r", encoding="utf8") as f:
        fluent_text = f.read()

    with open(disfluent_path, "r", encoding="utf8") as f:
        disfluent_text = f.read()

    fluent_segments = segment_by_speaker(fluent_text)
    disfluent_segments = segment_by_speaker(disfluent_text)

    # Index fluent by (speaker, turn)
    fluent_map = {
        (speaker, turn): text
        for speaker, turn, text in fluent_segments
        if text.strip()
    }

    # Disfluent is the ground truth timeline
    for speaker, turn, disfluent_text in disfluent_segments:
        fluent_text = fluent_map.get((speaker, turn), "")

        rows.append({
            "file": file_id,
            "speaker": speaker,
            "turn": turn,
            "text_fluent": fluent_text,
            "text_disfluent": disfluent_text,
            "keep": False
        })

    return rows

# --------------------------------------------------
# Dataset-level CSV builder
# --------------------------------------------------

def build_csv(split_dir, out_csv):
    fluent_dir = os.path.join(split_dir, "fluent")
    disfluent_dir = os.path.join(split_dir, "disfluent")

    if not os.path.isdir(fluent_dir):
        raise FileNotFoundError(f"Missing fluent dir: {fluent_dir}")
    if not os.path.isdir(disfluent_dir):
        raise FileNotFoundError(f"Missing disfluent dir: {disfluent_dir}")

    all_rows = []

    for fname in sorted(os.listdir(fluent_dir)):
        if not fname.endswith(".txt"):
            continue

        file_id = fname.replace(".txt", "")
        fluent_path = os.path.join(fluent_dir, fname)
        disfluent_path = os.path.join(disfluent_dir, fname)

        if not os.path.exists(disfluent_path):
            raise FileNotFoundError(f"Missing disfluent file: {disfluent_path}")

        rows = parse_parallel_files(
            fluent_path,
            disfluent_path,
            file_id
        )
        all_rows.extend(rows)

    with open(out_csv, "w", newline="", encoding="utf8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Wrote {len(all_rows)} rows → {out_csv}")

# --------------------------------------------------
# Entry point
# --------------------------------------------------

if __name__ == "__main__":
    SPLIT_DIR = "dres/data/treebank_3_flat/train"
    OUTPUT_CSV = "data/train.csv"

    build_csv(SPLIT_DIR, OUTPUT_CSV)
