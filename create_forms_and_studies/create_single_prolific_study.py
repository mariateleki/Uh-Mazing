#!/usr/bin/env python3
"""
Create a single Prolific draft study with a custom completion code.

Example:
python create_forms_and_studies/create_single_prolific_study.py \
  --name "Translation Task" \
  --internal-name "sw_uid_001" \
  --description "Please complete the external form." \
  --external-study-url "https://forms.gle/your-form-id" \
  --completion-code "MYCUSTOMCODE123"
"""

import argparse
import json
import os

import requests
from dotenv import load_dotenv


BASE_URL = "https://api.prolific.com/api/v1"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create one Prolific draft study with a custom completion code."
    )
    parser.add_argument("--name", required=True, help="Public study name.")
    parser.add_argument(
        "--internal-name", required=True, help="Internal reference for the study."
    )
    parser.add_argument("--description", required=True, help="Study description text.")
    parser.add_argument(
        "--external-study-url",
        required=True,
        help="External survey URL shown to participants.",
    )
    parser.add_argument(
        "--completion-code",
        required=True,
        help="Completion code participants submit when done.",
    )
    parser.add_argument(
        "--total-available-places",
        type=int,
        default=1,
        help="Number of participants (default: 1).",
    )
    parser.add_argument(
        "--estimated-completion-time",
        type=int,
        default=60,
        help="Estimated completion time in minutes (default: 60).",
    )
    parser.add_argument(
        "--reward",
        type=int,
        default=1200,
        help="Reward in cents (default: 1200).",
    )
    parser.add_argument(
        "--currency",
        default="USD",
        help="Reward currency (default: USD).",
    )
    parser.add_argument(
        "--prolific-id-option",
        default="question",
        help="Prolific ID option (default: question).",
    )
    parser.add_argument(
        "--device-compatibility",
        nargs="+",
        default=["desktop", "tablet", "mobile"],
        help="Allowed devices (default: desktop tablet mobile).",
    )
    parser.add_argument(
        "--filters-json",
        default="[]",
        help="Raw JSON list for Prolific filters (default: []).",
    )
    return parser.parse_args()


def create_draft_study(api_token, payload):
    headers = {
        "Authorization": f"Token {api_token}",
        "Content-Type": "application/json",
    }
    response = requests.post(f"{BASE_URL}/studies/", headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


def main():
    load_dotenv()
    api_token = os.getenv("PROLIFIC_TOKEN")
    project_id = os.getenv("PROLIFIC_PROJECT_ID")

    if not api_token:
        raise ValueError("Missing PROLIFIC_TOKEN in environment.")
    if not project_id:
        raise ValueError("Missing PROLIFIC_PROJECT_ID in environment.")

    args = parse_args()

    try:
        filters = json.loads(args.filters_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid --filters-json value: {exc}") from exc

    if not isinstance(filters, list):
        raise ValueError("--filters-json must decode to a JSON list.")

    payload = {
        "name": args.name,
        "internal_name": args.internal_name,
        "description": args.description,
        "external_study_url": args.external_study_url,
        "project": project_id,
        "prolific_id_option": args.prolific_id_option,
        "total_available_places": args.total_available_places,
        "estimated_completion_time": args.estimated_completion_time,
        "reward": args.reward,
        "currency": args.currency,
        "filters": filters,
        "completion_code": args.completion_code,
        "device_compatibility": args.device_compatibility,
    }

    result = create_draft_study(api_token, payload)
    study_id = result["id"]
    dashboard_url = f"https://app.prolific.com/researcher/studies/{study_id}/overview"

    print("[Draft Created]")
    print(f"Study ID: {study_id}")
    print(f"Dashboard: {dashboard_url}")
    print(f"External URL: {args.external_study_url}")
    print(f"Completion code: {args.completion_code}")


if __name__ == "__main__":
    main()
