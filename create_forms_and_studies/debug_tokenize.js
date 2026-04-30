// Run:
//   node create_forms_and_studies/debug_tokenize.js                  # full audit
//   node create_forms_and_studies/debug_tokenize.js IT T1 sw02005_A_149   # one cell
//   node create_forms_and_studies/debug_tokenize.js --raw "Cioè_ , _ uh"  # ad-hoc text
//
// Shows exactly what the live tokenizer does with annotation text:
//
//   1. Pulls in the live tokenize() function from docs/annotate.html so
//      we never drift from what the worker's browser actually runs.
//   2. Walks every (lang, utt_id, slot) translation in docs/round2/data.json
//      OR the single one you specify on the command line, and reports:
//        - the raw text from the prolific submission
//        - the text AFTER the regex normalizations (the cleanup logic)
//        - the resulting token list, with each token's index, isSpan flag,
//          and any anomaly markers
//   3. Anomaly heuristics flag tokens that smell like the parser tripped:
//        - text contains a literal "_"  (unclosed span / glued underscore)
//        - span text > 25 chars         (runaway span swallowing words)
//        - text contains "\n"            (line break leaked in)
//        - 0 clickable tokens overall
//
// Useful when a worker reports "highlighting doesn't work for utterance X
// in language Y" — you can paste that (lang, T#, utt_id) here and see the
// exact transformation chain that produced their broken token list.

const fs = require("fs");
const path = require("path");

// ── Pull the live tokenize() out of docs/annotate.html so we always
//    debug against what the browser actually parses.
function loadLiveTokenizer() {
  const html = fs.readFileSync(path.join(__dirname, "..", "docs", "annotate.html"), "utf8");
  const fnMatch = html.match(/function tokenize\(raw\)[\s\S]+?\n}/);
  if (!fnMatch) throw new Error("could not find tokenize() in docs/annotate.html");
  // eslint-disable-next-line no-eval
  eval(fnMatch[0] + "; module.exports.tokenize = tokenize;");
  return module.exports.tokenize;
}

// Mirror of the tokenizer's regex preprocessing so the debug output can
// show "after normalize" verbatim. KEEP IN SYNC with the prelude inside
// `function tokenize(raw)` in docs/annotate.html. As of this writing:
//
//   .replace(/_ *, *_/g, '_,_')                    // collapse "_ , _"
//   .replace(/_ *\. *_/g, '_._')                   // collapse "_ . _"
//   .replace(/(\p{L})(_[,.]_)/gu, '$1 $2')         // unstick letter+_,_
//
// If you tweak those regexes in annotate.html (e.g. to also handle
// fullwidth Chinese punctuation _，_ / _。_), mirror the change here.
function applyNormalizations(raw) {
  return String(raw || '')
    .replace(/_ *, *_/g, '_,_')
    .replace(/_ *\. *_/g, '_._')
    .replace(/(\p{L})(_[,.]_)/gu, '$1 $2');
}

// ── Anomaly detection
function classifyTokens(toks) {
  const flags = [];
  const click = toks.filter(t => !t.isSpace);
  const litUnderscore = click.filter(t => /_/.test(t.text));
  const newlines      = click.filter(t => /[\n\r]/.test(t.text));
  const longSpans     = click.filter(t => t.isSpan && t.text.length > 25);
  if (litUnderscore.length) flags.push(`literal "_" in ${litUnderscore.length} token(s)`);
  if (longSpans.length)     flags.push(`runaway span: ${longSpans.length} token(s) over 25 chars (max ${Math.max(...longSpans.map(t => t.text.length))})`);
  if (newlines.length)      flags.push(`newline in ${newlines.length} token(s)`);
  if (click.length === 0)   flags.push("zero clickable tokens");
  return flags;
}

