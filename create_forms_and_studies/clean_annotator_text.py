# Run: python create_forms_and_studies/clean_annotator_text.py
#
# Reads the website's source data file (docs/round2/data.json — produced
# by generate_docs_data.py from the prolific annotator submissions),
# applies a sequence of underscore-cleanup operations to every translation
# string, then writes the cleaned result back out to both
# docs/round2/data.json AND docs/data.js so the website picks them up.
#
# Each cleanup operation is isolated as its own function with a docstring
# explaining the malformed input pattern it fixes. The runtime tokenizer
# in docs/annotate.html performs equivalent regex preprocessing on the fly,
# but applying the same fixes once at the source has two benefits:
#
#   1. Anyone inspecting docs/round2/data.json sees clean canonical text,
#      not the raw worker submissions with their stray spaces and glued
#      underscores.
#   2. If the runtime tokenizer is later simplified, the data already
#      survives without it.

import json
import re
import sys
from pathlib import Path

ROOT      = Path(__file__).resolve().parent.parent
DATA_JSON = ROOT / "docs" / "round2" / "data.json"
DATA_JS   = ROOT / "docs" / "data.js"


# ── Cleanup operations ────────────────────────────────────────────────────────
# Each function takes a single translation string and returns the cleaned
# version. They are applied in order in `clean_text()` below; ordering
# matters because some functions assume the canonical separators produced
# by earlier ones.

def collapse_comma_separator(text: str) -> str:
    """Collapse "_ , _" → "_,_".

    Round-1 translators wrote disfluency separator markers with optional
    whitespace around the comma. The runtime tokenizer (and downstream
    cleanups in this file) expect the canonical no-space form, so collapse
    every variant — "_ , _", "_,_", "_  ,  _" — to a single token.
    """
    return re.sub(r"_ *, *_", "_,_", text)


def collapse_period_separator(text: str) -> str:
    """Collapse "_ . _" → "_._".

    Same idea as `collapse_comma_separator` but for sentence-ending
    separators like "Sì _ . _ Ma" used to mark a full stop alongside a
    disfluency. The collapsed form parses as a single span containing
    just ".".
    """
    return re.sub(r"_ *\. *_", "_._", text)


def collapse_cjk_comma_separator(text: str) -> str:
    """Collapse "_ ， _" → "_，_"   (Chinese fullwidth comma U+FF0C).

    Mandarin translators used the fullwidth comma "，" instead of ASCII ","
    inside their separators. The ASCII collapse above doesn't catch these,
    so we mirror it for Chinese punctuation.
    """
    return re.sub(r"_ *， *_", "_，_", text)


def collapse_cjk_period_separator(text: str) -> str:
    """Collapse "_ 。 _" → "_。_"   (Chinese ideographic period U+3002).

    Same as the comma case, for Mandarin sentence-ending separators.
    """
    return re.sub(r"_ *。 *_", "_。_", text)


# Why no "unstick" cleanup here:
#
# Earlier versions of this script tried to insert spaces before glued
# separators (e.g. turn "Cioè_,_" into "Cioè _,_") on the theory that the
# tokenizer's canStartSpan check rejects the leading "_". That broke a
# bunch of cases — when a worker writes "_diciamo_,_" they intend
# `_diciamo_` (closed span) followed by `_,_` (separator), and inserting
# a space turns it into "_diciamo _,_" — an UNCLOSED `_diciamo` span.
#
# The runtime tokenizer in docs/annotate.html has its own (more careful)
# unstick rule that handles "Cioè_,_" via a regex with proper anchoring,
# so we let that handle the live parse. This script focuses only on the
# safe normalizations that the worker's separator-spacing inconsistencies
# call for.

CLEANUPS = [
    collapse_comma_separator,
    collapse_period_separator,
    collapse_cjk_comma_separator,
    collapse_cjk_period_separator,
]


def clean_text(text: str) -> str:
    """Apply every cleanup operation in order and return the cleaned text."""
    for fn in CLEANUPS:
        text = fn(text)
    return text


# ── Driver ────────────────────────────────────────────────────────────────────

def main():
    if not DATA_JSON.exists():
        sys.exit(f"missing {DATA_JSON} — run generate_docs_data.py first")

    blob = json.loads(DATA_JSON.read_text(encoding="utf-8"))

    per_lang_changed = {}
    examples = []
    total_changed = 0
    for lang in sorted(blob):
        per_lang_changed[lang] = 0
        for item in blob[lang]:
            for slot, raw in (item.get("translations") or {}).items():
                if not raw:
                    continue
                cleaned = clean_text(raw)
                if cleaned != raw:
                    item["translations"][slot] = cleaned
                    per_lang_changed[lang] += 1
                    total_changed += 1
                    if len(examples) < 5:
                        examples.append((lang, item["utt_id"], slot, raw[:140], cleaned[:140]))

    print(f"Cleaned {total_changed} translation(s) total.")
    for lang, n in per_lang_changed.items():
        if n > 0:
            print(f"  {lang}: {n} changed")
    if examples:
        print("\nExamples:")
        for lang, utt_id, slot, before, after in examples:
            print(f"  {lang}/{utt_id}/{slot}")
            print(f"    BEFORE: {before}")
            print(f"    AFTER:  {after}")

    json_text = json.dumps(blob, ensure_ascii=False, indent=2)
    DATA_JSON.write_text(json_text + "\n", encoding="utf-8")
    DATA_JS.write_text(f"const INLINE_DATA = {json_text};\n", encoding="utf-8")
    print(f"\nWrote {DATA_JSON.relative_to(ROOT)}")
    print(f"Wrote {DATA_JS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
