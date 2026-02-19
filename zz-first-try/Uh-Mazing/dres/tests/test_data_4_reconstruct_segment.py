# python -m unittest tests/test_data_4_reconstruct_segment.py

import unittest
import pandas as pd
from pathlib import Path
from disfluency_removal.utils_dirs import RESULTS_DIR


def find_latest_file(path: Path, prefix: str):
    """Find the latest CSV file in a directory matching a given prefix."""
    files = list(path.glob(f"{prefix}*.csv"))
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


def compare_segment_and_full_files(segment_dir, full_dir):
    segment_dir = Path(segment_dir)
    full_dir = Path(full_dir)

    matched = []
    unmatched = []

    for seg_file in segment_dir.rglob("merged__*.csv"):
        seg_folder = seg_file.parent
        rel_path = seg_folder.relative_to(segment_dir)

        full_folder = full_dir / rel_path
        seg_latest = find_latest_file(seg_folder, "merged__")
        full_latest = find_latest_file(full_folder, "results__")

        if not full_latest:
            unmatched.append(seg_latest)
            continue

        seg_df = pd.read_csv(seg_latest)
        full_df = pd.read_csv(full_latest)

        if len(seg_df) != len(full_df):
            raise ValueError(f"Row count mismatch:\n - {seg_latest}\n - {full_latest}")

        for col in ["filename", "disfluent-text", "fluent-text"]:
            if not seg_df[col].equals(full_df[col]):
                diff_mask = ~(seg_df[col] == full_df[col])
                diff_rows = pd.DataFrame({
                    "segment": seg_df.loc[diff_mask, col].reset_index(drop=True),
                    "full": full_df.loc[diff_mask, col].reset_index(drop=True)
                })

                raise AssertionError(
                    f"\n❌ Mismatch in column '{col}' between:\n"
                    f" - Segment: {seg_latest}\n"
                    f" - Full:    {full_latest}\n"
                    f"🔍 Differences (showing up to 5 rows):\n"
                    f"{diff_rows.head(5).to_string(index=False)}"
                )

        matched.append((seg_latest.name, full_latest.name))

    return matched, unmatched


if __name__ == "__main__":
    unittest.main()
