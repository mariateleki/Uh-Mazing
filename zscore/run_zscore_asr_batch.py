import os
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ZSCORE_SRC = ROOT / "zscore" / "src"
if str(ZSCORE_SRC) not in sys.path:
    sys.path.insert(0, str(ZSCORE_SRC))

from zscore.zscore import evaluate_file  # noqa: E402


ASR_INPUTS = {
    "gemini": ROOT / "asr" / "asr_transcripts_gemini.csv",
    "gpt": ROOT / "asr" / "asr_transcripts_gpt_gpt-4o-transcribe.csv",
}

ZSCORE_CSV_DIR = ROOT / "zscore" / "data" / "csv"
ALIGN_DIR = ZSCORE_CSV_DIR / "align"
SUMMARY_PATH = ZSCORE_CSV_DIR / "eval__asr_batch_summary.csv"
ASR_XML_INPUTS = {
    "whisper": ZSCORE_CSV_DIR / "audio_en_en_standard_whisper_output.xml",
    "canary": ZSCORE_CSV_DIR / "audio_en_en_standard_canary_output.xml",
}
TRANSCRIPT_COLS = {
    "standard": "transcript_standard",
    "disfluent": "transcript_disfluent",
}
WER_SUMMARY_BY_MODEL = {
    "gemini": ROOT / "asr" / "asr_transcripts_gemini_wer_summary.csv",
    "gpt": ROOT / "asr" / "asr_transcripts_gpt_gpt-4o-transcribe_wer_summary.csv",
}


def parse_audio_id(audio_id: str):
    text = str(audio_id).strip().lower().replace(".wav", "")
    text = re.sub(r"^sw0(?=\d{4}_)", "sw", text)  # sw02005 -> sw2005

    m = re.match(r"^sw(\d{4})_([ab])_(\d+)$", text)
    if not m:
        return None

    convo, speaker, turn = m.groups()
    return f"sw{convo}.mrg", speaker.upper(), int(turn)


def build_input_csv(model_name: str, asr_path: Path, variant: str, transcript_col: str) -> tuple[Path, int]:
    df = pd.read_csv(asr_path)

    needed = {"file", transcript_col}
    missing = needed.difference(df.columns)
    if missing:
        raise RuntimeError(f"{asr_path} missing columns: {sorted(missing)}")

    parsed = df["file"].map(parse_audio_id)
    valid = parsed.notna()

    out = pd.DataFrame(parsed[valid].tolist(), columns=["filename", "speaker", "turn"])

    generated = df.loc[valid, transcript_col].fillna("").astype(str).str.strip()
    out["generated-text"] = generated
    dropped_empty = int(out["generated-text"].eq("").sum())
    out = out[out["generated-text"].ne("")]

    out_path = ZSCORE_CSV_DIR / f"asr_{model_name}_{variant}_zscore_input.csv"
    out.to_csv(out_path, index=False)
    return out_path, dropped_empty


def build_input_xml(model_name: str, xml_path: Path, variant: str = "standard") -> tuple[Path, int]:
    root = ET.parse(xml_path).getroot()

    rows = []
    for sample in root.iter("sample"):
        audio_id = sample.attrib.get("id", "")
        parsed = parse_audio_id(audio_id)
        if not parsed:
            continue

        filename, speaker, turn = parsed
        generated_text = "".join(sample.itertext()).strip()
        if not generated_text:
            continue

        rows.append(
            {
                "filename": filename,
                "speaker": speaker,
                "turn": turn,
                "generated-text": generated_text,
            }
        )

    out = pd.DataFrame(rows, columns=["filename", "speaker", "turn", "generated-text"])
    out_path = ZSCORE_CSV_DIR / f"asr_{model_name}_{variant}_zscore_input.csv"
    out.to_csv(out_path, index=False)
    return out_path, 0


