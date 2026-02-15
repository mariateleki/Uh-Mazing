# python calcuate_wer.py
import re
import string

import pandas as pd
from jiwer import process_words

# ======================= CONFIG =======================

ASR_CSV = "./asr_transcripts_gpt_gpt-4o-transcribe.csv"
GT_CSV = "../data/uh-mazing.csv"
GT_NAME_COL = "ID"
GT_REF_COLS = {
    "fluent": "EN_fluent",
    "disfluent": "EN_disfluent",
}

FILE_COL = "file"

HYP_COLS = {
    "standard": "transcript_standard",
    "disfluent": "transcript_disfluent",
}
REMOVE_PUNCTUATION = True

# =====================================================


def load_gt_csv(csv_path: str) -> pd.DataFrame:
    df_gt_raw = pd.read_csv(csv_path)

    required_cols = {GT_NAME_COL, *GT_REF_COLS.values()}
    missing = required_cols.difference(df_gt_raw.columns)
    if missing:
        raise RuntimeError(
            f"Missing required columns in GT CSV: {sorted(missing)}"
        )

    df_gt = df_gt_raw[[GT_NAME_COL, *GT_REF_COLS.values()]].copy()
    df_gt["audio_id"] = df_gt[GT_NAME_COL].map(normalize_audio_id)

    for ref_tag, ref_col in GT_REF_COLS.items():
        df_gt[f"reference_{ref_tag}"] = df_gt[ref_col].fillna("").astype(str).str.strip()

    has_reference = False
    for ref_tag in GT_REF_COLS:
        has_reference = has_reference | df_gt[f"reference_{ref_tag}"].ne("")

    df_gt = df_gt[df_gt["audio_id"].ne("") & has_reference]

    if df_gt.empty:
        raise RuntimeError("No transcripts found in GT CSV")

    out_cols = ["audio_id"] + [f"reference_{ref_tag}" for ref_tag in GT_REF_COLS]
    return df_gt[out_cols]


def normalize(text):
    if not isinstance(text, str):
        return ""
    text = text.strip().lower()
    if REMOVE_PUNCTUATION:
        text = text.translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", text).strip()


def normalize_audio_id(value) -> str:
    if pd.isna(value):
        return ""

    text = str(value).strip().lower().replace(".wav", "")
    # Align IDs like "sw02005_A_19" with "sw2005_A_19".
    text = re.sub(r"^sw0(?=\d{4}_)", "sw", text)
    return text


def print_summary(name: str, values: pd.Series):
    stats = {
        "n_utterances": int(len(values)),
        "mean_wer": float(values.mean()),
        "median_wer": float(values.median()),
        "std_wer": float(values.std()),
        "min_wer": float(values.min()),
        "max_wer": float(values.max()),
        "pct_wer_eq_0": float((values == 0).mean() * 100),
        "pct_wer_ge_1": float((values >= 1).mean() * 100),
    }

    print(f"\n===== WER SUMMARY: {name} =====")
    print(f"N utterances:        {stats['n_utterances']}")
    print(f"Mean WER:            {stats['mean_wer']:.4f}")
    print(f"Median WER:          {stats['median_wer']:.4f}")
    print(f"Std dev:             {stats['std_wer']:.4f}")
    print(f"Min WER:             {stats['min_wer']:.4f}")
    print(f"Max WER:             {stats['max_wer']:.4f}")
    print(f"% WER = 0:           {stats['pct_wer_eq_0']:.2f}%")
    print(f"% WER ≥ 1:           {stats['pct_wer_ge_1']:.2f}%")

    return stats


def compute_wer_breakdown(ref: str, hyp: str) -> dict:
    ref_words = ref.split()
    n_ref_words = len(ref_words)

    if n_ref_words == 0:
        return {
            "wer": 1.0,
            "substitutions": 0,
            "deletions": 0,
            "insertions": len(hyp.split()),
            "n_ref_words": 0,
            "s_rate": float("nan"),
            "d_rate": float("nan"),
            "i_rate": float("nan"),
        }

    out = process_words(ref, hyp)
    substitutions = int(out.substitutions)
    deletions = int(out.deletions)
    insertions = int(out.insertions)

    return {
        "wer": float(out.wer),
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
        "n_ref_words": n_ref_words,
        "s_rate": substitutions / n_ref_words,
        "d_rate": deletions / n_ref_words,
        "i_rate": insertions / n_ref_words,
    }


