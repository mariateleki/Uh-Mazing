# python ./create_forms_and_studies/merge_filtered_annotators.py
#
# Fetches Google Forms responses and outputs ONE submission per form,
# keeping only the annotator specified in annotator_keep.csv.
#
# annotator_keep.csv rules per cell (T1–T4):
#   <prolific_id>              → keep the response whose Prolific ID answer matches
#   BLANK                      → keep the response with an empty-string Prolific ID
#   NONE                       → skip this form entirely
#   <id> / <timestamp>         → keep the response matching that ID AND closest to that timestamp
#   INCOMPLETE / <id>          → keep the response matching that ID (treat as normal)
#
# Output: data/prolific_responses_filtered.csv
#   columns: UID, formId, responseId, timestamp, question, answer
#   (same schema as bulk_merge_google_forms.py output)

import csv
import re
from datetime import datetime, timezone

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/forms.body.readonly",
    "https://www.googleapis.com/auth/forms.responses.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

ANNOTATOR_KEEP  = "./create_forms_and_studies/annotator_keep.csv"
FORMS_LIST      = "./data/google_forms.txt"
OUTPUT_CSV      = "./data/prolific_responses_filtered.csv"
PROLIFIC_Q_KEY  = "Prolific ID"   # substring matched against question text

# Only pull forms that live in this Google Drive folder.
DRIVE_FOLDER_ID = "1Vkl62xtVm062bUBglPsXux-uXWb_2uQb"

# Only consider responses submitted on or after this date.
# Filters out the January 2026 pilot batch.
MIN_DATE = datetime(2026, 3, 1, tzinfo=timezone.utc)

# annotator_keep uses "CZ" for Czech; forms use "CS"
LANG_REMAP = {"CZ": "CS"}


# ------------------------------------------------------------
# AUTH
# ------------------------------------------------------------
def authorize():
    try:
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    except Exception:
        creds = None
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            "./create_forms_and_studies/credentials.json", SCOPES
        )
        creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return creds


# ------------------------------------------------------------
# PARSE annotator_keep.csv → {uid: rule}
# rule is one of:
#   ("plain",      prolific_id)
#   ("blank",      None)
#   ("none",       None)
#   ("timestamp",  prolific_id, datetime)
#   ("incomplete", prolific_id)
# ------------------------------------------------------------
def parse_keep(path):
    rules = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lang = row["language_code"].strip()
            lang = LANG_REMAP.get(lang, lang)
            for t in ["T1", "T2", "T3", "T4"]:
                cell = row.get(t, "").strip()
                uid  = f"{lang}_{t}"
                if not cell or cell.upper() == "NONE":
                    rules[uid] = ("none", None)
                elif cell.upper() == "BLANK":
                    rules[uid] = ("blank", None)
                elif "/" in cell:
                    # Could be  "INCOMPLETE / <id>"  or  "<id> / <timestamp>"
                    parts = [p.strip() for p in cell.split("/", 1)]
                    if parts[0].upper() == "INCOMPLETE":
                        rules[uid] = ("incomplete", parts[1].strip())
                    else:
                        # "<id> / M/D/YYYY HH:MM:SS"  — re-join because date has slashes
                        pid, rest = cell.split(" / ", 1)
                        ts = datetime.strptime(rest.strip(), "%m/%d/%Y %H:%M:%S")
                        ts = ts.replace(tzinfo=timezone.utc)
                        rules[uid] = ("timestamp", pid.strip(), ts)
                else:
                    rules[uid] = ("plain", cell)
    return rules


# ------------------------------------------------------------
# LOAD FORMS LIST → {uid: form_id}, filtered to DRIVE_FOLDER_ID
# ------------------------------------------------------------
def get_folder_form_ids(drive_svc, folder_id):
    """Return set of file IDs for Google Forms inside the given Drive folder."""
    form_ids = set()
    page_token = None
    query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.form' and trashed=false"
    while True:
        resp = drive_svc.files().list(
            q=query,
            fields="nextPageToken, files(id, name)",
            pageToken=page_token,
        ).execute()
        for f in resp.get("files", []):
            form_ids.add(f["id"])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return form_ids


def load_forms(path, allowed_form_ids):
    """Read google_forms.txt and keep only forms whose ID is in allowed_form_ids."""
    forms = {}
    skipped = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="|")
        for row in reader:
            uid, _, form_id, *_ = [x.strip() for x in row]
            if form_id in allowed_form_ids:
                forms[uid] = form_id
            else:
                skipped.append(uid)
    if skipped:
        print(f"[FOLDER FILTER] Excluded {len(skipped)} form(s) not in Drive folder: {skipped}")
    return forms


