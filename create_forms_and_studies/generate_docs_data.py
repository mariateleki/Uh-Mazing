# Run: python ./create_forms_and_studies/generate_docs_data.py
#
# Generates the static data files used by the docs/ website (and the round2/
# viewer) from data/prolific_responses_filtered.csv. This is the link between
# the merge pipeline and the front-end:
#
#   prolific_responses_filtered.csv ──► docs/data.js  (loaded by docs/*.html)
#                                  ╰──► round2/data.json
#
# English source text is taken from the existing round2/data.json so it stays
# consistent (those en strings already carry the right disfluency markup).

import csv
import json
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
FILTERED_CSV = ROOT / "data" / "prolific_responses_filtered.csv"
EN_SOURCE    = ROOT / "docs" / "round2" / "data.json"
OUT_DATA_JS  = ROOT / "docs" / "data.js"
OUT_JSON     = ROOT / "docs" / "round2" / "data.json"

UID_RE = re.compile(r"^([A-Z]{2,3})_(T\d)$")
QUESTION_RE = re.compile(r"\[(sw\d+_[AB]_\d+)\]")


def load_english_by_uttid():
    """Return dict utt_id -> en string, taken from the existing round2/data.json."""
    blob = json.loads(EN_SOURCE.read_text())
    out = {}
    for lang, items in blob.items():
        for it in items:
            uid = it["utt_id"]
            # If the same utt_id shows up under multiple languages, prefer the
            # first one (they should match — same English source per utterance).
            out.setdefault(uid, it["en"])
    return out


def load_translations():
    """Return dict lang -> utt_id -> translator -> text from the filtered CSV."""
    out = defaultdict(lambda: defaultdict(dict))
    with open(FILTERED_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            m = UID_RE.match(row["UID"])
            if not m:
                continue
            lang, translator = m.group(1), m.group(2)
            qm = QUESTION_RE.match(row["question"])
            if not qm:
                continue  # skip Prolific ID / Completion Code rows
            utt_id = qm.group(1)
            out[lang][utt_id][translator] = row["answer"]
    return out


def build_dataset(translations, en_by_utt):
    """Assemble final {lang: [ {utt_id, en, translations: {Tn: ...}}, ... ]}."""
    dataset = {}
    missing_en = set()
    for lang in sorted(translations):
        items = []
        # Stable utt_id order: sort lexicographically so the website is deterministic.
        for utt_id in sorted(translations[lang]):
            en = en_by_utt.get(utt_id)
            if en is None:
                missing_en.add(utt_id)
                en = ""  # leave blank rather than dropping the row
            items.append({
                "utt_id": utt_id,
                "en": en,
                "translations": dict(sorted(translations[lang][utt_id].items())),
            })
        dataset[lang] = items
    if missing_en:
        print(f"  WARNING: {len(missing_en)} utt_id(s) had no English source: "
              f"{sorted(missing_en)[:5]}{'…' if len(missing_en) > 5 else ''}")
    return dataset


def write_outputs(dataset):
    """Write dataset to both docs/data.js (as a JS const) and round2/data.json."""
    json_text = json.dumps(dataset, ensure_ascii=False, indent=2)

    OUT_JSON.write_text(json_text + "\n", encoding="utf-8")
    print(f"  wrote {OUT_JSON.relative_to(ROOT)}")

    OUT_DATA_JS.write_text(f"const INLINE_DATA = {json_text};\n", encoding="utf-8")
    print(f"  wrote {OUT_DATA_JS.relative_to(ROOT)}")


def main():
    print(f"Reading translations from {FILTERED_CSV.relative_to(ROOT)}")
    translations = load_translations()
    total_cells = sum(
        len(t) for lang_d in translations.values() for t in lang_d.values()
    )
    print(f"  {len(translations)} languages, "
          f"{sum(len(v) for v in translations.values())} (lang,utt) pairs, "
          f"{total_cells} translation cells")

    print(f"Reading English source from {EN_SOURCE.relative_to(ROOT)}")
    en_by_utt = load_english_by_uttid()
    print(f"  {len(en_by_utt)} unique utt_ids")

    print("Building combined dataset")
    dataset = build_dataset(translations, en_by_utt)

    print("Writing outputs")
    write_outputs(dataset)

    # Per-language summary
    print("\nPer-language counts (utt_ids · translators):")
    for lang in sorted(dataset):
        items = dataset[lang]
        translators = sorted({t for it in items for t in it["translations"]})
        print(f"  {lang}: {len(items)} utt_ids · {','.join(translators)}")


if __name__ == "__main__":
    main()
