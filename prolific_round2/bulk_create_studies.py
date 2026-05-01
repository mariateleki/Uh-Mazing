# Run: python prolific_round2/bulk_create_studies.py
#
# Creates one Prolific study per language for the disfluency annotation
# site at docs/annotate.html. By default that's 8 studies — one per
# language, each covering all 80 utterances for that language.
#
# Each study:
#   - filters native speakers of the target language (fluent in English too)
#   - points at https://mariateleki.github.io/Uh-Mazing/annotate.html
#     with ?lang=XX&cc=<unique completion code>
#   - registers that same completion code with Prolific so the participant
#     can return successfully
#   - allocates TOTAL_PLACES_PER_STUDY slots (default 1)
#
# Output: prolific_round2/results.csv  (study IDs + dashboard URLs)
# Required env vars (set in .env at repo root):
#   PROLIFIC_TOKEN

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
# Hard-pinned to the dedicated round-2 disfluency-annotation project.
# Intentionally ignores PROLIFIC_PROJECT_ID env var so this script always
# publishes to the right place even if .env points elsewhere.
PROJECT   = "69f2eaa7c3cb0d7c7a476d8b"
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

TOTAL_PLACES_PER_STUDY = 1   # how many distinct workers per language

# Reward / time. Bumped to $20 for 60 min (~$20/hr) to attract more
# qualified annotators given the niche language requirements.
ESTIMATED_TIME_MIN  = 105   # 90–120 minute window; we display this median
REWARD_USD_CENTS    = 2000   # $20.00 per submission
MIN_COMPLETION_TIME = 15     # auto-reject submissions faster than 15 min

DEVICE_COMPATIBILITY = ["desktop"]
# annotate.html collects the Prolific ID via the intake form, so use
# "question" mode (no PROLIFIC_PID placeholder needed in the URL).
PROLIFIC_ID_OPTION   = "question"
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

STUDY_TITLE_TEMPLATE = "Disfluency Annotation — {lang_name}"
STUDY_DESCRIPTION_TEMPLATE = """You will look at short English utterances paired with their {lang_name} translations and highlight which words in the translation correspond to the disfluencies (filler words, repetitions, false starts) marked in the English. If a translation is missing words or contains errors, you can edit it.

You'll annotate 80 utterances total. This study should take approximately 90–120 minutes.

Native {lang_name} speakers only. The site asks you to read and accept a short privacy policy before you start."""


def completion_code(lang_code):
    """Stable per-language code, used both in the URL and registered with
    Prolific as the COMPLETED code."""
    return f"UM-{lang_code}"


def study_url(lang_code):
    cc = completion_code(lang_code)
    qs = urlencode({"lang": lang_code, "cc": cc})
    # No PROLIFIC_PID placeholder needed — the worker enters their ID via
    # the intake form on annotate.html (PROLIFIC_ID_OPTION = "question").
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


def build_payload(lang_code, lang_name):
    cc = completion_code(lang_code)
    return {
        "name":           STUDY_TITLE_TEMPLATE.format(lang_name=lang_name),
        "internal_name":  f"uh-mazing_round2_disfluency_{lang_code.lower()}",
        "description":    STUDY_DESCRIPTION_TEMPLATE.format(lang_name=lang_name),
        "external_study_url":        study_url(lang_code),
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
    if not API_TOKEN:
        raise RuntimeError("PROLIFIC_TOKEN must be set in .env")
    if not PROJECT:
        raise RuntimeError(
            "PROLIFIC_PROJECT_ID is unset and no default project hardcoded"
        )
    print(f"Using Prolific project {PROJECT}")

    pairs = list(LANGUAGES.items())
    if TEST_MODE:
        pairs = pairs[:1]
        print("TEST MODE: creating only the first study")
    else:
        print(f"Creating {len(pairs)} studies (1 per language)")

    results = []
    for i, (lang_code, lang_name) in enumerate(pairs, start=1):
        cc  = completion_code(lang_code)
        url = study_url(lang_code)
        try:
            draft    = create_draft_study(build_payload(lang_code, lang_name))
            study_id = draft["id"]
            publish_study(study_id)
            dashboard = f"https://app.prolific.com/researcher/studies/{study_id}/overview"
            results.append({
                "lang":            lang_code,
                "completion_code": cc,
                "study_url":       url,
                "study_id":        study_id,
                "dashboard_url":   dashboard,
                "status":          "published",
            })
            print(f"[{i}/{len(pairs)}] ✓ {lang_code}  → {study_id}")
            print(f"    {dashboard}")
        except requests.exceptions.HTTPError as e:
            body = e.response.text if e.response is not None else ""
            print(f"[{i}/{len(pairs)}] ✗ {lang_code}: {e}")
            if body:
                print(f"    Response: {body}")
            results.append({
                "lang":            lang_code,
                "completion_code": cc,
                "study_url":       url,
                "study_id":        "",
                "dashboard_url":   "",
                "status":          f"error: {e}",
            })

        time.sleep(DELAY_SECONDS)

    # Write results
    fieldnames = [
        "lang", "completion_code", "study_url",
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
