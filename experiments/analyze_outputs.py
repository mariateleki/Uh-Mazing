"""Analyze node-combo translation outputs for blanks, short, and weird translations."""

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import glob
import pandas as pd

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
MODEL_TAGS = ["gemini-2.5-flash", "gpt52"]
LANGUAGES = ["ZH", "ES", "HI", "FR", "DE", "IT", "CZ", "AR"]

# A translation 5x longer than its source is suspicious (likely extra explanation or repeated output)
# A translation under 5 chars is suspicious (likely failed)
SOURCE_RATIO_THRESHOLD = 5.0
SHORT_THRESHOLD = 5


def get_translation_cols(df):
    return [c for c in df.columns if any(f"{lang}_{tag}" == c for lang in LANGUAGES for tag in MODEL_TAGS)]


def guess_source_col(fname):
    """Figure out which column was the source text based on the filename."""
    # filename pattern: node-combos_{model}_{standard|disfluent}_{combo_col}.csv
    parts = fname.replace(".csv", "").split("_")
    # skip "node-combos", model tag, and "standard"/"disfluent" to get combo col
    for tag in MODEL_TAGS:
        tag_parts = tag.split("-")
        # find where model tag ends
        for i in range(len(parts)):
            candidate = "-".join(parts[i:i+len(tag_parts)])
            if candidate == tag:
                # next part is standard/disfluent, rest is combo col
                remainder = parts[i+len(tag_parts):]
                if len(remainder) >= 2:
                    return "_".join(remainder[1:])  # skip standard/disfluent
    return None


def check_file(path):
    fname = os.path.basename(path)
    df = pd.read_csv(path)
    cols = get_translation_cols(df)
    if not cols:
        return None

    source_col = guess_source_col(fname)
    has_source = source_col and source_col in df.columns
    total = len(df)

    blanks = []
    shorts = []
    ratio_flags = []

    for col in cols:
        for idx, val in df[col].items():
            is_blank = pd.isna(val) or str(val).strip() == ""
            if is_blank:
                blanks.append((idx, col))
                continue

            text = str(val).strip()
            if len(text) < SHORT_THRESHOLD:
                shorts.append((idx, col, text))
                continue

            # check length ratio vs source
            if has_source:
                src = str(df.at[idx, source_col]).strip()
                if len(src) > 0:
                    ratio = len(text) / len(src)
                    if ratio > SOURCE_RATIO_THRESHOLD:
                        ratio_flags.append((idx, col, f"{ratio:.1f}x source", text[:100]))

    has_issues = blanks or shorts or ratio_flags
    tag = "!!" if has_issues else "OK"
    print(f"  [{tag}] {fname}  ({total} rows, {len(cols)} langs)", end="")
    if has_source:
        print(f"  [source: {source_col}]")
    else:
        print()

    if blanks:
        # group by language
        by_lang = {}
        for idx, col in blanks:
            by_lang.setdefault(col, []).append(idx)
        print(f"       BLANK ({len(blanks)} cells):")
        for col, rows in by_lang.items():
            print(f"         {col}: rows {rows}")

    if shorts:
        print(f"       SHORT ({len(shorts)} cells, <{SHORT_THRESHOLD} chars):")
        for idx, col, text in shorts:
            print(f"         row {idx}, {col}: \"{text}\"")

    if ratio_flags:
        print(f"       RATIO ({len(ratio_flags)} cells, >{SOURCE_RATIO_THRESHOLD}x source length):")
        for idx, col, ratio, preview in ratio_flags:
            print(f"         row {idx}, {col}: {ratio}")
            print(f"           \"{preview}\"")

    return has_issues


def main():
    files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "node-combos_*.csv")))
    if not files:
        print(f"No node-combos files found in {OUTPUT_DIR}")
        sys.exit(1)

    print(f"Scanning {len(files)} node-combo files in {OUTPUT_DIR}")
    print(f"Checks: blank cells, short (<{SHORT_THRESHOLD} chars), length ratio (>{SOURCE_RATIO_THRESHOLD}x source)")
    print()

    clean = 0
    problems = 0
    for f in files:
        has_issues = check_file(f)
        if has_issues is None:
            continue
        if has_issues:
            problems += 1
        else:
            clean += 1

    print(f"\n{'=' * 60}")
    print(f"RESULT: {clean} clean, {problems} with issues, {len(files)} total")
    if clean == len(files):
        print("All node-combo translations look good!")


if __name__ == "__main__":
    main()
