# python ./create_forms_and_studies/bulk_create_google_forms.py

import json
import pandas as pd
import os
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ------------------------------------------------------------
# 1. AUTHENTICATION
# ------------------------------------------------------------
load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/drive"
]


def authorize():
    creds = None
    try:
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    except Exception:
        pass

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            "./create_forms_and_studies/credentials.json",
            SCOPES
        )
        creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds


# ------------------------------------------------------------
# 2. GOOGLE FORMS HELPERS
# ------------------------------------------------------------

def create_form(forms_service, title):
    result = forms_service.forms().create(
        body={"info": {"title": title}}
    ).execute()
    return result["formId"]


def set_description(forms_service, form_id, description_text):
    forms_service.forms().batchUpdate(
        formId=form_id,
        body={
            "requests": [
                {
                    "updateFormInfo": {
                        "info": {"description": description_text},
                        "updateMask": "description"
                    }
                }
            ]
        }
    ).execute()


def add_items(forms_service, form_id, items):
    requests = []
    for idx, item in enumerate(items):
        requests.append({
            "createItem": {
                "item": item,
                "location": {"index": idx}
            }
        })

    forms_service.forms().batchUpdate(
        formId=form_id,
        body={"requests": requests}
    ).execute()


def move_to_folder(drive_service, file_id, folder_id):
    file = drive_service.files().get(
        fileId=file_id,
        fields="parents"
    ).execute()

    prev_parents = ",".join(file.get("parents", []))

    drive_service.files().update(
        fileId=file_id,
        addParents=folder_id,
        removeParents=prev_parents,
        fields="id, parents"
    ).execute()


# ------------------------------------------------------------
# 3. LOAD BASE FORM TEMPLATE
# ------------------------------------------------------------

def load_base_form(json_path="./create_forms_and_studies/base_form.json"):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------
# 4. LANGUAGE CONFIGURATION
# ------------------------------------------------------------

LANGUAGES = {
    # "EN": "English",
    "ZH": "Mandarin",
    "ES": "Spanish",
    "HI": "Hindi",
    "FR": "French",
    "DE": "German",
    "IT": "Italian",
    "CS": "Czech",
    "AR": "Arabic"
}


# ------------------------------------------------------------
# 5. TRANSLATION ITEM BUILDER
# ------------------------------------------------------------

def make_translation_item(disfluent_text, item_number, target_language, ID):
    return {
        "title": f"[{ID}] Translation {item_number}",
        "description": (
            f"Translate the following text into {target_language}:\n"
            f"{disfluent_text}"
        ),
        "questionItem": {
            "question": {
                "required": True,
                "textQuestion": {
                    "paragraph": True
                }
            }
        }
    }


# ------------------------------------------------------------
# 6. BULK CREATION PIPELINE
# ------------------------------------------------------------

def bulk_create(
    forms_service,
    drive_service=None,
    folder_id=None,
    items_per_form=20
):
    results = []
    item_mappings = []

    base_form = load_base_form()
    df = pd.read_csv("./data/translation-dataset-with-timestamps.csv")

    # CHUNK DATASET
    chunks = [
        df.iloc[i:i + items_per_form]
        for i in range(0, len(df), items_per_form)
    ]

    for lang_code, lang_name in LANGUAGES.items():
        print(f"\n=== Creating forms for {lang_name} ({lang_code}) ===")

        for form_idx, chunk in enumerate(chunks, start=1):
            UID = f"{lang_code}_T{form_idx}"
            title = f"Translation Task – {lang_name} (Part {form_idx})"

            google_description = (
                base_form["description"]["google"]
                .replace("[TARGET_LANGUAGE]", lang_name)
            )

            prolific_description = (
                base_form["description"]["prolific"]
                .replace("[TARGET_LANGUAGE]", lang_name)
            )

            items = []
            items.append({
            "title": "Provide your Prolific ID in the box below.",
            "questionItem": {
                "question": {
                "required": False,
                "textQuestion": {}
                }
            }
            })

            for q_num, (row_idx, row) in enumerate(chunk.iterrows(), start=1):
                
                # extract ID info
                conv_raw = row["file"]          # "sw2005" or possibly "2005"
                conv_num = int(conv_raw.replace("sw", ""))
                conv = f"sw{conv_num:05d}"      # -> "sw02005"
                ID = f"{conv}_{row['speaker']}_{row['turn']}"

                items.append(
                    make_translation_item(
                        row["text_disfluent"],
                        q_num,
                        lang_name,
                        ID
                    )
                )

                item_mappings.append({
                    "language_code": lang_code,
                    "language_name": lang_name,
                    "form_uid": UID,
                    "form_id": None,  # filled later
                    "form_part": form_idx,
                    "question_number": q_num,
                    "source_row_index": int(row_idx),
                    "source_id": ID
                })
            
            items.append({
                "title": f"Completion Code",
                "description": (
                    f"Paste the following completion code when you return to Prolific: COMPLETED021384. Thanks!\n"
                ),
                "questionItem": {
                    "question": {
                        "required": False,
                        "textQuestion": {
                            "paragraph": True
                        }
                    }
                }
            })

            # CREATE FORM
            form_id = create_form(forms_service, title)
            set_description(forms_service, form_id, google_description)
            add_items(forms_service, form_id, items)

            participant_url = f"https://docs.google.com/forms/d/{form_id}/viewform"

            # UPDATE FORM ID IN MAPPINGS
            for m in item_mappings:
                if m["form_uid"] == UID and m["form_id"] is None:
                    m["form_id"] = form_id

            results.append(
                (form_id, UID, lang_code, participant_url, prolific_description)
            )

            print(f"[OK] {UID} | {form_id}")

            if folder_id:
                move_to_folder(drive_service, form_id, folder_id)

    return results, item_mappings


# ------------------------------------------------------------
# 7. MAIN ENTRY POINT
# ------------------------------------------------------------

if __name__ == "__main__":
    creds = authorize()
    forms_service = build("forms", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")

    results, item_mappings = bulk_create(
        forms_service,
        drive_service,
        DRIVE_FOLDER_ID,
        items_per_form=20
    )

    print("\nDONE — Forms Created\n")

    # SAVE PROLIFIC / FORM LINKS
    with open("./data/google_forms.txt", "w", encoding="utf-8") as f:
        for form_id, UID, lang_code, participant_url, description in results:
            safe_description = description.replace("\n", "\\n")
            line = (
                f"{UID} | {lang_code} | {form_id} | "
                f"{participant_url} | {safe_description}\n"
            )
            print(line.strip())
            f.write(line)

    # SAVE FORM–QUESTION–ROW MAPPING
    mapping_df = pd.DataFrame(item_mappings)
    mapping_df.to_csv(
        "./data/form_item_mapping.csv",
        index=False,
        encoding="utf-8"
    )

    print("\nSaved google_forms.txt")
    print("Saved form_item_mapping.csv\n")