# ------------------------------------------------------------
# FETCH responses for one form, return list of response dicts
# Each dict: {responseId, timestamp (datetime), prolific_id, rows[]}
# rows = [[UID, formId, responseId, ts_str, question, answer], ...]
# ------------------------------------------------------------
def extract_answer(answer_obj):
    if "textAnswers"  in answer_obj:
        return " | ".join(a["value"] for a in answer_obj["textAnswers"]["answers"])
    if "choiceAnswers" in answer_obj:
        return " | ".join(answer_obj["choiceAnswers"]["values"])
    if "scaleAnswers"  in answer_obj:
        return str(answer_obj["scaleAnswers"]["value"])
    return "UNKNOWN_ANSWER_TYPE"


def fetch_responses(svc, uid, form_id):
    form      = svc.forms().get(formId=form_id).execute()
    q_order   = []
    q_map     = {}
    for item in form.get("items", []):
        qi = item.get("questionItem")
        if not qi:
            continue
        q  = qi["question"]
        qid = q["questionId"]
        q_order.append(qid)
        q_map[qid] = item.get("title", "")

    raw = svc.forms().responses().list(formId=form_id).execute().get("responses", [])

    results = []
    for r in raw:
        ts_str  = r["lastSubmittedTime"]
        rid     = r["responseId"]
        answers = r.get("answers", {})

        # Find the Prolific ID answer
        prolific_id = ""
        for qid, title in q_map.items():
            if PROLIFIC_Q_KEY in title and qid in answers:
                prolific_id = extract_answer(answers[qid]).strip()
                break

        ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

        if ts_dt < MIN_DATE:
            continue  # skip January pilot responses

        rows = []
        for qid in q_order:
            if qid not in answers:
                continue
            rows.append([uid, form_id, rid, ts_str, q_map[qid], extract_answer(answers[qid])])

        results.append({
            "responseId":  rid,
            "timestamp":   ts_dt,
            "prolific_id": prolific_id,
            "rows":        rows,
        })
    return results


# ------------------------------------------------------------
# APPLY RULE → select the right response (or None)
# ------------------------------------------------------------
def select_response(responses, rule):
    kind = rule[0]

    if kind == "none":
        return None

    if kind == "blank":
        for r in responses:
            if r["prolific_id"] == "":
                return r
        print("    WARNING: no blank-prolific-ID response found")
        return None

    if kind in ("plain", "incomplete"):
        target = rule[1]
        for r in responses:
            if r["prolific_id"] == target:
                return r
        print(f"    WARNING: prolific ID {target!r} not found in responses")
        return None

    if kind == "timestamp":
        target_id, target_ts = rule[1], rule[2]
        # Filter to matching prolific ID first
        candidates = [r for r in responses if r["prolific_id"] == target_id]
        if not candidates:
            print(f"    WARNING: prolific ID {target_id!r} not found")
            return None
        # Pick closest timestamp
        best = min(candidates, key=lambda r: abs((r["timestamp"] - target_ts).total_seconds()))
        diff = abs((best["timestamp"] - target_ts).total_seconds())
        if diff > 300:
            print(f"    WARNING: closest match is {diff:.0f}s away from target timestamp")
        return best

    raise ValueError(f"Unknown rule kind: {kind}")


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
if __name__ == "__main__":
    creds = authorize()
    svc        = build("forms", "v1", credentials=creds)
    drive_svc  = build("drive", "v3", credentials=creds)

    print(f"[DRIVE] Listing forms in folder {DRIVE_FOLDER_ID} ...")
    allowed_ids = get_folder_form_ids(drive_svc, DRIVE_FOLDER_ID)
    print(f"[DRIVE] Found {len(allowed_ids)} form(s) in folder")

    rules = parse_keep(ANNOTATOR_KEEP)
    forms = load_forms(FORMS_LIST, allowed_ids)

    headers   = ["UID", "formId", "responseId", "timestamp", "question", "answer"]
    all_rows  = []
    kept       = 0
    skipped    = 0

    for uid in sorted(forms):
        rule = rules.get(uid)
        if rule is None:
            print(f"[SKIP] {uid} — not in annotator_keep.csv")
            skipped += 1
            continue

        if rule[0] == "none":
            print(f"[NONE] {uid} — skipped per annotator_keep.csv")
            skipped += 1
            continue

        form_id = forms[uid]
        print(f"[FETCH] {uid} | {form_id}")
        responses = fetch_responses(svc, uid, form_id)
        print(f"        {len(responses)} response(s) found")

        chosen = select_response(responses, rule)
        if chosen is None:
            print(f"        → no matching response selected")
            skipped += 1
            continue

        print(f"        → keeping {chosen['prolific_id']!r} @ {chosen['timestamp'].isoformat()}")
        all_rows.extend(chosen["rows"])
        kept += 1

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(all_rows)

    print(f"\nDONE — {kept} forms kept, {skipped} skipped → {len(all_rows)} rows → {OUTPUT_CSV}")
