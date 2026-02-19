# python ./experiments/run_gpt.py
import os
import time
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv

# ======================= CONFIG =======================
load_dotenv()

INPUT_CSV = "./data/uh-mazing.csv"
OUTPUT_DIR = "./outputs"
SLEEP_SECONDS = 0.1

MODEL_NAME = "gpt-5.2-2025-12-11"
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

TEXT_STANDARD_PROMPT = (
    "Translate the transcribed speech into <LANGUAGE> text. "
    "Only return the answer requested. Do not include any explanation or introductions."
)

TEXT_DISFLUENT_PROMPT = (
    "Translate the transcribed speech into <LANGUAGE> text, keeping any disfluencies "
    "(such as 'um', 'uh', repetitions, and hesitations) in the translation. "
    "Only return the answer requested. Do not include any explanation or introductions."
)

# ------------- Experimental Conditions -------------
CONDITIONS = {
    "text_standard_fluent": {
        "source_col": "EN_fluent",
        "prompt": TEXT_STANDARD_PROMPT
    },
    "text_disfluent_fluent": {
        "source_col": "EN_fluent",
        "prompt": TEXT_DISFLUENT_PROMPT
    },
    "text_standard_disfluent": {
        "source_col": "EN_disfluent",
        "prompt": TEXT_STANDARD_PROMPT
    },
    "text_disfluent_disfluent": {
        "source_col": "EN_disfluent",
        "prompt": TEXT_DISFLUENT_PROMPT
    },
}

# =====================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    organization=os.getenv("OPENAI_ORG_KEY"),
    project=os.getenv("OPENAI_PROJECT_KEY"),
)

def call_api(prompt: str) -> str:
    response = client.responses.create(
        model=MODEL_NAME,
        temperature=1.0,
        reasoning={"effort": "none"},
        input=prompt,
    )
    return response.output_text.strip()


def run_condition(df_base, condition_name, cfg):
    print(f"\n🚀 Running condition: {condition_name}")

    out_path = os.path.join(
        OUTPUT_DIR,
        f"uh-mazing_{MODEL_TAG}_{condition_name}-noextra.csv"
    )

    # -------- Resume / init --------
    if os.path.exists(out_path):
        df_out = pd.read_csv(out_path)
        print("🔁 Resuming existing file")
    else:
        df_out = df_base.copy()
        for lang in LANGUAGES:
            df_out[f"{lang}_{MODEL_TAG}"] = ""

    # -------- Main loop --------
    for idx, row in df_out.iterrows():
        src_text = row[cfg["source_col"]]
        src_text = str(src_text).replace("_", "")

        if "_" in src_text:
            print("!!!!!!!!!!!! lksal;kdfjlaksdjfalksdjfllas;f")

        if pd.isna(src_text) or not str(src_text).strip():
            continue

        for lang_code, lang_name in LANGUAGES.items():
            out_col = f"{lang_code}_{MODEL_TAG}"

            if isinstance(row[out_col], str) and row[out_col].strip():
                continue

            prompt = cfg["prompt"].replace("<LANGUAGE>", lang_name)
            full_prompt = f"{prompt}\n{src_text}"
            translation = ""

            try:
                translation = call_api(full_prompt)
                df_out.at[idx, out_col] = translation
                print(f"✓ {condition_name} | row {idx} → {lang_code}")
            except Exception as e:
                print(f"⚠️ ERROR {condition_name} | row {idx} → {lang_code}: {e}")
                df_out.at[idx, out_col] = ""

            print(full_prompt, translation)

            time.sleep(SLEEP_SECONDS)

        df_out.to_csv(out_path, index=False)

    print(f"✅ Finished {condition_name}")
    print(f"📄 Saved to {out_path}")


def main():
    df_base = pd.read_csv(INPUT_CSV)
    df_base = df_base

    for condition_name, cfg in CONDITIONS.items():
        run_condition(df_base, condition_name, cfg)


if __name__ == "__main__":
    main()
