"""
Append disfluency-node combination columns to train-marked.csv.

New columns:
- edited_nodes_only
- intj_only
- prn_only
- edited_intj
- intj_prn
- edited_prn
- edited_prn_intj

Usage:
    python process_swb/add_disfluency_combo_cols_to_train_marked.py
"""

from pathlib import Path
import sys
import argparse
import pandas as pd
import types


DEFAULT_INPUT_CSV = Path("data/train-marked.csv")
DEFAULT_MRG_ROOT = Path("dres/data/treebank_3/parsed/mrg/swbd")
DEFAULT_OUTPUT_CSV = Path("data/train-marked-with-node-combos.csv")


def _ensure_import_path() -> None:
    root = Path(__file__).resolve().parents[1]
    dres_src = root / "dres" / "src"
    if str(dres_src) not in sys.path:
        sys.path.insert(0, str(dres_src))


_ensure_import_path()
# `utils_process_trees` imports icecream; create a no-op shim if it's unavailable.
if "icecream" not in sys.modules:
    shim = types.ModuleType("icecream")
    shim.ic = lambda *args, **kwargs: args[0] if args else None
    sys.modules["icecream"] = shim
from disfluency_removal.utils_process_trees import (  # noqa: E402
    get_turn_disfluency_node_counts_from_file,
    get_turn_text_excluding_disfluency_labels_from_file,
)


def resolve_mrg_path(file_id: str, mrg_root: Path) -> Path:
    digits = "".join(ch for ch in str(file_id) if ch.isdigit())
    if not digits:
        raise ValueError(f"Could not extract numeric SWB id from file value: {file_id!r}")
    sw_id = f"sw{digits}"
    return mrg_root / sw_id[2] / f"{sw_id}.mrg"


def build_file_turn_count_cache(file_ids, mrg_root: Path):
    cache = {}
    for fid in sorted(set(file_ids)):
        mrg_path = resolve_mrg_path(fid, mrg_root)
        if not mrg_path.exists():
            raise FileNotFoundError(f"Missing .mrg file for {fid}: {mrg_path}")
        cache[fid] = get_turn_disfluency_node_counts_from_file(str(mrg_path))
    return cache


def build_file_turn_text_cache(file_ids, mrg_root: Path):
    disfluency_labels = {"EDITED", "INTJ", "PRN"}
    include_label_sets = {
        "edited_nodes_only": ("EDITED",),
        "intj_only": ("INTJ",),
        "prn_only": ("PRN",),
        "edited_intj": ("EDITED", "INTJ"),
        "intj_prn": ("INTJ", "PRN"),
        "edited_prn": ("EDITED", "PRN"),
        "edited_prn_intj": ("EDITED", "PRN", "INTJ"),
    }
    cache = {}
    for fid in sorted(set(file_ids)):
        mrg_path = resolve_mrg_path(fid, mrg_root)
        if not mrg_path.exists():
            raise FileNotFoundError(f"Missing .mrg file for {fid}: {mrg_path}")
        per_combo = {}
        for col, include_labels in include_label_sets.items():
            excluded = tuple(sorted(disfluency_labels - set(include_labels)))
            per_combo[col] = get_turn_text_excluding_disfluency_labels_from_file(
                str(mrg_path),
                excluded_labels=excluded
            )
        cache[fid] = per_combo
    return cache


def add_combo_columns(df: pd.DataFrame, mrg_root: Path) -> pd.DataFrame:
    required = {"file", "speaker", "turn"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    file_turn_counts = build_file_turn_count_cache(df["file"].astype(str).tolist(), mrg_root)
    file_turn_texts = build_file_turn_text_cache(df["file"].astype(str).tolist(), mrg_root)

    edited_counts = []
    intj_counts = []
    prn_counts = []
    combo_text_cols = {
        "edited_nodes_only": [],
        "intj_only": [],
        "prn_only": [],
        "edited_intj": [],
        "intj_prn": [],
        "edited_prn": [],
        "edited_prn_intj": [],
    }

    for _, row in df.iterrows():
        fid = str(row["file"])
        speaker = str(row["speaker"])
        turn = int(row["turn"])

        counts = file_turn_counts.get(fid, {}).get((speaker, turn), {"EDITED": 0, "INTJ": 0, "PRN": 0})
        e = int(counts["EDITED"])
        i = int(counts["INTJ"])
        p = int(counts["PRN"])

        edited_counts.append(e)
        intj_counts.append(i)
        prn_counts.append(p)

        for col in combo_text_cols:
            combo_text = file_turn_texts.get(fid, {}).get(col, {}).get((speaker, turn), "")
            combo_text_cols[col].append(combo_text)

    out = df.copy()
    out["edited_count"] = edited_counts
    out["intj_count"] = intj_counts
    out["prn_count"] = prn_counts

    for col in [
        "edited_nodes_only",
        "intj_only",
        "prn_only",
        "edited_intj",
        "intj_prn",
        "edited_prn",
        "edited_prn_intj",
    ]:
        out[col] = combo_text_cols[col]

    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT_CSV)
    parser.add_argument("--mrg-root", type=Path, default=DEFAULT_MRG_ROOT)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input_csv)
    out = add_combo_columns(df, args.mrg_root)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output_csv, index=False)
    print(f"Wrote {len(out)} rows to {args.output_csv}")


if __name__ == "__main__":
    main()
