# Run: python prolific_round2/bulk_create_studies.py
#
# Creates one Prolific study per (language × part) for the disfluency
# annotation site at docs/annotate.html. By default that's 16 studies:
# 8 languages × 2 halves of 40 utterances each.
#
# Each study:
#   - filters native speakers of the target language (fluent in English too)
#   - points at https://mariateleki.github.io/Uh-Mazing/annotate.html
#     with ?lang=XX&part=N&cc=<unique completion code>
#   - registers that same completion code with Prolific so the participant
#     can return successfully
#   - allocates TOTAL_PLACES_PER_STUDY slots (default 3) so multiple workers
#     can pick up the same part independently
#
# Output: prolific_round2/results.csv  (study IDs + dashboard URLs)
# Required env vars (set in .env at repo root):
#   PROLIFIC_TOKEN, PROLIFIC_PROJECT_ID

import csv
import os
import time
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------
load_dotenv()
API_TOKEN = os.getenv("PROLIFIC_TOKEN")
PROJECT   = os.getenv("PROLIFIC_PROJECT_ID")
BASE_URL  = "https://api.prolific.com/api/v1"

ANNOTATE_BASE = "https://mariateleki.github.io/Uh-Mazing/annotate.html"
RESULTS_CSV   = "prolific_round2/results.csv"

# Languages to publish for; LANG_NAMES are used in study titles/descriptions.
LANGUAGES = {
    "AR": "Arabic",
    "CS": "Czech",
    "DE": "German",
    "ES": "Spanish",
    "FR": "French",
    "HI": "Hindi",
    "IT": "Italian",
    "ZH": "Mandarin",
}

# Prolific filter choice IDs for the "first-language" filter.
# Verify with create_forms_and_studies/check_prolific_filters.py.
FIRST_LANGUAGE_CHOICE_IDS = {
    "AR": "3",
    "CS": "11",
    "DE": "27",
    "ES": "59",
    "FR": "24",
    "HI": "30",
    "IT": "35",
    "ZH": "80",
}
FIRST_LANGUAGE_FILTER_ID   = "first-language"
FLUENT_LANGUAGES_FILTER_ID = "fluent-languages"
ENGLISH_CHOICE_ID          = "19"

PARTS = [1, 2]               # 40 items each
TOTAL_PLACES_PER_STUDY = 3   # how many distinct workers per (lang × part)

# Reward / time. annotate.html quotes "15–20 minutes" for half a language;
# we budget 25 min on Prolific so workers don't feel rushed and the per-hour
# rate stays at $12/hr ($5 for 25 min).
ESTIMATED_TIME_MIN  = 25
REWARD_USD_CENTS    = 500    # $5.00 per submission
MIN_COMPLETION_TIME = 8      # auto-reject submissions faster than 8 min

DEVICE_COMPATIBILITY = ["desktop"]
PROLIFIC_ID_OPTION   = "url_parameters"  # Prolific appends ?PROLIFIC_PID=…
PRIVACY_NOTICE_URL   = (
    # The privacy policy text now lives inside annotate.html itself as the
    # consent screen. Keeping a short fallback URL here for Prolific's UI.
    "https://mariateleki.github.io/Uh-Mazing/annotate.html"
)

DELAY_SECONDS = 1
TEST_MODE     = False   # True = create 1 study (the first one) for preview

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------
HEADERS = {
    "Authorization": f"Token {API_TOKEN}",
    "Content-Type":  "application/json",
}

STUDY_TITLE_TEMPLATE = "Disfluency Annotation — {lang_name} (part {part} of 2)"
STUDY_DESCRIPTION_TEMPLATE = """You will look at short English utterances paired with their {lang_name} translations and highlight which words in the translation correspond to the disfluencies (filler words, repetitions, false starts) marked in the English. If a translation is missing words or contains errors, you can edit it.

This is **part {part} of 2** for {lang_name} (40 utterances). The other half is in a separate Prolific study.

This study should take approximately {time_min} minutes.

Native {lang_name} speakers only. The site asks you to read and accept a short privacy policy before you start."""


def completion_code(lang_code, part):
    """Stable per-(lang × part) code, used both in the URL and registered
    with Prolific as the COMPLETED code."""
    return f"UM-{lang_code}-P{part}"


def study_url(lang_code, part):
    cc = completion_code(lang_code, part)
    qs = urlencode({"lang": lang_code, "part": part, "cc": cc})
    # Prolific appends &PROLIFIC_PID=… so the &pid=… on annotate.html isn't
    # used here — annotate.html reads the Prolific PID from the URL
    # automatically when prolific_id_option is "url_parameters".
    return f"{ANNOTATE_BASE}?{qs}"


