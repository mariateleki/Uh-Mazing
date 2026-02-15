# python ./create_forms_and_studies/bulk_merge_google_forms.py

import csv
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import pandas as pd

SCOPES = [
    "https://www.googleapis.com/auth/forms.body.readonly",
    "https://www.googleapis.com/auth/forms.responses.readonly",
    "https://www.googleapis.com/auth/spreadsheets"
]

BATCH_SIZE = 5000 


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
            "./create_forms_and_studies/credentials.json",
            SCOPES
        )
        creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())

    return creds


# ------------------------------------------------------------
# LOAD FORMS LIST
# ------------------------------------------------------------
def load_forms(path="./data/google_forms.txt"):
    forms = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="|")
        for row in reader:
            UID, _, form_id, *_ = [x.strip() for x in row]
            forms.append((UID, form_id))
    return forms


# ------------------------------------------------------------
# FETCH + NORMALIZE RESPONSES
# ------------------------------------------------------------
def build_question_order_and_map(form):
    order = []
    qmap = {}

    for item in form.get("items", []):
        qi = item.get("questionItem")
        if not qi:
            continue

        question = qi["question"]
        qid = question["questionId"]
        title = item.get("title", "")

        order.append(qid)
        qmap[qid] = title

    return order, qmap


def extract_answer(answer_obj):
    if "textAnswers" in answer_obj:
        return " | ".join(a["value"] for a in answer_obj["textAnswers"]["answers"])
    if "choiceAnswers" in answer_obj:
        return " | ".join(answer_obj["choiceAnswers"]["values"])
    if "scaleAnswers" in answer_obj:
        return str(answer_obj["scaleAnswers"]["value"])
    if "dateAnswers" in answer_obj:
        return str(answer_obj["dateAnswers"]["value"])
    if "timeAnswers" in answer_obj:
        return str(answer_obj["timeAnswers"]["value"])
    if "fileUploadAnswers" in answer_obj:
        return " | ".join(f["fileId"] for f in answer_obj["fileUploadAnswers"]["answers"])
    return "UNKNOWN_ANSWER_TYPE"


def extract_rows(forms_service, UID, form_id):
    rows = []

    form = forms_service.forms().get(formId=form_id).execute()
    question_order, question_map = build_question_order_and_map(form)

    responses = forms_service.forms().responses().list(
        formId=form_id
    ).execute().get("responses", [])

    for r in responses:
        ts = r["lastSubmittedTime"]
        rid = r["responseId"]
        answers = r.get("answers", {})

        for qid in question_order:
            if qid not in answers:
                continue

            rows.append([
                UID,
                form_id,
                rid,
                ts,
                question_map.get(qid, "UNKNOWN_QUESTION"),
                extract_answer(answers[qid])
            ])

    return rows


# ------------------------------------------------------------
# APPEND IN BATCHES
# ------------------------------------------------------------
def append_rows_batched(sheets_service, rows):
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        sheets_service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": batch}
        ).execute()
        print(f"        → appended {len(batch)} rows")

# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
if __name__ == "__main__":

    creds = authorize()
    forms_service = build("forms", "v1", credentials=creds)

    forms = load_forms()
    print(forms)

    HEADERS = ["UID", "formId", "responseId", "timestamp", "question", "answer"]

    all_rows = []

    for UID, form_id in forms:
        print(f"[FETCH] {UID} | {form_id}")
        rows = extract_rows(forms_service, UID, form_id)
        all_rows.extend(rows)
        print(f"        → collected {len(rows)} rows")

    # LOAD INTO DATAFRAME
    df = pd.DataFrame(all_rows, columns=HEADERS)

    # SAVE LOCALLY 
    df.to_csv("./data/prolific_responses_raw.csv", index=False)

    print(f"\nDONE — {len(df)} rows saved locally.")

