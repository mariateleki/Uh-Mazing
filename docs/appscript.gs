// Run instructions:
// 1. Open https://script.google.com and create a new project
// 2. Paste this entire file into the editor
// 3. Add OpenAI credentials to Script Properties (Project Settings → Script Properties):
//      OPENAI_API_KEY  = sk-...
//      OPENAI_ORG      = org-...
//      OPENAI_PROJECT  = proj_...
// 4. Click Deploy > New deployment > Web app
//    - Execute as: Me
//    - Who has access: Anyone
// 5. Copy the deployment URL and paste it into annotate.html as APPS_SCRIPT_URL

const SHEET_ID = '1C-_1lLYM2JocDWMbZMFzd22RQyBAKhFfvSoyLhAIEiE';

function getOrCreateSheet(name, headers) {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  let sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
    sheet.appendRow(headers);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold');
    return sheet;
  }
  // Migrate: append any new headers that aren't already present.
  // Existing rows keep blank cells in the new columns, which is fine.
  const existing = sheet.getRange(1, 1, 1, Math.max(1, sheet.getLastColumn())).getValues()[0];
  const existingSet = new Set(existing.map(String));
  for (const h of headers) {
    if (!existingSet.has(h)) {
      const col = sheet.getLastColumn() + 1;
      sheet.getRange(1, col).setValue(h).setFontWeight('bold');
    }
  }
  return sheet;
}

// Column index (1-based) for a header on the given sheet, or null if missing.
function colIdx(sheet, header) {
  const row = sheet.getRange(1, 1, 1, Math.max(1, sheet.getLastColumn())).getValues()[0];
  for (let i = 0; i < row.length; i++) if (String(row[i]) === header) return i + 1;
  return null;
}

