"""
Map rows in train-marked.csv to their corresponding Switchboard .mrg file.

Usage:
    python process_swb/map_train_marked_to_mrg.py
"""

from pathlib import Path
import argparse
import pandas as pd


DEFAULT_INPUT_CSV = Path("data/train-marked.csv")
DEFAULT_MRG_ROOT = Path("dres/data/treebank_3/parsed/mrg/swbd")
DEFAULT_OUTPUT_CSV = Path("data/train-marked-with-mrg.csv")


def normalize_file_id(file_id: str) -> str:
    digits = "".join(ch for ch in str(file_id) if ch.isdigit())
    if not digits:
        raise ValueError(f"Could not extract numeric SWB id from file value: {file_id!r}")
    return f"sw{digits}"


def resolve_mrg_path(file_id: str, mrg_root: Path) -> Path:
    sw_id = normalize_file_id(file_id)
    shard = sw_id[2]
    return mrg_root / shard / f"{sw_id}.mrg"


def build_mapping(input_csv: Path, mrg_root: Path) -> pd.DataFrame:
    df = pd.read_csv(input_csv)
    if "file" not in df.columns:
        raise ValueError(f"Expected a 'file' column in {input_csv}")

    mrg_paths = []
    exists = []
    missing_files = set()

    for file_id in df["file"].astype(str):
        mrg_path = resolve_mrg_path(file_id, mrg_root)
        path_exists = mrg_path.exists()
        mrg_paths.append(str(mrg_path))
        exists.append(path_exists)
        if not path_exists:
            missing_files.add(file_id)

    out = df.copy()
    out["mrg_path"] = mrg_paths
    out["mrg_exists"] = exists

    if missing_files:
        preview = ", ".join(sorted(missing_files)[:10])
        raise FileNotFoundError(
            f"Missing .mrg file for {len(missing_files)} conversation ids. "
            f"Examples: {preview}"
        )

    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT_CSV)
    parser.add_argument("--mrg-root", type=Path, default=DEFAULT_MRG_ROOT)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mapped = build_mapping(args.input_csv, args.mrg_root)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    mapped.to_csv(args.output_csv, index=False)
    print(f"Wrote {len(mapped)} rows to {args.output_csv}")


if __name__ == "__main__":
    main()
