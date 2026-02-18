#!/usr/bin/env python3
"""Score translation outputs with a GPT judge using llm-as-a-judge/prompt.txt.

Usage:
  python llm-as-a-judge/score_outputs_gpt.py
  python llm-as-a-judge/score_outputs_gpt.py --input-glob 'outputs/*gemini*.csv' --model gpt-5.2-2025-12-11
"""

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import List

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI


SOURCE_COL = "EN_disfluent"
SKIP_SOURCE_SUFFIXES = {"disfluent", "fluent"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score translation CSVs with a GPT judge.")
    parser.add_argument("--input-glob", default="outputs/*.csv", help="Glob for output CSV files to score.")
    parser.add_argument(
        "--prompt-file",
        default="llm-as-a-judge/prompt.txt",
        help="Judge prompt template file.",
    )
    parser.add_argument(
        "--out-dir",
        default="llm-as-a-judge/scores",
        help="Directory for scored CSV outputs.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5.2-2025-12-11",
        help="OpenAI model to use as judge.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.1,
        help="Pause between API calls.",
    )
    parser.add_argument(
        "--print-examples",
        type=int,
        default=3,
        help="Number of source/target examples to print per file before scoring.",
    )
    parser.add_argument(
        "--retry-sleep-seconds",
        type=float,
        default=1.0,
        help="Sleep between judge retries when output is invalid.",
    )
    return parser.parse_args()


def translation_columns(df: pd.DataFrame) -> List[str]:
    cols: List[str] = []
    for col in df.columns:
        if "_" not in col:
            continue
        lang, suffix = col.split("_", 1)
        if len(lang) != 2 or not lang.isupper():
            continue
        if suffix in SKIP_SOURCE_SUFFIXES:
            continue
        cols.append(col)
    return cols


def clean_json_text(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\\s*", "", t)
        t = re.sub(r"\\s*```$", "", t)
    return t.strip()


def judge_one(
    client: OpenAI,
    model: str,
    base_prompt: str,
    source_text: str,
    target_text: str,
    lang_code: str,
    retry_sleep_seconds: float,
) -> dict:
    if "<SOURCE-TEXT>" in base_prompt and "<TARGET-TEXT>" in base_prompt:
        user_prompt = (
            base_prompt.replace("<SOURCE-TEXT>", source_text).replace("<TARGET-TEXT>", target_text)
        )
    else:
        user_prompt = (
            f"{base_prompt}\n\n"
            f"SOURCE ({lang_code}):\n{source_text}\n\n"
            f"TARGET ({lang_code}):\n{target_text}"
        )

    while True:
        try:
            response = client.responses.create(
                model=model,
                temperature=0.0,
                reasoning={"effort": "none"},
                input=user_prompt,
            )
            raw = (response.output_text or "").strip()
            parsed = json.loads(clean_json_text(raw))

            if not isinstance(parsed, dict):
                raise ValueError("Judge output is not a JSON object")

            has_style = "style_preservation_score" in parsed and str(parsed.get("style_preservation_score", "")).strip() != ""
            has_meaning = "meaning_preservation_score" in parsed and str(parsed.get("meaning_preservation_score", "")).strip() != ""
            if not has_style or not has_meaning:
                raise ValueError("Judge output missing style/meaning scores")

            if "errors" not in parsed:
                raise ValueError("Judge output missing errors key")

            return parsed
        except Exception as exc:
            print(f"RETRY | {lang_code} | invalid judge output: {exc}")
            time.sleep(retry_sleep_seconds)


def ensure_score_columns(df: pd.DataFrame, trans_cols: List[str]) -> None:
    for col in trans_cols:
        for suffix in (
            "judge_style_preservation_score",
            "judge_meaning_preservation_score",
            "judge_errors_json",
            "judge_status",
            "judge_error_message",
        ):
            score_col = f"{col}__{suffix}"
            if score_col not in df.columns:
                df[score_col] = ""


def row_already_scored(row: pd.Series, col: str) -> bool:
    style_col = f"{col}__judge_style_preservation_score"
    meaning_col = f"{col}__judge_meaning_preservation_score"
    status_col = f"{col}__judge_status"

    style = row.get(style_col, "")
    meaning = row.get(meaning_col, "")
    status = str(row.get(status_col, "")).strip().lower()

    has_scores = pd.notna(style) and str(style).strip() != "" and pd.notna(meaning) and str(meaning).strip() != ""
    return has_scores and status == "ok"


def score_file(
    client: OpenAI,
    csv_path: Path,
    out_dir: Path,
    base_prompt: str,
    model: str,
    sleep_seconds: float,
    print_examples: int,
    retry_sleep_seconds: float,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{csv_path.stem}__judge-{model}.csv"

    if out_path.exists():
        df = pd.read_csv(out_path)
        print(f"Resuming: {csv_path.name}")
    else:
        df = pd.read_csv(csv_path)
        print(f"Scoring: {csv_path.name}")

    trans_cols = translation_columns(df)
    ensure_score_columns(df, trans_cols)
    maybe_print_examples(df=df, csv_path=csv_path, trans_cols=trans_cols, print_examples=print_examples)

    if SOURCE_COL not in df.columns:
        raise RuntimeError(f"Missing required source column: {SOURCE_COL} in {csv_path}")

    for idx, row in df.iterrows():
        for t_col in trans_cols:
            if row_already_scored(row, t_col):
                continue

            lang_code = t_col.split("_", 1)[0]
            source_text = (
                str(row.get(SOURCE_COL, ""))
                .replace("_", "")
                .replace(" ,", ",")
                .replace(" .", ".")
                .replace(" '", "'")
            )
            source_text = re.sub(r"\s+", " ", source_text).strip()
            target_text = row.get(t_col, "")
            if pd.isna(source_text) or not str(source_text).strip():
                df.at[idx, f"{t_col}__judge_status"] = "skipped"
                df.at[idx, f"{t_col}__judge_error_message"] = "Empty source text"
                continue
            if pd.isna(target_text) or not str(target_text).strip():
                df.at[idx, f"{t_col}__judge_status"] = "skipped"
                df.at[idx, f"{t_col}__judge_error_message"] = "Empty target text"
                continue

            result = judge_one(
                client=client,
                model=model,
                base_prompt=base_prompt,
                source_text=str(source_text),
                target_text=str(target_text),
                lang_code=lang_code,
                retry_sleep_seconds=retry_sleep_seconds,
            )
            errors = result.get("errors", [])
            style = result.get("style_preservation_score", "")
            meaning = result.get("meaning_preservation_score", "")

            df.at[idx, f"{t_col}__judge_style_preservation_score"] = style
            df.at[idx, f"{t_col}__judge_meaning_preservation_score"] = meaning
            df.at[idx, f"{t_col}__judge_errors_json"] = json.dumps(errors, ensure_ascii=False)
            df.at[idx, f"{t_col}__judge_status"] = "ok"
            df.at[idx, f"{t_col}__judge_error_message"] = ""
            print(f"OK    | {csv_path.name} | row {idx} | {t_col} | style={style} meaning={meaning}")

            time.sleep(sleep_seconds)

        # Persist progress row-by-row for safe resume.
        df.to_csv(out_path, index=False)

    print(f"Saved: {out_path}")


def maybe_print_examples(df: pd.DataFrame, csv_path: Path, trans_cols: List[str], print_examples: int) -> None:
    if print_examples <= 0:
        return

    if SOURCE_COL not in df.columns:
        print(f"EXAMPLE | {csv_path.name} | skipped: missing {SOURCE_COL}")
        return

    printed = 0
    for idx, row in df.iterrows():
        if printed >= print_examples:
            break
        for t_col in trans_cols:
            if printed >= print_examples:
                break
            source_text = (
                str(row.get(SOURCE_COL, ""))
                .replace("_", "")
                .replace(" ,", ",")
                .replace(" .", ".")
                .replace(" '", "'")
            )
            source_text = re.sub(r"\s+", " ", source_text).strip()
            target_text = row.get(t_col, "")
            if pd.isna(source_text) or not str(source_text).strip():
                continue
            if pd.isna(target_text) or not str(target_text).strip():
                continue

            source_preview = str(source_text).replace("\n", " ")[:180]
            target_preview = str(target_text).replace("\n", " ")[:180]
            print(f"EXAMPLE | {csv_path.name} | row {idx} | {SOURCE_COL} -> {t_col}")
            print(f"  SOURCE: {source_preview}")
            print(f"  TARGET: {target_preview}")
            printed += 1


def main() -> None:
    load_dotenv()
    args = parse_args()

    prompt_path = Path(args.prompt_file)
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    base_prompt = prompt_path.read_text(encoding="utf-8").strip()
    input_paths = sorted(Path(".").glob(args.input_glob))
    if not input_paths:
        print(f"No files matched: {args.input_glob}")
        return

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        organization=os.getenv("OPENAI_ORG_KEY"),
        project=os.getenv("OPENAI_PROJECT_KEY"),
    )

    out_dir = Path(args.out_dir)

    for csv_path in input_paths:
        score_file(
            client=client,
            csv_path=csv_path,
            out_dir=out_dir,
            base_prompt=base_prompt,
            model=args.model,
            sleep_seconds=args.sleep_seconds,
            print_examples=args.print_examples,
            retry_sleep_seconds=args.retry_sleep_seconds,
        )


if __name__ == "__main__":
    main()
