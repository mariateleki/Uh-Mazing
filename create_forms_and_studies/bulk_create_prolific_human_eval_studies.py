#!/usr/bin/env python3
"""
Create one Prolific draft study per human-eval link.

You will manually paste the external study links into STUDY_LINKS below.
Each created Prolific study is filtered to:
1) first language = target language for that study
2) fluent languages includes English

Run:
python create_forms_and_studies/bulk_create_prolific_human_eval_studies.py
"""

import os
import time

import requests
from dotenv import load_dotenv


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

# Public title shown on Prolific (batch suffix is appended automatically)
STUDY_NAME_PREFIX = "Judging Translation Quality"

# Put your custom study description here (shown on Prolific).
CUSTOM_STUDY_DESCRIPTION = """This study is conducted for research purposes. Data will be collected and analyzed in accordance with our Privacy Policy:

https://docs.google.com/document/d/1WOBUXwyXHHipvtXtm1V0jbvqNZy7rjxUNs_v9LxOVOc/edit?usp=sharing

Participation is voluntary. You may withdraw at any time without penalty. By continuing, you confirm that you have reviewed the Privacy Policy and consent to participate.

Task Overview

This is a data annotation task with two components:
1. Mark disfluent spans
2. Score translations

You will be presented with short text passages that may contain disfluencies or non-standard language (e.g., grammatical errors, hesitations, repetitions, incomplete sentences).

Evaluate each item independently. Spend no more than 5 minutes per item."""

# Optional internal prefix for easier grouping in Prolific.
INTERNAL_NAME_PREFIX = "uhmazing_human_eval"

# Reward is in cents. Update these to match your plan.
REWARD_USD_CENTS = 1200
ESTIMATED_TIME_MIN = 60
TOTAL_PLACES = 1

PROLIFIC_ID_OPTION = "question"
DEVICE_COMPATIBILITY = ["desktop"]
COMPLETION_CODE = "metaphrast"
DELAY_SECONDS = 1
DRY_RUN = False
PROLIFIC_PROJECT_ID_OVERRIDE = "699df160e875cf88bd9ef2a6"

# Verify these filter IDs in create_forms_and_studies/check_prolific_filters.py if needed.
FIRST_LANGUAGE_FILTER_ID = "first-language"
FLUENT_LANGUAGES_FILTER_ID = "fluent-languages"
ENGLISH_CHOICE_ID = "19"

# Put all your external study links here (one per study). Leave blank to skip.
STUDY_LINKS = {
    "uhmazing_v1_ar": {
        "1..20_r0": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_ar&user_id=1..20_r0",
        "1..20_r1": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_ar&user_id=1..20_r1",
        "1..20_r2": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_ar&user_id=1..20_r2",
        "21..41": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_ar&user_id=21..41",
        "41..61": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_ar&user_id=41..61",
        "61..81": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_ar&user_id=61..81",
    },
    "uhmazing_v1_cs": {
        "1..20_r0": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_cs&user_id=1..20_r0",
        "1..20_r1": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_cs&user_id=1..20_r1",
        "1..20_r2": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_cs&user_id=1..20_r2",
        "21..41": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_cs&user_id=21..41",
        "41..61": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_cs&user_id=41..61",
        "61..81": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_cs&user_id=61..81",
    },
    "uhmazing_v1_de": {
        "1..20_r0": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_de&user_id=1..20_r0",
        "1..20_r1": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_de&user_id=1..20_r1",
        "1..20_r2": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_de&user_id=1..20_r2",
        "21..41": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_de&user_id=21..41",
        "41..61": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_de&user_id=41..61",
        "61..81": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_de&user_id=61..81",
    },
    "uhmazing_v1_es": {
        "1..20_r0": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_es&user_id=1..20_r0",
        "1..20_r1": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_es&user_id=1..20_r1",
        "1..20_r2": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_es&user_id=1..20_r2",
        "21..41": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_es&user_id=21..41",
        "41..61": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_es&user_id=41..61",
        "61..81": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_es&user_id=61..81",
    },
    "uhmazing_v1_fr": {
        "1..20_r0": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_fr&user_id=1..20_r0",
        "1..20_r1": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_fr&user_id=1..20_r1",
        "1..20_r2": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_fr&user_id=1..20_r2",
        "21..41": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_fr&user_id=21..41",
        "41..61": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_fr&user_id=41..61",
        "61..81": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_fr&user_id=61..81",
    },
    "uhmazing_v1_hi": {
        "1..20_r0": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_hi&user_id=1..20_r0",
        "1..20_r1": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_hi&user_id=1..20_r1",
        "1..20_r2": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_hi&user_id=1..20_r2",
        "21..41": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_hi&user_id=21..41",
        "41..61": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_hi&user_id=41..61",
        "61..81": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_hi&user_id=61..81",
    },
    "uhmazing_v1_it": {
        "1..20_r0": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_it&user_id=1..20_r0",
        "1..20_r1": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_it&user_id=1..20_r1",
        "1..20_r2": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_it&user_id=1..20_r2",
        "21..41": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_it&user_id=21..41",
        "41..61": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_it&user_id=41..61",
        "61..81": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_it&user_id=61..81",
    },
    "uhmazing_v1_zh": {
        "1..20_r0": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_zh&user_id=1..20_r0",
        "1..20_r1": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_zh&user_id=1..20_r1",
        "1..20_r2": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_zh&user_id=1..20_r2",
        "21..41": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_zh&user_id=21..41",
        "41..61": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_zh&user_id=41..61",
        "61..81": "https://pearmut.ngrok.io/annotate?campaign_id=uhmazing_v1_zh&user_id=61..81",
    },
}


