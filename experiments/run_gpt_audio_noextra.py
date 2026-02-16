# python ./experiments/run_gpt_audio_noextra.py
import os
import re
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

# ======================= CONFIG =======================
load_dotenv()

INPUT_CSV = "./data/uh-mazing.csv"
AUDIO_DIR = "./asr/preprocessed_audio_switchboard"
OUTPUT_DIR = "./outputs"
SLEEP_SECONDS = 0.1

ID_COL = "ID"
ASR_MODEL_NAME = "gpt-4o-transcribe"
MODEL_TAG = "gpt52"

LANGUAGES = {
    "ZH": "Mandarin",
    "ES": "Spanish",
    "HI": "Hindi",
    "FR": "French",
    "DE": "German",
    "IT": "Italian",
    "SW": "Swahili",
    "CZ": "Czech",
    "AR": "Arabic",
    "LG": "Luganda",
}

AUDIO_STANDARD_PROMPT = (
    "Translate the speech audio into <LANGUAGE> text. "
    "Only return the answer requested. Do not include any explanation or introductions."
)
AUDIO_DISFLUENT_PROMPT = (
    "Translate the speech audio into <LANGUAGE> text, keeping any disfluencies "
    "(such as 'um', 'uh', repetitions, and hesitations) in the translation. "
    "Only return the answer requested. Do not include any explanation or introductions."
)

CONDITIONS = {
    "audio_standard": {"prompt": AUDIO_STANDARD_PROMPT},
    "audio_disfluent": {"prompt": AUDIO_DISFLUENT_PROMPT},
}
# =====================================================


def id_to_audio_filename(value: str) -> str:
    text = str(value).strip()
    text = re.sub(r"\.wav$", "", text, flags=re.IGNORECASE)

    m = re.match(r"^sw(\d{4})_([abAB])_(\d+)$", text)
    if m:
        call_id, speaker, turn = m.groups()
        return f"sw0{call_id}_{speaker.upper()}_{turn}.wav"

    m = re.match(r"^sw0(\d{4})_([abAB])_(\d+)$", text)
    if m:
        call_id, speaker, turn = m.groups()
        return f"sw0{call_id}_{speaker.upper()}_{turn}.wav"

    return f"{text}.wav"


def transcribe_audio(client: OpenAI, wav_path: Path, prompt: str) -> str:
    with open(wav_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            file=audio_file,
            model=ASR_MODEL_NAME,
            prompt=prompt,
        )

    return (response.text or "").strip()


def run_condition(client: OpenAI, df_base: pd.DataFrame, condition_name: str, cfg: dict):
    print(f"\nRunning condition: {condition_name}")
    out_path = Path(OUTPUT_DIR) / f"uh-mazing_{MODEL_TAG}_{condition_name}-noextra.csv"

    if out_path.exists():
        df_out = pd.read_csv(out_path)
        print("Resuming existing output file")
    else:
        df_out = df_base.copy()
        for lang in LANGUAGES:
            df_out[f"{lang}_{MODEL_TAG}"] = ""

    audio_col = "_audio_filename"

    for idx, row in df_out.iterrows():
        wav_name = row.get(audio_col, "")
        wav_path = Path(AUDIO_DIR) / str(wav_name)
        if not wav_path.exists():
            continue

        for lang_code, lang_name in LANGUAGES.items():
            out_col = f"{lang_code}_{MODEL_TAG}"
            existing = row.get(out_col, "")
            if isinstance(existing, str) and existing.strip():
                continue

            prompt = cfg["prompt"].replace("<LANGUAGE>", lang_name)
            try:
                text = transcribe_audio(client, wav_path, prompt)
                df_out.at[idx, out_col] = text
                print(f"✓ {condition_name} | row {idx} -> {lang_code}")
            except Exception as exc:
                print(f"ERROR {condition_name} | row {idx} -> {lang_code}: {exc}")
                df_out.at[idx, out_col] = ""

            time.sleep(SLEEP_SECONDS)

        df_out.to_csv(out_path, index=False)

    print(f"Saved: {out_path}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        organization=os.getenv("OPENAI_ORG_KEY"),
        project=os.getenv("OPENAI_PROJECT_KEY"),
    )

    df_base = pd.read_csv(INPUT_CSV)
    if ID_COL not in df_base.columns:
        raise RuntimeError(f"Missing '{ID_COL}' column in {INPUT_CSV}")
    df_base["_audio_filename"] = df_base[ID_COL].map(id_to_audio_filename)

    for condition_name, cfg in CONDITIONS.items():
        run_condition(client, df_base, condition_name, cfg)


if __name__ == "__main__":
    main()
