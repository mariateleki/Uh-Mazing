# python run_asr_gemini.py
import os
import time
import pandas as pd
from dotenv import load_dotenv
import google.generativeai as genai

# ======================= CONFIG =======================
load_dotenv()

AUDIO_DIR = "./preprocessed_audio_switchboard"
OUTPUT_CSV = "./asr_transcripts_gemini.csv"

MODEL_NAME = "gemini-2.5-pro"
SLEEP_SECONDS = 0.1

PROMPTS = {
    "standard": "Transcribe the speech.",
    "disfluent": (
        "Transcribe the speech verbatim, keeping any disfluencies (such as 'um', 'uh', repetitions, false starts, and hesitations)."
    ),
}

# =====================================================

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel(MODEL_NAME)


def transcribe_audio(wav_path: str, prompt: str) -> str:
    with open(wav_path, "rb") as f:
        audio_bytes = f.read()

    response = model.generate_content(
        [
            prompt,
            {
                "mime_type": "audio/wav",
                "data": audio_bytes,
            },
        ],
        generation_config={
            "temperature": 0.0,  
        },
    )

    return response.text.strip()


def main():
    wav_files = sorted(
        f for f in os.listdir(AUDIO_DIR)
        if f.lower().endswith(".wav")
    )

    if not wav_files:
        raise RuntimeError("No .wav files found")

    # -------- Resume / init --------
    if os.path.exists(OUTPUT_CSV):
        df = pd.read_csv(OUTPUT_CSV)
        print("🔁 Resuming existing CSV")
    else:
        df = pd.DataFrame(
            columns=[
                "file",
                "transcript_standard",
                "transcript_disfluent",
            ]
        )

    processed = set(df["file"]) if not df.empty else set()

    # -------- Main loop --------
    for wav in wav_files:
        if wav in processed:
            continue

        wav_path = os.path.join(AUDIO_DIR, wav)
        print(f"\n🎧 {wav}")

        row = {"file": wav}

        for tag, prompt in PROMPTS.items():
            print(f"  → {tag}")

            try:
                text = transcribe_audio(wav_path, prompt)
            except Exception as e:
                print(f"⚠️ ERROR ({tag}): {e}")
                text = ""

            row[f"transcript_{tag}"] = text
            time.sleep(SLEEP_SECONDS)

            print("FILE:", wav, "\nTEXT:", text, "\n\n")

        df.loc[len(df)] = row
        df.to_csv(OUTPUT_CSV, index=False)

    print("\n✅ All files processed")
    print(f"📄 Saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
