# python ./experiments/run_translate.py --model gemini --mode text
# python ./experiments/run_translate.py --model gemini --mode text --noextra
# python ./experiments/run_translate.py --model gemini --mode audio
# python ./experiments/run_translate.py --model gemini --mode audio --noextra
# python ./experiments/run_translate.py --model gemini --mode node-combos
# python ./experiments/run_translate.py --model gemini --mode node-combos --noextra
# python ./experiments/run_translate.py --model gpt --mode text
# python ./experiments/run_translate.py --model gpt --mode text --noextra
# python ./experiments/run_translate.py --model gpt --mode audio
# python ./experiments/run_translate.py --model gpt --mode audio --noextra
# python ./experiments/run_translate.py --model gpt --mode node-combos
# python ./experiments/run_translate.py --model gpt --mode node-combos --noextra
# python ./experiments/run_translate.py --model gemini --mode text --input-csv ./data/other.csv
import argparse
import os
import re
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# ======================= CONFIG =======================
load_dotenv()

OUTPUT_DIR = "./outputs"
SLEEP_SECONDS = 0.1
VERBOSE_FIRST_N = 3  # print full details for the first N API calls per condition

MODEL_CONFIGS = {
    "gemini": {
        "model_name": "gemini-2.5-flash",
        "model_tag": "gemini-2.5-flash",
    },
    "gpt": {
        "model_name": "gpt-5.2-2025-12-11",
        "model_tag": "gpt52",
        "asr_model_name": "gpt-4o-transcribe",
    },
}

LANGUAGES = {
    "ZH": "Mandarin",
    "ES": "Spanish",
    "HI": "Hindi",
    "FR": "French",
    "DE": "German",
    "IT": "Italian",
    "CZ": "Czech",
    "AR": "Arabic",
}

NOEXTRA_SUFFIX = " Only return the answer requested. Do not include any explanation or introductions."

TEXT_STANDARD   = "Translate the transcribed speech into <LANGUAGE> text."
TEXT_DISFLUENT  = ("Translate the transcribed speech into <LANGUAGE> text, keeping any disfluencies "
                   "(such as 'um', 'uh', repetitions, and hesitations) in the translation.")
AUDIO_STANDARD  = "Translate the speech audio into <LANGUAGE> text."
AUDIO_DISFLUENT = ("Translate the speech audio into <LANGUAGE> text, keeping any disfluencies "
                    "(such as 'um', 'uh', repetitions, and hesitations) in the translation.")

NODE_COMBO_COLS = [
    "edited_nodes_only",
    "intj_only",
    "prn_only",
    "edited_intj",
    "intj_prn",
    "edited_prn",
    "edited_prn_intj",
]

# =====================================================


def make_prompt(base: str, noextra: bool) -> str:
    return base + NOEXTRA_SUFFIX if noextra else base


def id_to_audio_filename(value: str) -> str:
    text = str(value).strip()
    text = re.sub(r"\.wav$", "", text, flags=re.IGNORECASE)
    m = re.match(r"^sw0?(\d{4})_([abAB])_(\d+)$", text)
    if m:
        call_id, speaker, turn = m.groups()
        return f"sw0{call_id}_{speaker.upper()}_{turn}.wav"
    return f"{text}.wav"


# ---- Gemini API calls ----

def init_gemini():
    import google.generativeai as genai
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY (or GOOGLE_API_KEY)")
    print(f"  [DEBUG init_gemini] API key loaded (first 8 chars): {api_key[:8]}...")
    genai.configure(api_key=api_key)
    model_name = MODEL_CONFIGS["gemini"]["model_name"]
    print(f"  [DEBUG init_gemini] Using model: {model_name}")
    return genai.GenerativeModel(model_name)


def gemini_text(client, prompt: str) -> str:
    response = client.generate_content(prompt)
    print(f"  [DEBUG gemini_text] type={type(response).__name__}, text repr={response.text!r}")
    return response.text


def gemini_audio(client, wav_path: Path, prompt: str) -> str:
    audio_bytes = wav_path.read_bytes()
    response = client.generate_content(
        [prompt, {"mime_type": "audio/wav", "data": audio_bytes}],
        generation_config={"temperature": 0.0},
    )
    print(f"  [DEBUG gemini_audio] type={type(response).__name__}, text repr={response.text!r}")
    return (response.text or "").strip()


# ---- GPT API calls ----

