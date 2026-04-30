# Uh-Mazing — pipeline reference

This README documents the full data + script flow across the repo. The
`create_forms_and_studies/` directory is the *middle* of the pipeline —
upstream is Switchboard processing, downstream is analysis / experiments /
ASR / IRR.

---

## Full data flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. UPSTREAM — Switchboard preprocessing (process_swb/)                  │
└─────────────────────────────────────────────────────────────────────────┘

  Switchboard MRG / split files
              │
              ▼
  process_swb/process_swb_text.py  ─────────► data/train.csv
                                              data/train-marked.csv
              │
              ├─► map_train_marked_to_mrg.py ─► data/train-marked-with-mrg.csv
              ├─► add_disfluency_combo_cols_to_train_marked.py
              │                              ─► data/train-marked-with-timestamps.csv
              │                              ─► data/train-marked-with-node-combos.csv
              ▼
  Switchboard audio  ─► process_swb_audio.ipynb
                       ─► data/swb1_audio_timestamps/
                       ─► data/translation_dataset_audio/

  data/translation-dataset-with-timestamps.csv  (English source for forms)


┌─────────────────────────────────────────────────────────────────────────┐
│ 2. ANNOTATION COLLECTION — Google Forms + Prolific                      │
└─────────────────────────────────────────────────────────────────────────┘

  data/translation-dataset-with-timestamps.csv
              │
              ▼
  bulk_create_google_forms.py        ─► 32 Google Forms (8 langs × T1–T4)
  bulk_create_prolific_studies.py    ─► matching Prolific studies
  check_prolific_filters.py          ─► verify Prolific filters

              │  (Annotators submit translations)
              ▼

  bulk_merge_google_forms.py  ─► data/prolific_responses_raw.csv
                                 (every submission from every form)


┌─────────────────────────────────────────────────────────────────────────┐
│ 3. CURATION — pick one submission per form                              │
└─────────────────────────────────────────────────────────────────────────┘

  annotator_keep.csv  (curator decisions)
              │
              ▼  (independent fetch — does NOT read raw.csv)
  merge_filtered_annotators.py
              │
              ▼
  data/prolific_responses_filtered.csv


┌─────────────────────────────────────────────────────────────────────────┐
│ 4. PUBLICATION — produce website                                        │
└─────────────────────────────────────────────────────────────────────────┘

  data/prolific_responses_filtered.csv
              │
              ▼
  generate_docs_data.py
              │
   ┌──────────┴──────────────┐
   ▼                         ▼
  docs/data.js     docs/round2/data.json

  Everything served by GitHub Pages lives under docs/.
  Loaded by:
    docs/index.html         (read-only translation viewer)
    docs/admin.html         (curator view)
    docs/annotate.html      (annotator UI)
    docs/round2/index.html  (round2 combined viewer)


