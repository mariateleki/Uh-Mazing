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
│ 4. PUBLICATION — produce dataset + website                              │
└─────────────────────────────────────────────────────────────────────────┘

  data/prolific_responses_filtered.csv         data/prolific_responses_raw.csv
              │                                              │
              ▼                                              ▼
  generate_docs_data.py                         finalize_dataset.py
              │                                  (uses BAD_PROLIFIC_IDS list)
   ┌──────────┴──────────┐                                   │
   ▼                     ▼                                   ▼
  docs/data.js     round2/data.json                  data/uh-mazing.csv

  (loaded by docs/index.html, docs/admin.html, docs/annotate.html,
   and round2/index.html)


┌─────────────────────────────────────────────────────────────────────────┐
│ 5. DOWNSTREAM — analysis, experiments, ASR, IRR                         │
└─────────────────────────────────────────────────────────────────────────┘

  data/uh-mazing.csv
        │
        ├─► process_swb/add_node_combos_to_uh_mazing.py
        │                              ─► data/uh-mazing-with-node-combos.csv
        │
        ├─► experiments/run_translate.py  (LLM translation conditions)
        │                              ─► outputs/uh-mazing_<model>_<cond>.csv
        │   experiments/infer_single_missing_arabic_gemini_audio_…ipynb
        │
        ├─► asr/run_asr_gpt.py            ─► asr/asr_transcripts_gpt_*.csv
        │   asr/run_asr_gemini.py         ─► asr/asr_transcripts_gemini_*.csv
        │   asr/calculate_wer.py
        │       (compares ASR vs uh-mazing as ground truth)
        │                              ─► asr/*_with_wer.csv, *_wer_summary.csv
        │
        ├─► analysis/IRR/irr.ipynb        (uses uh-mazing.csv + uh-mazing-gold-irr.csv)
        │
        ├─► llm-as-a-judge/score_outputs_gpt.py  (scores experiments/ outputs)
        │                              ─► llm-as-a-judge/scores/
        │   llm-as-a-judge/plot_category_distribution.ipynb
        │
        └─► round2/eda_underscore_patterns.ipynb
                (reads prolific_responses_filtered.csv directly)

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

To also refresh the raw dump and `data/uh-mazing.csv` (used by analysis):

```bash
python ./create_forms_and_studies/bulk_merge_google_forms.py
python ./create_forms_and_studies/finalize_dataset.py
```

To refresh downstream artifacts (after `uh-mazing.csv` changes):

```bash
python ./process_swb/add_node_combos_to_uh_mazing.py
python ./experiments/run_translate.py     # rerun LLM translation experiments
python ./asr/calculate_wer.py             # recompute WER vs new ground truth
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

| Page                   | Role                                       |
|------------------------|--------------------------------------------|
| `docs/index.html`      | Read-only translation viewer               |
| `docs/admin.html`      | Curator view (needs `?script=…` URL)       |
| `docs/annotate.html`   | Annotator UI                               |

Serve locally:

```bash
cd docs && python3 -m http.server 8765
# then open http://localhost:8765/  (or admin.html, annotate.html)
```

`round2/index.html` is a separate self-contained viewer served by
`round2/serve.py` on port 8765 — combined view, no role split.

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
| `finalize_dataset.py`                         | Build `data/uh-mazing.csv` for downstream analysis   |
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
