# python ./create_forms_and_studies/finalize_dataset.py

import pandas as pd
import re

# ------------------------------------------------------------
# 1. LOAD & NORMALIZE ENGLISH TRANSLATION DATA
# ------------------------------------------------------------

trans = pd.read_csv("data/translation-dataset-with-timestamps.csv")

trans["ID"] = (
    trans["file"].astype(str).str.strip()
    + "_"
    + trans["speaker"].astype(str).str.strip()
    + "_"
    + trans["turn"].astype(str).str.strip()
)

trans = trans.rename(columns={
    "text_fluent": "EN_fluent",
    "text_disfluent": "EN_disfluent"
})

trans = trans.drop(columns=["file", "speaker", "turn"])

trans = trans[[
    "ID",
    "EN_fluent",
    "EN_disfluent",
    "start_time",
    "end_time"
]]

# ------------------------------------------------------------
# 2. LOAD & NORMALIZE PROLIFIC RESPONSES
# ------------------------------------------------------------

BAD_PROLIFIC_IDS = {
    "68315e5a9a6549bae1cf72c9", # DE_T2
    "614759cfe568048a1689b38a", # DE_T2
    "67910fc4e7b17c7956861af8", # ES_T3
    "616a593422674254bdf13f77"  # CZ_T1
}

prolific = pd.read_csv("data/prolific_responses_raw.csv")

# identify rows where participants provided their Prolific ID
id_question_mask = (
    prolific["question"]
    .astype(str)
    .str.strip()
    == "Provide your Prolific ID in the box below."
)

# responseIds whose provided Prolific ID is bad
bad_response_ids = set(
    prolific.loc[
        id_question_mask & prolific["answer"].isin(BAD_PROLIFIC_IDS),
        "responseId"
    ]
)

print(f"Excluding {len(bad_response_ids)} submissions based on Prolific ID")

# drop *all* rows from those submissions
prolific = prolific[~prolific["responseId"].isin(bad_response_ids)]

# make sure bad IDs are truly gone
assert not prolific["responseId"].isin(bad_response_ids).any()

# quick visibility
print("Remaining rows:", len(prolific))
print("Remaining unique submissions:", prolific["responseId"].nunique())

# extract raw ID from question
prolific["ID_raw"] = (
    prolific["question"]
    .astype(str)
    .str.extract(r"(sw\d+_[A-Z]_\d+)")
    .iloc[:, 0]
)

prolific = prolific.dropna(subset=["ID_raw", "answer", "UID"])

# normalize sw02005 → sw2005
prolific["ID"] = prolific["ID_raw"].str.replace(
    r"sw0+(\d+)_",
    r"sw\1_",
    regex=True
)

# extract language code
prolific["lang"] = prolific["UID"].astype(str).str.split("_").str[0]

# ------------------------------------------------------------
# 3. COLLAPSE TO ONE ROW PER (ID, LANGUAGE)
# ------------------------------------------------------------

prolific = (
    prolific
    .sort_values("timestamp")
    .groupby(["ID", "lang"], as_index=False)
    .first()
)

# ------------------------------------------------------------
# 4. PIVOT LANGUAGES → COLUMNS
# ------------------------------------------------------------

prolific_wide = prolific.pivot(
    index="ID",
    columns="lang",
    values="answer"
)

prolific_wide.columns = [
    f"{lang}_disfluent" for lang in prolific_wide.columns
]

prolific_wide = prolific_wide.reset_index()

# ------------------------------------------------------------
# 5. SANITY CHECK
# ------------------------------------------------------------

common_ids = set(trans["ID"]) & set(prolific_wide["ID"])

print("Sample trans IDs:", trans["ID"].head().tolist())
print("Sample prolific IDs:", prolific_wide["ID"].head().tolist())
print("Intersection size:", len(common_ids))

assert len(common_ids) > 0, "No overlapping IDs after normalization"

# ------------------------------------------------------------
# 6. MERGE
# ------------------------------------------------------------

merged = trans.merge(
    prolific_wide,
    on="ID",
    how="inner"
)

# ------------------------------------------------------------
# 7. SAVE
# ------------------------------------------------------------

out = "data/uh-mazing.csv"
merged.to_csv(out, index=False)

print(f"DONE — {len(merged)} rows written to {out}")
print("Language columns:",
      [c for c in merged.columns if c.endswith("_disfluent")])
