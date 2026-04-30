# prolific_round2

Scripts that publish the round-2 disfluency-annotation site as Prolific
studies. The site itself lives at
[`docs/annotate.html`](../docs/annotate.html) and supports
`?lang=XX&part=1|2&cc=…` URL parameters; this folder turns that into 16
live Prolific studies (8 languages × 2 parts).

## Files

| File                    | Purpose                                                          |
|-------------------------|------------------------------------------------------------------|
| `bulk_create_studies.py`| Creates + publishes one study per (lang × part)                  |
| `results.csv`           | Output written by `bulk_create_studies.py` — study IDs + URLs    |

## Standard workflow

1. Set `PROLIFIC_TOKEN` in `.env` at the repo root. The Prolific project ID
   is hardcoded to `69f2e9293c71ad8d3978a8f6` (a dedicated round-2 project)
   inside `bulk_create_studies.py`; override by setting `PROLIFIC_PROJECT_ID`
   in `.env` if you need to publish somewhere else.
2. (Optional) Set `TEST_MODE = True` near the top of `bulk_create_studies.py`
   to dry-run a single study before publishing all 16.
3. Run:
   ```bash
   python prolific_round2/bulk_create_studies.py
   ```
4. Each (lang × part) gets:
   - title `Disfluency Annotation — {LangName} (part N of 2)`
   - filter: native speaker of target language + fluent in English
   - external URL with `lang=XX&part=N&cc=UM-XX-PN`
   - completion code `UM-XX-PN` registered as `COMPLETED` (auto-approve)
5. Inspect `prolific_round2/results.csv` for study IDs and dashboard links.

## Tunable knobs

Edit at the top of `bulk_create_studies.py`:

| Constant                   | Default | Notes                                          |
|----------------------------|---------|------------------------------------------------|
| `TOTAL_PLACES_PER_STUDY`   | 3       | Distinct annotators per (lang × part)          |
| `ESTIMATED_TIME_MIN`       | 25      | What Prolific shows participants               |
| `REWARD_USD_CENTS`         | 500     | $5 per submission ≈ $12/hr at 25 min           |
| `MIN_COMPLETION_TIME`      | 8       | Auto-reject submissions faster than this (min) |
| `TEST_MODE`                | False   | True = create only the first study             |
| `LANGUAGES`                | 8 langs | Add/remove (lang_code → display name)          |

## How completion codes wire up

`bulk_create_studies.py` derives a stable code per study:
`UM-{LANG}-P{PART}` (e.g. `UM-ZH-P1`). That same code is:

1. Embedded in the URL given to Prolific via `?cc=UM-ZH-P1`. `annotate.html`
   reads `cc` from the URL and uses it as the displayed completion code on
   the final screen.
2. Registered with Prolific as the `COMPLETED` completion code so the
   participant can submit successfully.

This means each (lang × part) study has exactly one completion code that
everyone using that link will see at the end.

## Differences from `prolific/bulk_create_studies.py`

| | `prolific/` (round 1)             | `prolific_round2/` (this folder)   |
|-|-----------------------------------|------------------------------------|
| Input | `prolific/annotators.csv` — one row per worker, one URL per worker | None — config in the script        |
| URLs  | One per annotator (assigned)      | One per `(lang × part)` (shared)   |
| Filters | English fluency only            | First language = target language   |
| # studies | Variable (one per annotator)  | 16 (8 langs × 2 parts)             |
| Task title | "Inferring Emotions from Speech" | "Disfluency Annotation — …"       |
