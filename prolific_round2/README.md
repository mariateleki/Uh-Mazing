# prolific_round2

Scripts that publish the round-2 disfluency-annotation site as Prolific
studies. The site itself lives at
[`docs/annotate.html`](../docs/annotate.html); this folder turns it into 8
live Prolific studies (one per language, all 80 utterances each).

## Files

| File                    | Purpose                                                          |
|-------------------------|------------------------------------------------------------------|
| `bulk_create_studies.py`| Creates + publishes one study per language                       |
| `check_status.py`       | Queries the Prolific API for completion status of every study    |
| `results.csv`           | Output written by `bulk_create_studies.py` — study IDs + URLs    |

## Standard workflow

1. Set `PROLIFIC_TOKEN` in `.env` at the repo root. The Prolific project ID
   is hardcoded inside `bulk_create_studies.py`; override by setting
   `PROLIFIC_PROJECT_ID` if you need to publish elsewhere.
2. (Optional) Set `TEST_MODE = True` near the top of `bulk_create_studies.py`
   to dry-run a single study before publishing all 8.
3. Run:
   ```bash
   python prolific_round2/bulk_create_studies.py
   ```
4. Each language gets:
   - title `Disfluency Annotation — {LangName}`
   - filter: native speaker of target language + fluent in English
   - external URL with `lang=XX&cc=UM-XX`
   - completion code `UM-XX` registered as `COMPLETED` (auto-approve)
5. Inspect `prolific_round2/results.csv` for study IDs and dashboard links.

## Tunable knobs

Edit at the top of `bulk_create_studies.py`:

| Constant                   | Default | Notes                                          |
|----------------------------|---------|------------------------------------------------|
| `TOTAL_PLACES_PER_STUDY`   | 1       | Distinct annotators per language               |
| `ESTIMATED_TIME_MIN`       | 60      | What Prolific shows participants               |
| `REWARD_USD_CENTS`         | 2000    | $20 per submission                             |
| `MIN_COMPLETION_TIME`      | 15      | Auto-reject submissions faster than this (min) |
| `TEST_MODE`                | False   | True = create only the first study             |
| `LANGUAGES`                | 8 langs | Add/remove (lang_code → display name)          |

## Completion codes

Each language has a stable code: `UM-{LANG}` (e.g. `UM-ZH`). That same code
is:

1. Embedded in the URL via `?cc=UM-ZH`. `annotate.html` reads `cc` and shows
   it on the final screen.
2. Registered with Prolific as the `COMPLETED` completion code for that
   study so the participant can submit successfully.