def build_filters(lang_code):
    if lang_code not in FIRST_LANGUAGE_CHOICE_IDS:
        raise ValueError(f"No first-language mapping for lang_code={lang_code!r}")
    return [
        {
            "filter_id":       FIRST_LANGUAGE_FILTER_ID,
            "selected_values": [FIRST_LANGUAGE_CHOICE_IDS[lang_code]],
        },
        {
            "filter_id":       FLUENT_LANGUAGES_FILTER_ID,
            "selected_values": [ENGLISH_CHOICE_ID],
        },
    ]


def build_payload(lang_code, lang_name, part):
    cc = completion_code(lang_code, part)
    return {
        "name":           STUDY_TITLE_TEMPLATE.format(lang_name=lang_name, part=part),
        "internal_name":  f"uh-mazing_round2_disfluency_{lang_code.lower()}_p{part}",
        "description":    STUDY_DESCRIPTION_TEMPLATE.format(
                              lang_name=lang_name, part=part, time_min=ESTIMATED_TIME_MIN),
        "external_study_url":        study_url(lang_code, part),
        "project":                   PROJECT,
        "prolific_id_option":        PROLIFIC_ID_OPTION,
        "total_available_places":    TOTAL_PLACES_PER_STUDY,
        "estimated_completion_time": ESTIMATED_TIME_MIN,
        "reward":                    REWARD_USD_CENTS,
        "currency":                  "USD",
        "filters":                   build_filters(lang_code),
        "device_compatibility":      DEVICE_COMPATIBILITY,
        "privacy_notice_url":        PRIVACY_NOTICE_URL,
        "minimum_completion_time":   MIN_COMPLETION_TIME,
        "completion_codes": [
            {
                "code":      cc,
                "code_type": "COMPLETED",
                "actions":   [{"action": "AUTOMATICALLY_APPROVE"}],
            }
        ],
    }


def create_draft_study(payload):
    res = requests.post(f"{BASE_URL}/studies/", json=payload, headers=HEADERS)
    res.raise_for_status()
    return res.json()


def publish_study(study_id):
    res = requests.post(
        f"{BASE_URL}/studies/{study_id}/transition/",
        json={"action": "PUBLISH"},
        headers=HEADERS,
    )
    res.raise_for_status()
    return res.json()


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    if not API_TOKEN or not PROJECT:
        raise RuntimeError(
            "PROLIFIC_TOKEN and PROLIFIC_PROJECT_ID must be set in .env"
        )

    pairs = [(lc, ln, p) for lc, ln in LANGUAGES.items() for p in PARTS]
    if TEST_MODE:
        pairs = pairs[:1]
        print("TEST MODE: creating only the first study")

    print(f"Creating {len(pairs)} studies "
          f"({len(LANGUAGES)} langs × {len(PARTS)} parts)" if not TEST_MODE else "")

    results = []
    for i, (lang_code, lang_name, part) in enumerate(pairs, start=1):
        cc  = completion_code(lang_code, part)
        url = study_url(lang_code, part)
        try:
            draft    = create_draft_study(build_payload(lang_code, lang_name, part))
            study_id = draft["id"]
            publish_study(study_id)
            dashboard = f"https://app.prolific.com/researcher/studies/{study_id}/overview"
            results.append({
                "lang":            lang_code,
                "part":            part,
                "completion_code": cc,
                "study_url":       url,
                "study_id":        study_id,
                "dashboard_url":   dashboard,
                "status":          "published",
            })
            print(f"[{i}/{len(pairs)}] ✓ {lang_code} part {part}  → {study_id}")
            print(f"    {dashboard}")
        except requests.exceptions.HTTPError as e:
            body = e.response.text if e.response is not None else ""
            print(f"[{i}/{len(pairs)}] ✗ {lang_code} part {part}: {e}")
            if body:
                print(f"    Response: {body}")
            results.append({
                "lang":            lang_code,
                "part":            part,
                "completion_code": cc,
                "study_url":       url,
                "study_id":        "",
                "dashboard_url":   "",
                "status":          f"error: {e}",
            })

        time.sleep(DELAY_SECONDS)

    # Write results
    fieldnames = [
        "lang", "part", "completion_code", "study_url",
        "study_id", "dashboard_url", "status",
    ]
    os.makedirs(os.path.dirname(RESULTS_CSV), exist_ok=True)
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nDone. Results written to {RESULTS_CSV}")


if __name__ == "__main__":
    main()