def init_gpt():
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    org_key = os.getenv("OPENAI_ORG_KEY")
    project_key = os.getenv("OPENAI_PROJECT_KEY")
    if not api_key:
        print("  [WARNING init_gpt] OPENAI_API_KEY is missing!")
    else:
        print(f"  [DEBUG init_gpt] API key loaded (first 8 chars): {api_key[:8]}...")
    if not org_key:
        print("  [WARNING init_gpt] OPENAI_ORG_KEY is missing (may be optional)")
    if not project_key:
        print("  [WARNING init_gpt] OPENAI_PROJECT_KEY is missing (may be optional)")
    return OpenAI(
        api_key=api_key,
        organization=org_key,
        project=project_key,
    )


def gpt_text(client, prompt: str) -> str:
    model_name = MODEL_CONFIGS["gpt"]["model_name"]
    response = client.responses.create(
        model=model_name,
        temperature=1.0,
        reasoning={"effort": "none"},
        input=prompt,
    )
    print(f"  [DEBUG gpt_text] type={type(response).__name__}, attrs={[a for a in dir(response) if not a.startswith('_')]}")
    print(f"  [DEBUG gpt_text] output_text repr={response.output_text!r}")
    if hasattr(response, 'output'):
        print(f"  [DEBUG gpt_text] output={response.output}")
    return response.output_text.strip()


def gpt_audio(client, wav_path: Path, prompt: str) -> str:
    asr_model = MODEL_CONFIGS["gpt"]["asr_model_name"]
    with open(wav_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            file=audio_file,
            model=asr_model,
            prompt=prompt,
        )
    print(f"  [DEBUG gpt_audio] type={type(response).__name__}, text repr={response.text!r}")
    return (response.text or "").strip()


# ---- Dispatch table ----

API_FUNCS = {
    "gemini": {"init": init_gemini, "text": gemini_text, "audio": gemini_audio},
    "gpt":    {"init": init_gpt,    "text": gpt_text,    "audio": gpt_audio},
}


# ---- Core loop ----

def run_condition(client, call_text, call_audio, model_tag, df_base,
                  condition_name, source_col, prompt_template,
                  noextra, is_audio=False, audio_dir=None, file_prefix="uh-mazing"):
    suffix = "-noextra" if noextra else ""
    out_path = Path(OUTPUT_DIR) / f"{file_prefix}_{model_tag}_{condition_name}{suffix}.csv"

    print(f"\n🚀 Running condition: {condition_name}{suffix}")

    if out_path.exists():
        df_out = pd.read_csv(out_path)
        print("🔁 Resuming existing file")
    else:
        df_out = df_base.copy()
        for lang in LANGUAGES:
            df_out[f"{lang}_{model_tag}"] = ""

    call_count = 0

    for idx, row in df_out.iterrows():
        if is_audio:
            wav_name = row.get("_audio_filename", "")
            wav_path = Path(audio_dir) / str(wav_name)
            if not wav_path.exists():
                continue
        else:
            src_text = row[source_col]
            if pd.isna(src_text) or not str(src_text).strip():
                continue
            src_text = str(src_text).replace("__", "").replace("_", "")

        for lang_code, lang_name in LANGUAGES.items():
            out_col = f"{lang_code}_{model_tag}"
            existing = row.get(out_col, "")
            if isinstance(existing, str) and existing.strip():
                continue

            prompt = prompt_template.replace("<LANGUAGE>", lang_name)
            translation = ""

            try:
                if is_audio:
                    translation = call_audio(client, wav_path, prompt)
                else:
                    translation = call_text(client, f"{prompt}\n{src_text}")
                df_out.at[idx, out_col] = translation
                call_count += 1
                print(f"✓ {condition_name}{suffix} | row {idx} → {lang_code}")
            except Exception as e:
                print(f"⚠️ ERROR {condition_name}{suffix} | row {idx} → {lang_code}: {e}")
                df_out.at[idx, out_col] = ""
                call_count += 1

            if call_count <= VERBOSE_FIRST_N:
                print(f"\n{'━'*70}")
                print(f"  CALL {call_count}/{VERBOSE_FIRST_N} | {condition_name}{suffix} | row {idx} → {lang_code} ({lang_name})")
                print(f"  MODEL: {model_tag}")
                print(f"{'━'*70}")
                if is_audio:
                    print(f"  AUDIO FILE:\n    {wav_path}")
                else:
                    print(f"  SOURCE TEXT:")
                    print(f"    {src_text}")
                print(f"\n  FULL PROMPT:")
                if is_audio:
                    print(f"    {prompt}")
                else:
                    print(f"    {prompt}")
                    print(f"    {src_text}")
                print(f"\n  MODEL OUTPUT:")
                print(f"    {translation}")
                print(f"{'━'*70}\n")

            time.sleep(SLEEP_SECONDS)

        df_out.to_csv(out_path, index=False)

    print(f"✅ Finished {condition_name}{suffix}")
    print(f"📄 Saved to {out_path}")


