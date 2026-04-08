"""Check row counts across all node-combo output files and compare to input data."""

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import glob
import pandas as pd

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
INPUT_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "train-marked-with-node-combos.csv")


def main():
    # load input and apply same filter as run_translate.py
    df_input = pd.read_csv(INPUT_CSV)
    if "keep" in df_input.columns:
        df_input = df_input[df_input["keep"] == True].reset_index(drop=True)
    expected_rows = len(df_input)
    print(f"Input: {INPUT_CSV}")
    print(f"Expected rows (after keep=True filter): {expected_rows}")
    print()

    files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "node-combos_*.csv")))
    if not files:
        print("No node-combos files found.")
        sys.exit(1)

    mismatches = []
    for f in files:
        df = pd.read_csv(f)
        fname = os.path.basename(f)
        actual = len(df)
        status = "OK" if actual == expected_rows else f"MISMATCH (got {actual})"
        print(f"  [{status}] {fname}")
        if actual != expected_rows:
            mismatches.append((fname, df, actual))

    if not mismatches:
        print(f"\nAll {len(files)} files have {expected_rows} rows. No issues.")
        return

    # dig into each mismatch
    print(f"\n{'=' * 60}")
    print(f"INVESTIGATING {len(mismatches)} MISMATCHED FILES")
    print(f"{'=' * 60}")

    # use a key column to identify rows — try 'file', 'speaker', 'turn' combo
    key_cols = ["file", "speaker", "turn"]
    if all(c in df_input.columns for c in key_cols):
        input_keys = set(df_input[key_cols].apply(lambda r: f"{r['file']}_{r['speaker']}_{r['turn']}", axis=1))
    else:
        input_keys = None

    for fname, df, actual in mismatches:
        diff = expected_rows - actual
        print(f"\n  {fname}: {actual} rows ({diff} {'missing' if diff > 0 else 'extra'})")

        if input_keys and all(c in df.columns for c in key_cols):
            output_keys = set(df[key_cols].apply(lambda r: f"{r['file']}_{r['speaker']}_{r['turn']}", axis=1))
            missing = input_keys - output_keys
            extra = output_keys - input_keys

            if missing:
                print(f"\n    MISSING ROWS ({len(missing)}):")
                # find the actual input rows that are missing
                for key in sorted(missing):
                    parts = key.rsplit("_", 2)
                    if len(parts) == 3:
                        match = df_input[
                            (df_input["file"] == parts[0]) &
                            (df_input["speaker"] == parts[1]) &
                            (df_input["turn"] == int(parts[2]))
                        ]
                        for _, row in match.iterrows():
                            src_preview = str(row.get("text_disfluent", ""))[:80]
                            print(f"      {key}: \"{src_preview}\"")
                    else:
                        print(f"      {key}")

            if extra:
                print(f"\n    EXTRA ROWS ({len(extra)}):")
                for key in sorted(extra):
                    print(f"      {key}")
        else:
            print("    (Cannot identify specific rows — key columns not found)")


if __name__ == "__main__":
    main()