// ── POST: receive annotation submission ──────────────────────────────────────
function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const type = data.type;

    // The 'part' column is preserved in existing sheets but always written
    // empty going forward — we removed the part split from annotate.html.
    if (type === 'annotation') {
      const sheet = getOrCreateSheet('Responses', [
        'timestamp', 'prolific_id', 'lang',
        'native_language', 'fluency', 'age_range',
        'utt_id', 'slot', 'removed', 'added', 'text_edit'
      ]);
      // Append by header lookup so we don't disturb legacy 'part'/'qc_*' cols
      // in older sheets — those just stay blank for new rows.
      const row = new Array(sheet.getLastColumn()).fill('');
      const set = (h, v) => { const c = colIdx(sheet, h); if (c) row[c - 1] = v; };
      set('timestamp',       new Date().toISOString());
      set('prolific_id',     data.prolific_id);
      set('lang',            data.lang);
      set('native_language', data.native_language);
      set('fluency',         data.fluency);
      set('age_range',       data.age_range);
      set('utt_id',          data.utt_id);
      set('slot',            data.slot);
      set('removed',         JSON.stringify(data.removed || []));
      set('added',           JSON.stringify(data.added || []));
      set('text_edit',       data.text_edit || '');
      sheet.appendRow(row);
    }

    if (type === 'report') {
      const sheet = getOrCreateSheet('Reports', [
        'timestamp', 'prolific_id', 'lang',
        'native_language', 'fluency', 'age_range',
        'screen', 'utt_id', 'item_index', 'message'
      ]);
      const row = new Array(sheet.getLastColumn()).fill('');
      const set = (h, v) => { const c = colIdx(sheet, h); if (c) row[c - 1] = v; };
      set('timestamp',       new Date().toISOString());
      set('prolific_id',     data.prolific_id     || '');
      set('lang',            data.lang            || '');
      set('native_language', data.native_language || '');
      set('fluency',         data.fluency         || '');
      set('age_range',       data.age_range       || '');
      set('screen',          data.screen          || '');
      set('utt_id',          data.utt_id          || '');
      set('item_index',      data.item_index      || '');
      set('message',         data.message         || '');
      sheet.appendRow(row);
    }

    if (type === 'intake') {
      const sheet = getOrCreateSheet('Annotators', [
        'timestamp', 'prolific_id', 'lang',
        'native_language', 'fluency', 'age_range', 'status'
      ]);
      const cPid    = colIdx(sheet, 'prolific_id');
      const cLang   = colIdx(sheet, 'lang');
      const cStatus = colIdx(sheet, 'status');
      // Upsert by (prolific_id, lang) — no longer split by part.
      const data_values = sheet.getDataRange().getValues();
      let found = false;
      for (let i = 1; i < data_values.length; i++) {
        if (
          data_values[i][cPid - 1]  === data.prolific_id &&
          data_values[i][cLang - 1] === data.lang
        ) {
          sheet.getRange(i + 1, cStatus).setValue(data.status || 'started');
          found = true;
          break;
        }
      }
      if (!found) {
        const row = new Array(sheet.getLastColumn()).fill('');
        const set = (h, v) => { const c = colIdx(sheet, h); if (c) row[c - 1] = v; };
        set('timestamp',       new Date().toISOString());
        set('prolific_id',     data.prolific_id);
        set('lang',            data.lang);
        set('native_language', data.native_language);
        set('fluency',         data.fluency);
        set('age_range',       data.age_range);
        set('status',          data.status || 'started');
        sheet.appendRow(row);
      }
    }

    return ContentService
      .createTextOutput(JSON.stringify({ status: 'ok' }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// ── GET: return progress summary for admin page ───────────────────────────────
// Supports JSONP via ?callback=fnName to bypass browser CORS restrictions.
function doGet(e) {
  const callback = (e.parameter || {}).callback || null;

  function respond(payload) {
    const json = JSON.stringify(payload);
    if (callback) {
      // JSONP: wrap in callback function call, loaded as <script>
      return ContentService
        .createTextOutput(callback + '(' + json + ')')
        .setMimeType(ContentService.MimeType.JAVASCRIPT);
    }
    return ContentService
      .createTextOutput(json)
      .setMimeType(ContentService.MimeType.JSON);
  }

  const type = (e.parameter || {}).type || '';

  // ── Verify which (utt_id, slot) pairs are already saved for a worker ──────
  // Used by annotate.html's screenComplete: after the final saveAndNext, the
  // browser asks "what do you actually have?" and re-POSTs anything missing
  // before showing the completion code. Catches races where the tab closes
  // before Apps Script finishes appendRow.
  if (type === 'verify_saves') {
    try {
      const pid  = (e.parameter.prolific_id || '').toString();
      const lang = (e.parameter.lang        || '').toString();
      if (!pid || !lang) return respond({ status: 'error', message: 'pid and lang required' });

      const ss = SpreadsheetApp.openById(SHEET_ID);
      const sheet = ss.getSheetByName('Responses');
      if (!sheet) return respond({ status: 'ok', saved: [] });

      const cPid  = colIdx(sheet, 'prolific_id');
      const cLang = colIdx(sheet, 'lang');
      const cUtt  = colIdx(sheet, 'utt_id');
      const cSlot = colIdx(sheet, 'slot');
      if (!cPid || !cLang || !cUtt || !cSlot) {
        return respond({ status: 'error', message: 'Responses sheet missing required columns' });
      }

      const rows  = sheet.getDataRange().getValues();
      const saved = [];
      for (let i = 1; i < rows.length; i++) {
        if (String(rows[i][cPid - 1])  !== pid)  continue;
        if (String(rows[i][cLang - 1]) !== lang) continue;
        saved.push({ utt_id: String(rows[i][cUtt - 1]), slot: String(rows[i][cSlot - 1]) });
      }
      return respond({ status: 'ok', saved });
    } catch (err) {
      return respond({ status: 'error', message: err.toString() });
    }
  }

  // ── Default: return annotator progress summary ────────────────────────────
  try {
    const ss = SpreadsheetApp.openById(SHEET_ID);

    // Annotators sheet summary — read by header so column ordering changes
    // (or legacy 'part' columns) don't break existing rows.
    const annotSheet = ss.getSheetByName('Annotators');
    const annotators = [];
    if (annotSheet) {
      const rows = annotSheet.getDataRange().getValues();
      const h = (name) => {
        const c = colIdx(annotSheet, name);
        return c ? c - 1 : -1;
      };
      const cTime = h('timestamp'),       cPid = h('prolific_id'), cLang = h('lang');
      const cNat  = h('native_language'), cFlu = h('fluency');
      const cAge  = h('age_range'),       cStatus = h('status');
      for (let i = 1; i < rows.length; i++) {
        annotators.push({
          timestamp:       cTime   >= 0 ? rows[i][cTime]   : '',
          prolific_id:     cPid    >= 0 ? rows[i][cPid]    : '',
          lang:            cLang   >= 0 ? rows[i][cLang]   : '',
          native_language: cNat    >= 0 ? rows[i][cNat]    : '',
          fluency:         cFlu    >= 0 ? rows[i][cFlu]    : '',
          age_range:       cAge    >= 0 ? rows[i][cAge]    : '',
          status:          cStatus >= 0 ? rows[i][cStatus] : ''
        });
      }
    }

    // Responses sheet — count per (prolific_id, lang)
    const respSheet = ss.getSheetByName('Responses');
    const counts = {};
    if (respSheet) {
      const rows = respSheet.getDataRange().getValues();
      const cPid  = colIdx(respSheet, 'prolific_id');
      const cLang = colIdx(respSheet, 'lang');
      for (let i = 1; i < rows.length; i++) {
        const pid  = cPid  ? rows[i][cPid  - 1] : '';
        const lang = cLang ? rows[i][cLang - 1] : '';
        counts[pid + '|' + lang] = (counts[pid + '|' + lang] || 0) + 1;
      }
    }

    // Attach counts to annotators
    for (const a of annotators) {
      a.annotations_submitted = counts[a.prolific_id + '|' + a.lang] || 0;
    }

    return respond({ status: 'ok', annotators });

  } catch (err) {
    return respond({ status: 'error', message: err.toString() });
  }
}