┌─────────────────────────────────────────────────────────────────────────┐
│ 5. DOWNSTREAM — analysis, experiments, ASR, IRR                         │
└─────────────────────────────────────────────────────────────────────────┘

  Switchboard-derived English source — used by anything that doesn't need
  the per-language translations:

  data/translation-dataset-with-timestamps.csv
        │  (file/speaker/turn → ID synthesized at load time;
        │   text_fluent/text_disfluent → renamed inline)
        │
        ├─► process_swb/add_node_combos_to_uh_mazing.py
        │                              ─► data/translation-source-with-node-combos.csv
        │
        ├─► experiments/run_translate.py  (text + audio modes)
        │                              ─► outputs/uh-mazing_<model>_<cond>.csv
        │   experiments/infer_single_missing_arabic_gemini_audio_…ipynb
        │
        └─► asr/calculate_wer.py
                (compares ASR vs English ground truth)
                                       ─► asr/*_with_wer.csv, *_wer_summary.csv

  Translation pipeline — used by anything that needs the actual annotator
  translations:

  data/prolific_responses_filtered.csv
        │
        ├─► analysis/IRR/irr.ipynb
        │     (pivots filtered.csv → wide LANG_disfluent layout inline,
        │      compares against data/uh-mazing-gold-irr.csv)
        │
        └─► round2/eda_underscore_patterns.ipynb

  Output of run_translate.py → llm-as-a-judge:
        llm-as-a-judge/score_outputs_gpt.py  → llm-as-a-judge/scores/
        llm-as-a-judge/plot_category_distribution.ipynb

  Separate human-eval branches (independent of uh-mazing.csv):
        analyze_style/visualize_annotations.ipynb     (uses analyze_style/annotations.json)
        human-eval-emotions/visualize.ipynb            (uses human-eval-emotions/annotations.json)

  External libraries vendored in repo:
        dres/      disfluency-removal-env (DRES)
        zscore/    z-score ASR scoring; run_zscore_asr_batch.py
```

---

## Standard workflow

After updating `annotator_keep.csv`:

```bash
python ./create_forms_and_studies/merge_filtered_annotators.py
python ./create_forms_and_studies/generate_docs_data.py
```

The first command fetches forms fresh from Google Drive and writes
`data/prolific_responses_filtered.csv`. The second pivots that into the
website's expected shape and writes both `docs/data.js` and
`round2/data.json`.

To also refresh the raw dump (used for ad-hoc analysis of all submissions):

```bash
python ./create_forms_and_studies/bulk_merge_google_forms.py
```

To refresh downstream artifacts (no `uh-mazing.csv` middleman anymore — these
read directly from the Switchboard source or from `prolific_responses_filtered.csv`):

```bash
python ./process_swb/add_node_combos_to_uh_mazing.py
python ./experiments/run_translate.py     # rerun LLM translation experiments
python ./asr/calculate_wer.py             # recompute WER vs new ground truth
# IRR notebook: open analysis/IRR/irr.ipynb (pivots filtered.csv inline)
```

---

## annotator_keep.csv cell formats

| Cell                       | Meaning                                                |
|----------------------------|--------------------------------------------------------|
| `<prolific_id>`            | Keep the response whose Prolific ID answer matches     |
| `BLANK`                    | Keep the response with empty-string Prolific ID        |
| `NONE`                     | Skip this form entirely                                |
| `<id> / M/D/YYYY HH:MM:SS` | Disambiguate duplicate submissions by timestamp        |
| `INCOMPLETE / <id>`        | Keep the response, flagged as incomplete               |

---

## Viewing the website

Three pages live in `docs/`:

| Page                       | Role                                       |
|----------------------------|--------------------------------------------|
| `docs/index.html`          | Read-only translation viewer               |
| `docs/admin.html`          | Curator view (needs `?script=…` URL)       |
| `docs/annotate.html`       | Annotator UI                               |
| `docs/round2/index.html`   | Round2 combined viewer                     |

Live URLs (deployed by GitHub Pages from the `docs/` folder):

- https://mariateleki.github.io/Uh-Mazing/
- https://mariateleki.github.io/Uh-Mazing/admin.html
- https://mariateleki.github.io/Uh-Mazing/annotate.html
- https://mariateleki.github.io/Uh-Mazing/round2/

Serve locally (mirrors the same URL paths):

```bash
cd docs && python3 -m http.server 8765
# or:
python3 round2/serve.py
# then open http://localhost:8765/  (or /round2/, /admin.html, /annotate.html)
```

---

## Files in `create_forms_and_studies/`

| File                                          | Purpose                                              |
|-----------------------------------------------|------------------------------------------------------|
| `bulk_create_google_forms.py`                 | Create the 32 Google Forms from a base template      |
| `bulk_create_prolific_studies.py`             | Create matching Prolific studies                     |
| `bulk_create_prolific_human_eval_studies.py`  | Same, for human-eval round                           |
| `check_prolific_filters.py`                   | Verify Prolific study filter settings                |
| `bulk_merge_google_forms.py`                  | Pull every submission from every form (raw)          |
| `merge_filtered_annotators.py`                | Pick one submission per form via `annotator_keep.csv`|
| `generate_docs_data.py`                       | Build `docs/data.js` + `round2/data.json`            |
| `annotator_keep.csv`                          | Curator's per-form chosen submission                 |
| `base_form.json`                              | Template used by `bulk_create_google_forms.py`       |
| `credentials.json`                            | OAuth client secrets (gitignored)                    |
| `../token.json`                               | Cached OAuth token (gitignored)                      |

---

## Auth notes

Google APIs are accessed via OAuth (`token.json` at the repo root).
Different scripts request different scopes:

- `bulk_merge_google_forms.py` — Forms + Sheets
- `merge_filtered_annotators.py` — Forms + Drive
- `generate_docs_data.py` — local files only, no auth needed

If you switch between scripts and hit a 403 "insufficient scopes" error,
delete `token.json` and re-authorize — the next run will request the fuller
scope set.