function describeOne(tokenize, raw, label) {
  const normalized = applyNormalizations(raw);
  const toks = tokenize(raw);
  const flags = classifyTokens(toks);

  const lines = [];
  if (label) lines.push(`── ${label} ──`);
  lines.push("RAW:        " + JSON.stringify(raw).slice(0, 400));
  if (normalized !== raw) {
    lines.push("NORMALIZED: " + JSON.stringify(normalized).slice(0, 400));
  } else {
    lines.push("NORMALIZED: (no regex changes)");
  }
  lines.push("TOKENS:");
  for (const t of toks) {
    if (t.isSpace) continue;
    const span = t.isSpan ? "*" : " ";
    const warn = (/[_\n\r]/.test(t.text) || (t.isSpan && t.text.length > 25)) ? "  ⚠" : "";
    lines.push(`  [${String(t.index).padStart(3)}] ${span}  ${JSON.stringify(t.text)}${warn}`);
  }
  if (flags.length) {
    lines.push("ANOMALIES: " + flags.join("; "));
  } else {
    lines.push("ANOMALIES: none");
  }
  return lines.join("\n");
}

// ── Modes
function modeRawString(tokenize, rawStr) {
  console.log(describeOne(tokenize, rawStr, "ad-hoc string"));
}

function modeOneCell(tokenize, lang, slot, uttId) {
  const data = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "docs", "round2", "data.json"), "utf8"));
  const items = data[lang.toUpperCase()];
  if (!items) throw new Error(`unknown language: ${lang}`);
  const item = items.find(x => x.utt_id === uttId);
  if (!item) throw new Error(`utt_id ${uttId} not found in ${lang}`);
  const raw = (item.translations || {})[slot.toUpperCase()];
  if (raw === undefined) throw new Error(`no ${slot.toUpperCase()} translation for ${lang}/${uttId}`);
  console.log(describeOne(tokenize, raw, `${lang.toUpperCase()} / ${uttId} / ${slot.toUpperCase()}`));
}

function modeFullAudit(tokenize) {
  const data = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "docs", "round2", "data.json"), "utf8"));
  const totals = {};
  const samples = {};
  for (const lang of Object.keys(data).sort()) {
    let count = 0;
    for (const item of data[lang]) {
      for (const [slot, raw] of Object.entries(item.translations || {})) {
        if (!raw) continue;
        const flags = classifyTokens(tokenize(raw));
        if (flags.length === 0) continue;
        count++;
        if (!samples[lang]) samples[lang] = [];
        if (samples[lang].length < 3) {
          samples[lang].push({ utt_id: item.utt_id, slot, flags, raw: raw.slice(0, 180) });
        }
      }
    }
    totals[lang] = count;
  }

  console.log("=== Anomaly summary across all languages ===\n");
  let grand = 0;
  for (const lang of Object.keys(totals).sort()) {
    grand += totals[lang];
    console.log(`  ${lang}: ${totals[lang]} translation(s) flagged`);
    for (const s of samples[lang] || []) {
      console.log(`    • ${s.utt_id} ${s.slot}  [${s.flags.join("; ")}]`);
      console.log(`      raw: ${s.raw}${s.raw.length === 180 ? "…" : ""}`);
    }
  }
  console.log(`\nGrand total: ${grand} flagged translation(s)`);
  console.log("\nTo inspect a specific cell:");
  console.log("  node create_forms_and_studies/debug_tokenize.js <LANG> <T#> <utt_id>");
  console.log("  e.g. node create_forms_and_studies/debug_tokenize.js IT T1 sw02005_A_149");
}

// ── Entry point
function main() {
  const tokenize = loadLiveTokenizer();
  const args = process.argv.slice(2);

  if (args.length === 0) {
    modeFullAudit(tokenize);
  } else if (args[0] === "--raw") {
    modeRawString(tokenize, args.slice(1).join(" "));
  } else if (args.length === 3) {
    modeOneCell(tokenize, args[0], args[1], args[2]);
  } else {
    console.error("Usage:");
    console.error("  node create_forms_and_studies/debug_tokenize.js                          # full audit");
    console.error("  node create_forms_and_studies/debug_tokenize.js LANG T# utt_id           # one cell");
    console.error("  node create_forms_and_studies/debug_tokenize.js --raw \"any string\"     # ad-hoc text");
    process.exit(1);
  }
}

main();
