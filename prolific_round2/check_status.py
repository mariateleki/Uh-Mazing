# Run: python prolific_round2/check_status.py
#
# Queries Prolific's API for the status of every study in
# prolific_round2/results.csv (and optionally prolific/results.csv) and
# prints which are "done" (all places filled with approved submissions).
#
# Output columns:
#   lang/part - identifier (or user_id for legacy round 1)
#   places_taken / total_available_places - capacity status
#   submissions - count breakdown (submitted, approved, returned, ...)
#   status - Prolific's lifecycle (PUBLISHED, AWAITING_REVIEW, COMPLETED, etc.)
#   done? - True if no places remain AND submissions look healthy

import csv
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv("PROLIFIC_TOKEN")
BASE_URL  = "https://api.prolific.com/api/v1"

ROUND2_RESULTS = "prolific_round2/results.csv"
ROUND1_RESULTS = "prolific/results.csv"

HEADERS = {
    "Authorization": f"Token {API_TOKEN}",
    "Content-Type":  "application/json",
}


def fetch_study(study_id):
    if not study_id:
        return None
    r = requests.get(f"{BASE_URL}/studies/{study_id}/", headers=HEADERS)
    if r.status_code == 404:
        return {"_missing": True}
    r.raise_for_status()
    return r.json()


def fetch_submissions(study_id):
    """Returns dict like {submitted: 1, approved: 0, returned: 2, ...}."""
    if not study_id:
        return {}
    counts = {}
    page_url = f"{BASE_URL}/studies/{study_id}/submissions/?limit=100"
    while page_url:
        r = requests.get(page_url, headers=HEADERS)
        if r.status_code == 404:
            return counts
        r.raise_for_status()
        body = r.json()
        for sub in body.get("results", []):
            st = sub.get("status", "UNKNOWN").lower()
            counts[st] = counts.get(st, 0) + 1
        page_url = body.get("_links", {}).get("next", {}).get("href")
    return counts


def is_done(study, subs):
    if not study or study.get("_missing"):
        return False
    total   = study.get("total_available_places") or 0
    if total == 0:
        return False
    # "Done" = no places remaining AND we have at least one approved/awaiting submission
    places_taken = study.get("places_taken")
    if places_taken is None:
        # Older studies don't expose places_taken; fall back to subs count
        places_taken = sum(v for k, v in subs.items() if k in ("approved", "awaiting review"))
    healthy_subs = sum(v for k, v in subs.items()
                       if k in ("approved", "awaiting review", "completed"))
    return places_taken >= total and healthy_subs >= total


def fmt_subs(subs):
    if not subs:
        return "(no subs)"
    return ", ".join(f"{k}={v}" for k, v in sorted(subs.items()))


def report(rows, label_fn):
    """Generic reporter. label_fn(row) → str for the leading column."""
    fmt = "{:<14} {:<24} {:>10} {:>20} {:<35} {}"
    print(fmt.format("study", "study_id", "places", "status", "submissions", "done?"))
    print("-" * 130)
    done_count = 0
    for row in rows:
        sid = row.get("study_id", "").strip()
        if not sid:
            print(fmt.format(label_fn(row), "(no study)", "-", "-", row.get("status", ""), ""))
            continue
        try:
            study = fetch_study(sid)
            subs  = fetch_submissions(sid)
        except requests.exceptions.HTTPError as e:
            print(fmt.format(label_fn(row), sid[:24], "-", "-", f"error: {e}", ""))
            continue
        if not study or study.get("_missing"):
            print(fmt.format(label_fn(row), sid[:24], "-", "-", "404 (deleted?)", ""))
            continue
        total = study.get("total_available_places", "?")
        taken = study.get("places_taken", "?")
        st    = study.get("status", "?")
        done  = is_done(study, subs)
        if done:
            done_count += 1
        print(fmt.format(
            label_fn(row),
            sid[:24],
            f"{taken}/{total}",
            st,
            fmt_subs(subs),
            "✓ DONE" if done else "",
        ))
    return done_count


def main():
    if not API_TOKEN:
        sys.exit("PROLIFIC_TOKEN must be set in .env")

    print(f"=== Round 2 ($20 studies, 8 langs) ===\n")
    if os.path.exists(ROUND2_RESULTS):
        with open(ROUND2_RESULTS) as f:
            r2 = list(csv.DictReader(f))
        done2 = report(r2, lambda r: r.get("lang", "?"))
        print(f"\nRound 2 done: {done2}/{len(r2)}")
    else:
        print(f"  ({ROUND2_RESULTS} not found)")

    print(f"\n=== Round 1 ($5 studies, per-annotator) ===\n")
    if os.path.exists(ROUND1_RESULTS):
        with open(ROUND1_RESULTS) as f:
            r1 = list(csv.DictReader(f))
        done1 = report(r1, lambda r: r.get("user_id", "?")[:14])
        print(f"\nRound 1 done: {done1}/{len(r1)}")
    else:
        print(f"  ({ROUND1_RESULTS} not found)")


if __name__ == "__main__":
    main()