def main():
    # ---------- Load ASR ----------
    df_asr = pd.read_csv(ASR_CSV)
    df_asr["audio_id"] = df_asr[FILE_COL].map(normalize_audio_id)

    # ---------- Load GT ----------
    df_gt = load_gt_csv(GT_CSV)

    # ---------- Merge ----------
    df = df_asr.merge(df_gt, on="audio_id", how="inner")
    if df.empty:
        raise RuntimeError("No matching audio_id between ASR CSV and GT CSV")

    print(f"Matched {len(df)} utterances")

    # ---------- Compute WER ----------
    summary_rows = []

    for ref_tag in GT_REF_COLS:
        ref_data_col = f"reference_{ref_tag}"

        for hyp_tag, hyp_col in HYP_COLS.items():
            wers = []
            substitutions = []
            deletions = []
            insertions = []
            ref_word_counts = []
            s_rates = []
            d_rates = []
            i_rates = []

            for _, row in df.iterrows():
                ref = normalize(row.get(ref_data_col, ""))
                hyp = normalize(row.get(hyp_col, ""))
                breakdown = compute_wer_breakdown(ref, hyp)

                wers.append(breakdown["wer"])
                substitutions.append(breakdown["substitutions"])
                deletions.append(breakdown["deletions"])
                insertions.append(breakdown["insertions"])
                ref_word_counts.append(breakdown["n_ref_words"])
                s_rates.append(breakdown["s_rate"])
                d_rates.append(breakdown["d_rate"])
                i_rates.append(breakdown["i_rate"])

            col = f"wer_{hyp_tag}_vs_{ref_tag}"
            df[col] = wers
            s_col = f"s_{hyp_tag}_vs_{ref_tag}"
            d_col = f"d_{hyp_tag}_vs_{ref_tag}"
            i_col = f"i_{hyp_tag}_vs_{ref_tag}"
            s_rate_col = f"s_rate_{hyp_tag}_vs_{ref_tag}"
            d_rate_col = f"d_rate_{hyp_tag}_vs_{ref_tag}"
            i_rate_col = f"i_rate_{hyp_tag}_vs_{ref_tag}"
            ref_words_col = f"ref_words_{hyp_tag}_vs_{ref_tag}"
            df[s_col] = substitutions
            df[d_col] = deletions
            df[i_col] = insertions
            df[s_rate_col] = s_rates
            df[d_rate_col] = d_rates
            df[i_rate_col] = i_rates
            df[ref_words_col] = ref_word_counts

            stats = print_summary(f"{hyp_tag} vs {ref_tag}", df[col])
            total_ref_words = int(pd.Series(ref_word_counts).sum())
            total_s = int(pd.Series(substitutions).sum())
            total_d = int(pd.Series(deletions).sum())
            total_i = int(pd.Series(insertions).sum())
            s_rate_corpus = (total_s / total_ref_words) if total_ref_words else float("nan")
            d_rate_corpus = (total_d / total_ref_words) if total_ref_words else float("nan")
            i_rate_corpus = (total_i / total_ref_words) if total_ref_words else float("nan")

            print(f"Total S / D / I:      {total_s} / {total_d} / {total_i}")
            print(
                f"Corpus S / D / I rate:{s_rate_corpus:.4f} / {d_rate_corpus:.4f} / {i_rate_corpus:.4f}"
            )

            summary_rows.append(
                {
                    "comparison": f"{hyp_tag}_vs_{ref_tag}",
                    "hypothesis_tag": hyp_tag,
                    "reference_tag": ref_tag,
                    "wer_column": col,
                    "s_column": s_col,
                    "d_column": d_col,
                    "i_column": i_col,
                    "s_rate_column": s_rate_col,
                    "d_rate_column": d_rate_col,
                    "i_rate_column": i_rate_col,
                    "ref_words_column": ref_words_col,
                    "total_substitutions": total_s,
                    "total_deletions": total_d,
                    "total_insertions": total_i,
                    "total_ref_words": total_ref_words,
                    "corpus_s_rate": s_rate_corpus,
                    "corpus_d_rate": d_rate_corpus,
                    "corpus_i_rate": i_rate_corpus,
                    "mean_s_rate": float(pd.Series(s_rates).mean(skipna=True)),
                    "mean_d_rate": float(pd.Series(d_rates).mean(skipna=True)),
                    "mean_i_rate": float(pd.Series(i_rates).mean(skipna=True)),
                    **stats,
                }
            )

    # ---------- Save ----------
    out_path = ASR_CSV.replace(".csv", "_with_wer.csv")
    df.to_csv(out_path, index=False)
    print(f"\n📄 Saved → {out_path}")

    summary_out_path = ASR_CSV.replace(".csv", "_wer_summary.csv")
    pd.DataFrame(summary_rows).to_csv(summary_out_path, index=False)
    print(f"📄 Saved → {summary_out_path}")


if __name__ == "__main__":
    main()
