"""
Append disfluency-node combo text columns to uh-mazing.csv.

This keeps all non-excluded node content per combo:
- edited_nodes_only: excludes INTJ + PRN
- intj_only: excludes EDITED + PRN
- prn_only: excludes EDITED + INTJ
- edited_intj: excludes PRN
- intj_prn: excludes EDITED
- edited_prn: excludes INTJ
- edited_prn_intj: excludes nothing

Usage:
    python process_swb/add_node_combos_to_uh_mazing.py
"""

from pathlib import Path
import argparse
import sys
import types
import re
import pandas as pd


DEFAULT_INPUT_CSV = Path("data/uh-mazing.csv")
DEFAULT_MRG_ROOT = Path("dres/data/treebank_3/parsed/mrg/swbd")
DEFAULT_OUTPUT_CSV = Path("data/uh-mazing-with-node-combos.csv")


def _ensure_import_path() -> None:
    root = Path(__file__).resolve().parents[1]
    dres_src = root / "dres" / "src"
    if str(dres_src) not in sys.path:
        sys.path.insert(0, str(dres_src))


_ensure_import_path()
if "icecream" not in sys.modules:
    shim = types.ModuleType("icecream")
    shim.ic = lambda *args, **kwargs: args[0] if args else None
    sys.modules["icecream"] = shim

from disfluency_removal.utils_process_trees import (  # noqa: E402
    get_turn_disfluency_node_counts_from_file,
    get_turn_text_excluding_disfluency_labels_from_file,
)


def parse_uhm_id(row_id: str):
    m = re.match(r"^(sw\d+)_([A-Z])_(\d+)$", str(row_id))
    if not m:
        raise ValueError(f"Unexpected ID format: {row_id!r}")
    file_id, speaker, turn = m.groups()
    return file_id, speaker, int(turn)


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
    if "ID" not in df.columns:
        raise ValueError("Expected column 'ID' in uh-mazing CSV")

    parsed = [parse_uhm_id(v) for v in df["ID"].astype(str)]
    file_ids = [p[0] for p in parsed]

    file_turn_counts = build_file_turn_count_cache(file_ids, mrg_root)
    file_turn_texts = build_file_turn_text_cache(file_ids, mrg_root)

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

    for file_id, speaker, turn in parsed:
        counts = file_turn_counts.get(file_id, {}).get(
            (speaker, turn),
            {"EDITED": 0, "INTJ": 0, "PRN": 0}
        )

        edited_counts.append(int(counts["EDITED"]))
        intj_counts.append(int(counts["INTJ"]))
        prn_counts.append(int(counts["PRN"]))

        for col in combo_text_cols:
            text = file_turn_texts.get(file_id, {}).get(col, {}).get((speaker, turn), "")
            combo_text_cols[col].append(text)

    out = df.copy()
    out["edited_count"] = edited_counts
    out["intj_count"] = intj_counts
    out["prn_count"] = prn_counts

    for col in combo_text_cols:
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
