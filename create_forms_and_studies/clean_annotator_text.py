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


# Why no fancy "unstick glued separator" cleanup:
#
# Earlier versions of this script tried to insert spaces before glued
# separators (e.g. turn "Cioè_,_" into "Cioè _,_") on the theory that the
# tokenizer's canStartSpan check rejects the leading "_". That broke a
# bunch of cases — when a worker writes "_diciamo_,_" they intend
# `_diciamo_` (closed span) followed by `_,_` (separator), and inserting
# a space turns it into "_diciamo _,_" — an UNCLOSED `_diciamo` span.
#
# Instead, we have a fallback below: if the tokenizer would produce
# anomalies on a translation, strip ALL underscores from it so every
# individual token becomes cleanly clickable. The worker loses the
# default-highlight markup from the source but keeps a usable UI.


def strip_all_underscores_if_broken(text: str) -> str:
    """Last-resort fallback: if tokenize(text) would produce a literal "_"
    in any token (or a runaway span >25 chars), strip ALL underscores from
    the text. The translation then tokenizes into N clean plain-word
    tokens, each individually clickable but unhighlighted by default. The
    worker loses the source's default-highlight markup but the UI works.

    This handles the residual cases the four collapse_* functions can't
    fix:
      - "_word_" spans glued to a preceding letter (e.g. Czech
        "Celá_třída_", Arabic "لي_انا_", Mandarin "得_，_")
      - Unclosed spans like "_word " with no closing "_"
      - Trailing dangling "_" from a worker's last separator with no more
        "_"s after

    Detection runs the same logic as the live tokenizer in
    docs/annotate.html so we strip exactly the cases the worker would
    have seen broken.
    """
    if not _tokenizes_cleanly(text):
        return re.sub(r"_", "", text)
    return text


# ── Tokenizer mirror, used only by strip_all_underscores_if_broken ──
#
# Mirrors the JS tokenize() function in docs/annotate.html. KEEP IN
# SYNC if you change the JS one. We don't need the full token list —
# just enough to detect "would this parse with literal _ or runaway
# spans" — but it's easier to port the whole thing than maintain a
# heuristic that diverges from reality.

_NORMALIZE_PASSES = [
    (re.compile(r"_ *, *_"),         "_,_"),
    (re.compile(r"_ *\. *_"),        "_._"),
    (re.compile(r"(\w)(_[,.]_)", re.UNICODE),  r"\1 \2"),
]

def _normalize_for_tokenize(s: str) -> str:
    for pat, repl in _NORMALIZE_PASSES:
        s = pat.sub(repl, s)
    return s


def _tokenizes_cleanly(raw: str) -> bool:
    """Return False if the live tokenizer would produce any literal-underscore
    token or any span longer than 25 chars. Same detection rule used by
    debug_tokenize.js."""
    s = _normalize_for_tokenize(str(raw or ""))
    n = len(s)
    i = 0
    while i < n:
        # canStartSpan(pos): pos==0 OR previous char is non-letter
        def can_start(p):
            if p == 0:
                return True
            return not re.match(r"\w", s[p-1], flags=re.UNICODE)

        # Double-underscore span "__token__"
        if i + 1 < n and s[i] == "_" and s[i+1] == "_" and can_start(i):
            end = s.find("__", i + 2)
            if end != -1:
                content = s[i+2:end]
                if "_" in content or len(content) > 25:
                    return False
                i = end + 2
                continue

        # Single-underscore span "_token_"
        if s[i] == "_" and can_start(i):
            end = s.find("_", i + 1)
            if end != -1:
                content = s[i+1:end]
                # Multi-word span splits on whitespace; otherwise one token
                if content.strip() and " " in content.strip():
                    for part in re.split(r"(\s+)", content):
                        if part == "" or part.isspace():
                            continue
                        if "_" in part or len(part) > 25:
                            return False
                else:
                    if "_" in content or len(content) > 25:
                        return False
                i = end + 1
                continue

        # Plain text — scan to next span-starting underscore (or EOS)
        j = i + 1
        while j < n:
            if s[j] == "_" and can_start(j):
                break
            j += 1
        chunk = s[i:j]
        for part in re.split(r"(\s+)", chunk):
            if part == "" or part.isspace():
                continue
            for sub in re.split(r"([,!?;:.]+)", part):
                if sub == "":
                    continue
                if "_" in sub:
                    return False
        i = j

    return True


CLEANUPS = [
    collapse_comma_separator,
    collapse_period_separator,
    collapse_cjk_comma_separator,
    collapse_cjk_period_separator,
    strip_all_underscores_if_broken,
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