# ---- Condition builders ----

def build_text_conditions(noextra):
    return {
        "text_standard_fluent":     {"source_col": "EN_fluent",    "prompt": make_prompt(TEXT_STANDARD, noextra)},
        "text_disfluent_fluent":    {"source_col": "EN_fluent",    "prompt": make_prompt(TEXT_DISFLUENT, noextra)},
        "text_standard_disfluent":  {"source_col": "EN_disfluent", "prompt": make_prompt(TEXT_STANDARD, noextra)},
        "text_disfluent_disfluent": {"source_col": "EN_disfluent", "prompt": make_prompt(TEXT_DISFLUENT, noextra)},
    }


def build_audio_conditions(noextra):
    return {
        "audio_standard":  {"prompt": make_prompt(AUDIO_STANDARD, noextra)},
        "audio_disfluent": {"prompt": make_prompt(AUDIO_DISFLUENT, noextra)},
    }


def build_node_combo_conditions(noextra):
    conditions = {}
    for combo_col in NODE_COMBO_COLS:
        conditions[f"standard_{combo_col}"]  = {"source_col": combo_col, "prompt": make_prompt(TEXT_STANDARD, noextra)}
        conditions[f"disfluent_{combo_col}"] = {"source_col": combo_col, "prompt": make_prompt(TEXT_DISFLUENT, noextra)}
    return conditions


# ---- Main ----

def main():
    parser = argparse.ArgumentParser(description="Run translation experiments (Gemini or GPT)")
    parser.add_argument("--model", required=True, choices=["gemini", "gpt"],
                        help="Model backend: gemini or gpt")
    parser.add_argument("--mode", required=True, choices=["text", "audio", "node-combos"],
                        help="Experiment mode: text, audio, or node-combos")
    parser.add_argument("--noextra", action="store_true",
                        help="Append 'only return the answer' suffix to prompts")
    parser.add_argument("--input-csv", default=None,
                        help="Override input CSV path")
    parser.add_argument("--audio-dir", default="./asr/preprocessed_audio_switchboard",
                        help="Directory containing .wav files (audio mode only)")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    funcs = API_FUNCS[args.model]
    client = funcs["init"]()
    call_text = funcs["text"]
    call_audio = funcs["audio"]
    model_tag = MODEL_CONFIGS[args.model]["model_tag"]

    def run(conditions, file_prefix="uh-mazing", is_audio=False):
        for name, cfg in conditions.items():
            run_condition(
                client, call_text, call_audio, model_tag, df_base,
                name, cfg.get("source_col"), cfg["prompt"],
                args.noextra, is_audio=is_audio, audio_dir=args.audio_dir,
                file_prefix=file_prefix,
            )

    if args.mode == "text":
        input_csv = args.input_csv or "./data/uh-mazing.csv"
        df_base = pd.read_csv(input_csv)
        run(build_text_conditions(args.noextra))

    elif args.mode == "audio":
        input_csv = args.input_csv or "./data/uh-mazing.csv"
        df_base = pd.read_csv(input_csv)
        if "ID" not in df_base.columns:
            raise RuntimeError(f"Missing 'ID' column in {input_csv}")
        df_base["_audio_filename"] = df_base["ID"].map(id_to_audio_filename)
        run(build_audio_conditions(args.noextra), is_audio=True)

    elif args.mode == "node-combos":
        input_csv = args.input_csv or "./data/train-marked-with-node-combos.csv"
        df_base = pd.read_csv(input_csv)
        if "keep" in df_base.columns:
            df_base = df_base[df_base["keep"] == True].reset_index(drop=True)
            print(f"Filtered to {len(df_base)} rows with keep=True")
        run(build_node_combo_conditions(args.noextra), file_prefix="node-combos")

    print(f"\n{'='*50}")
    print(f"All conditions for --model {args.model} --mode {args.mode} {'--noextra ' if args.noextra else ''}complete.")


if __name__ == "__main__":
    main()
