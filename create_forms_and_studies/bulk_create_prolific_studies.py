# python create_forms_and_studies/bulk_create_prolific_studies.py

import requests
import time
import os
from dotenv import load_dotenv

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
load_dotenv()
API_TOKEN = os.getenv("PROLIFIC_TOKEN")
BASE_URL = "https://api.prolific.com/api/v1"

# ---------------------------------------------------------
# 1. LANGUAGE → PROLIFIC FILTER MAPPING
# (IDs come from Prolific "Fluent Languages" filter)
# see check_prolific_filters.py
# ---------------------------------------------------------

LANGUAGE_FILTER_IDS = {
    # "EN": "19", # English (source)
    "ZH": "81", # Mandarin
    "ES": "60", # Spanish
    "HI": "31", # Hindi
    "FR": "25", # French
    "DE": "28", # German
    "IT": "36", # Italian
    # "SW": "Swahili", # handled by collaborators :) 
    "CS": "12", # Czech
    "AR": "04", # Arabic
    # "LG": "Luganda", # handled by collaborators :) 
}

# ---------------------------------------------------------
# 2. LOAD FORM URL + INTRO + LANGUAGE
# ---------------------------------------------------------
def load_form_pairs(filename="./data/google_forms.txt"):
    pairs = []

    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 5:
                raise ValueError(f"Invalid line format: {line}")

            uid, lang_code, form_id, url, intro_string = parts
            intro_string = intro_string.replace("\\n", "\n")

            pairs.append({
                "uid": uid,
                "language_code": lang_code,
                "form_id": form_id,
                "url": url,
                "intro": intro_string
            })

    return pairs


form_entries = load_form_pairs()
print(f"Loaded {len(form_entries)} form entries.")

# ---------------------------------------------------------
# 3. STUDY PARAMETERS
# ---------------------------------------------------------
REWARD_USD_CENTS = 1200 # comes out to 12 USD/hr
ESTIMATED_TIME_MIN = 60
TOTAL_PLACES = 1
PROJECT = os.getenv("PROLIFIC_PROJECT_ID")
PROLIFIC_ID_OPTION = "question"
DEVICE_COMPATIBILITY = ["desktop", "tablet", "mobile"]
COMPLETION_CODE = "COMPLETED021384"
DELAY_SECONDS = 1

BASE_FILTERS = [
    # {
    #     "filter_id": "current-country-of-residence",
    #     "selected_values": ["1"]  # United States
    # }
]

# ---------------------------------------------------------
# 4. API HEADERS
# ---------------------------------------------------------
headers = {
    "Authorization": f"Token {API_TOKEN}",
    "Content-Type": "application/json"
}

# ---------------------------------------------------------
# 5. CREATE DRAFT STUDY
# ---------------------------------------------------------
def create_draft_study(payload):
    url = f"{BASE_URL}/studies/"
    res = requests.post(url, json=payload, headers=headers)
    res.raise_for_status()
    return res.json()

# ---------------------------------------------------------
# 6. CREATE ONE STUDY PER FORM (considering language)
# More info here: https://docs.prolific.com/api-reference/studies/create-study 
# ---------------------------------------------------------
results = []

for i, entry in enumerate(form_entries, start=1):
    lang_code = entry["language_code"]

    if lang_code not in LANGUAGE_FILTER_IDS:
        raise ValueError(f"No fluent-language filter defined for {lang_code}")

    fluent_language_filter = {
        "filter_id": "fluent-languages",
        "selected_values": ["19", LANGUAGE_FILTER_IDS[lang_code]] # "19" is for English
    }

    filters = BASE_FILTERS + [fluent_language_filter]

    study_payload = {
        "name": "Translation Task (Disfluent Text)",
        "internal_name": entry["uid"],
        "description": entry["intro"],
        "external_study_url": entry["url"],
        "project": PROJECT,
        "prolific_id_option": PROLIFIC_ID_OPTION,
        "total_available_places": TOTAL_PLACES,
        "estimated_completion_time": ESTIMATED_TIME_MIN,
        "reward": REWARD_USD_CENTS,
        "currency": "USD",
        "filters": filters,
        "completion_code": COMPLETION_CODE,
        "device_compatibility": DEVICE_COMPATIBILITY
    }

    try:
        response = create_draft_study(study_payload)
        study_id = response["id"]

        dashboard_url = (
            f"https://app.prolific.com/researcher/studies/"
            f"{study_id}/overview"
        )

        results.append({
            "study_number": i,
            "uid": entry["uid"],
            "language_code": lang_code,
            "study_id": study_id,
            "survey_url": entry["url"],
            "dashboard_url": dashboard_url
        })

        print(f"[Draft Created] {entry['uid']} ({lang_code})")
        print(f"  → Study ID: {study_id}")
        print(f"  → Survey: {entry['url']}")
        print(f"  → Dashboard: {dashboard_url}")

    except requests.exceptions.HTTPError as e:
        response_text = e.response.text if e.response else ""
        print(f"[ERROR] {entry['uid']}: {e}")
        if response_text:
            print(f"  → Response body: {response_text}")

        results.append({
            "study_number": i,
            "uid": entry["uid"],
            "language_code": lang_code,
            "error": str(e),
            "response_body": response_text
        })

    time.sleep(DELAY_SECONDS)

print("\nAll draft studies created.")