# ---------------------------------------------------------
# LANGUAGE MAPPINGS (Prolific choice IDs)
# ---------------------------------------------------------
# These IDs come from the Prolific language choice list in check_prolific_filters.py.
# If Prolific changes them, refresh with that script and update here.
FIRST_LANGUAGE_CHOICE_IDS = {
    "ar": "3",   # Arabic
    "cs": "11",  # Czech
    "de": "27",  # German
    "es": "59",  # Spanish
    "fr": "24",  # French
    "hi": "30",  # Hindi
    "it": "35",  # Italian
    "zh": "80",  # Mandarin 
}


# ---------------------------------------------------------
# API SETUP
# ---------------------------------------------------------
BASE_URL = "https://api.prolific.com/api/v1"


def make_headers(api_token):
    return {
        "Authorization": f"Token {api_token}",
        "Content-Type": "application/json",
    }


def create_draft_study(api_token, payload):
    response = requests.post(
        f"{BASE_URL}/studies/", json=payload, headers=make_headers(api_token)
    )
    response.raise_for_status()
    return response.json()


def extract_lang_code(group_name):
    return group_name.rsplit("_", 1)[-1].lower()


def build_filters(lang_code):
    if lang_code not in FIRST_LANGUAGE_CHOICE_IDS:
        raise ValueError(f"No first-language mapping for lang_code={lang_code!r}")

    return [
        {
            "filter_id": FIRST_LANGUAGE_FILTER_ID,
            "selected_values": [FIRST_LANGUAGE_CHOICE_IDS[lang_code]],
        },
        {
            "filter_id": FLUENT_LANGUAGES_FILTER_ID,
            "selected_values": [ENGLISH_CHOICE_ID],
        },
    ]


def iter_studies():
    for group_name, batches in STUDY_LINKS.items():
        lang_code = extract_lang_code(group_name)
        for batch_name, url in batches.items():
            yield {
                "group_name": group_name,
                "batch_name": batch_name,
                "lang_code": lang_code,
                "external_study_url": (url or "").strip(),
            }


def main():
    load_dotenv()
    api_token = os.getenv("PROLIFIC_TOKEN")
    project_id = PROLIFIC_PROJECT_ID_OVERRIDE or os.getenv("PROLIFIC_PROJECT_ID")

    if not api_token:
        raise ValueError("Missing PROLIFIC_TOKEN in environment.")
    if not project_id:
        raise ValueError(
            "Missing Prolific project ID. Set PROLIFIC_PROJECT_ID_OVERRIDE or "
            "PROLIFIC_PROJECT_ID in environment."
        )

    if not CUSTOM_STUDY_DESCRIPTION.strip() or "TODO:" in CUSTOM_STUDY_DESCRIPTION:
        raise ValueError("Please set CUSTOM_STUDY_DESCRIPTION before running.")

    results = []

    for i, study in enumerate(iter_studies(), start=1):
        group_name = study["group_name"]
        batch_name = study["batch_name"]
        lang_code = study["lang_code"]
        external_study_url = study["external_study_url"]

        if not external_study_url:
            print(f"[SKIP] {group_name} / {batch_name}: missing external study URL")
            continue

        filters = build_filters(lang_code)
        internal_name = f"{INTERNAL_NAME_PREFIX}__{group_name}__{batch_name}"
        public_name = f"{STUDY_NAME_PREFIX} ({lang_code.upper()}) {batch_name}"

        payload = {
            "name": public_name,
            "internal_name": internal_name,
            "description": CUSTOM_STUDY_DESCRIPTION,
            "external_study_url": external_study_url,
            "project": project_id,
            "prolific_id_option": PROLIFIC_ID_OPTION,
            "total_available_places": TOTAL_PLACES,
            "estimated_completion_time": ESTIMATED_TIME_MIN,
            "reward": REWARD_USD_CENTS,
            "currency": "USD",
            "filters": filters,
            "completion_code": COMPLETION_CODE,
            "device_compatibility": DEVICE_COMPATIBILITY,
        }

        if DRY_RUN:
            print(f"[DRY RUN] {i}: {group_name} / {batch_name}")
            print(f"  -> External URL: {external_study_url}")
            print(f"  -> Payload: {payload}")
            results.append(
                {
                    "group_name": group_name,
                    "batch_name": batch_name,
                    "dry_run": True,
                }
            )
            continue

        try:
            response = create_draft_study(api_token, payload)
            study_id = response["id"]
            dashboard_url = (
                f"https://app.prolific.com/researcher/studies/{study_id}/overview"
            )

            print(f"[Draft Created] {i}: {group_name} / {batch_name}")
            print(f"  -> Study ID: {study_id}")
            print(f"  -> External URL: {external_study_url}")
            print(f"  -> Dashboard: {dashboard_url}")

            results.append(
                {
                    "group_name": group_name,
                    "batch_name": batch_name,
                    "study_id": study_id,
                    "dashboard_url": dashboard_url,
                }
            )
        except requests.exceptions.HTTPError as exc:
            body = exc.response.text if exc.response is not None else ""
            print(f"[ERROR] {group_name} / {batch_name}: {exc}")
            if body:
                print(f"  -> Response body: {body}")
            results.append(
                {
                    "group_name": group_name,
                    "batch_name": batch_name,
                    "error": str(exc),
                    "response_body": body,
                }
            )

        time.sleep(DELAY_SECONDS)

    print("\nDone.")
    print(f"Created/attempted entries recorded: {len(results)}")


if __name__ == "__main__":
    main()
