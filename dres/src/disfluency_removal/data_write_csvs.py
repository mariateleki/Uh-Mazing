# python -m disfluency_removal.data_write_csvs

import pandas as pd
from pathlib import Path

def save_pairs_to_csv(disfluent_dir: Path, fluent_dir: Path, output_csv: Path):
    if not disfluent_dir.exists() or not fluent_dir.exists():
        print(f"⚠️ Skipping: {disfluent_dir.parent} (missing folders)")
        return

    rows = []
    for disfl_file in sorted(disfluent_dir.glob("*.txt")):
        filename = disfl_file.name
        fluent_file = fluent_dir / filename
        if not fluent_file.exists():
            print(f"⚠️ Missing fluent file for: {filename}")
            continue

        with disfl_file.open("r", encoding="utf-8") as f1, fluent_file.open("r", encoding="utf-8") as f2:
            disfluent_text = f1.read().strip()
            fluent_text = f2.read().strip()
            rows.append({
                "filename": filename,
                "disfluent": disfluent_text,
                "fluent": fluent_text
            })

    df = pd.DataFrame(rows)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)
    print(f"✅ Saved {len(df)} rows to {output_csv}")


def process_all_pairs():
    base = Path("data")
    styles = ["full", "segments"]
    splits = ["train", "valid", "test"]

    for style in styles:
        for split in splits:
            split_path = base / style / split
            disfluent_dir = split_path / "disfluent"
            fluent_dir = split_path / "fluent"
            output_csv = base / "treebank_3_csv" / f"{style}_{split}_pairs.csv"

            save_pairs_to_csv(disfluent_dir, fluent_dir, output_csv)


if __name__ == "__main__":
    process_all_pairs()