def summarize_eval(eval_csv: Path, model_name: str, variant: str, input_csv: Path, dropped_rows: int) -> dict:
    df = pd.read_csv(eval_csv)
    metrics = ["e_p", "e_r", "e_f", "z_e", "z_i", "z_p"]

    row = {
        "model": model_name,
        "variant": variant,
        "input_csv": str(input_csv),
        "eval_csv": str(eval_csv),
        "n_rows": int(len(df)),
        "dropped_empty_rows": dropped_rows,
    }
    for col in metrics:
        row[f"mean_{col}"] = float(df[col].mean()) if col in df.columns else float("nan")

    row.update(load_wer_metrics(model_name, variant))
    return row


def load_wer_metrics(model_name: str, variant: str) -> dict:
    path = WER_SUMMARY_BY_MODEL.get(model_name)
    if not path or not path.exists():
        return {}

    df = pd.read_csv(path)
    df = df[df["hypothesis_tag"].astype(str) == variant]
    if df.empty:
        return {}

    out = {}
    for ref in ("fluent", "disfluent"):
        row = df[df["reference_tag"].astype(str) == ref]
        if row.empty:
            continue

        r = row.iloc[0]
        prefix = f"wer_{ref}"
        out[f"{prefix}_mean"] = float(r.get("mean_wer", float("nan")))
        out[f"{prefix}_total_substitutions"] = float(r.get("total_substitutions", float("nan")))
        out[f"{prefix}_total_deletions"] = float(r.get("total_deletions", float("nan")))
        out[f"{prefix}_total_insertions"] = float(r.get("total_insertions", float("nan")))
        out[f"{prefix}_total_ref_words"] = float(r.get("total_ref_words", float("nan")))
        out[f"{prefix}_corpus_s_rate"] = float(r.get("corpus_s_rate", float("nan")))
        out[f"{prefix}_corpus_d_rate"] = float(r.get("corpus_d_rate", float("nan")))
        out[f"{prefix}_corpus_i_rate"] = float(r.get("corpus_i_rate", float("nan")))

    return out


def main():
    os.chdir(ROOT / "zscore")
    ZSCORE_CSV_DIR.mkdir(parents=True, exist_ok=True)
    ALIGN_DIR.mkdir(parents=True, exist_ok=True)

    summary_rows = []

    for model_name, asr_path in ASR_INPUTS.items():
        if not asr_path.exists():
            print(f"Skipping missing ASR file: {asr_path}")
            continue

        df_head = pd.read_csv(asr_path, nrows=1)
        for variant, transcript_col in TRANSCRIPT_COLS.items():
            if transcript_col not in df_head.columns:
                continue

            input_csv, dropped_rows = build_input_csv(
                model_name, asr_path, variant, transcript_col
            )
            print(f"Prepared zscore input for {model_name}/{variant}: {input_csv}")

            evaluate_file(str(input_csv))
            eval_csv = input_csv.parent / f"eval__{input_csv.name}"
            print(f"Computed zscore for {model_name}/{variant}: {eval_csv}")

            summary_rows.append(
                summarize_eval(eval_csv, model_name, variant, input_csv, dropped_rows)
            )

    for model_name, xml_path in ASR_XML_INPUTS.items():
        if not xml_path.exists():
            print(f"Skipping missing XML file: {xml_path}")
            continue

        variant = "standard"
        input_csv, dropped_rows = build_input_xml(model_name, xml_path, variant=variant)
        print(f"Prepared zscore input for {model_name}/{variant}: {input_csv}")

        evaluate_file(str(input_csv))
        eval_csv = input_csv.parent / f"eval__{input_csv.name}"
        print(f"Computed zscore for {model_name}/{variant}: {eval_csv}")

        summary_rows.append(
            summarize_eval(eval_csv, model_name, variant, input_csv, dropped_rows)
        )

    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        score_cols = [
            c
            for c in summary_df.columns
            if c.startswith("mean_") or c.endswith("_mean") or c.endswith("_rate")
        ]
        summary_df[score_cols] = (summary_df[score_cols] * 100).round(2)
        summary_df.to_csv(SUMMARY_PATH, index=False)
        print(f"Saved batch summary: {SUMMARY_PATH}")
    else:
        print("No model outputs were evaluated.")


if __name__ == "__main__":
    main()
