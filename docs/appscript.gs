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

    // Normalize the part field: '1', 1, or 'p1' all become 1; null/undefined/'' stay ''.
    const partVal = (data.part === 1 || data.part === '1' || data.part === 'p1') ? 1
                  : (data.part === 2 || data.part === '2' || data.part === 'p2') ? 2
                  : '';

    if (type === 'annotation') {
      const sheet = getOrCreateSheet('Responses', [
        'timestamp', 'prolific_id', 'lang', 'part',
        'native_language', 'fluency', 'age_range',
        'utt_id', 'slot', 'removed', 'added', 'text_edit',
        'qc_feedback', 'qc_note'
      ]);
      sheet.appendRow([
        new Date().toISOString(),
        data.prolific_id,
        data.lang,
        partVal,
        data.native_language,
        data.fluency,
        data.age_range,
        data.utt_id,
        data.slot,
        JSON.stringify(data.removed || []),
        JSON.stringify(data.added || []),
        data.text_edit   || '',
        data.qc_feedback || '',
        data.qc_note     || '',
      ]);
    }

    if (type === 'report') {
      const sheet = getOrCreateSheet('Reports', [
        'timestamp', 'prolific_id', 'lang', 'part',
        'native_language', 'fluency', 'age_range',
        'screen', 'utt_id', 'item_index', 'message'
      ]);
      sheet.appendRow([
        new Date().toISOString(),
        data.prolific_id     || '',
        data.lang            || '',
        partVal,
        data.native_language || '',
        data.fluency         || '',
        data.age_range       || '',
        data.screen          || '',
        data.utt_id          || '',
        data.item_index      || '',
        data.message         || ''
      ]);
    }

    if (type === 'intake') {
      const sheet = getOrCreateSheet('Annotators', [
        'timestamp', 'prolific_id', 'lang', 'part',
        'native_language', 'fluency', 'age_range', 'status'
      ]);
      // Resolve actual column positions in case the existing sheet has a
      // different ordering (migration safety).
      const cPid    = colIdx(sheet, 'prolific_id');
      const cLang   = colIdx(sheet, 'lang');
      const cPart   = colIdx(sheet, 'part');
      const cStatus = colIdx(sheet, 'status');
      // Update existing row or add new — match on (prolific_id, lang, part) so
      // a worker doing both halves of the same language has separate rows.
      const data_values = sheet.getDataRange().getValues();
      let found = false;
      for (let i = 1; i < data_values.length; i++) {
        const rowPart = cPart ? data_values[i][cPart - 1] : '';
        if (
          data_values[i][cPid - 1]  === data.prolific_id &&
          data_values[i][cLang - 1] === data.lang        &&
          (rowPart === partVal || (rowPart === '' && partVal === ''))
        ) {
          sheet.getRange(i + 1, cStatus).setValue(data.status || 'started');
          found = true;
          break;
        }
      }
      if (!found) {
        sheet.appendRow([
          new Date().toISOString(),
          data.prolific_id,
          data.lang,
          partVal,
          data.native_language,
          data.fluency,
          data.age_range,
          data.status || 'started'
        ]);
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

  // ── QC check: call OpenAI and return feedback via JSONP ───────────────────
  if (type === 'qc_check') {
    try {
      const props   = PropertiesService.getScriptProperties();
      const apiKey  = props.getProperty('OPENAI_API_KEY');
      const org     = props.getProperty('OPENAI_ORG')     || '';
      const project = props.getProperty('OPENAI_PROJECT') || '';
      const model   = e.parameter.model || 'gpt-4.5-preview';
      const lang    = e.parameter.lang  || '';
      const en      = e.parameter.en    || '';

      // Rebuild slot lines from URL params (t1, t2, t3, t4)
      const slotLines = ['t1','t2','t3','t4']
        .filter(s => e.parameter[s])
        .map(s => `  ${s.toUpperCase()}: ${e.parameter[s]}`)
        .join('\n');

      const langNames = {ZH:'Mandarin',ES:'Spanish',HI:'Hindi',FR:'French',DE:'German',IT:'Italian',CS:'Czech',AR:'Arabic'};
      const langName  = langNames[lang] || lang;

      const prompt = `English:\n  ${en}\n\n${langName} translation:\n${slotLines}\n\n` +
        `Each underscored word in the English should have a corresponding underscored word in the ${langName} translation. ` +
        `Check whether this is the case. Are any English underscored words missing a ${langName} equivalent? Are there any extra underscored words in the translation with no English counterpart?\n\n` +
        `Reply in 1–3 sentences. Start with "Looks correct." if everything matches. If there are issues, be specific about which words are missing or extra.`;

      const headers = { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + apiKey };
      if (org)     headers['OpenAI-Organization'] = org;
      if (project) headers['OpenAI-Project']      = project;

      const aiResp = UrlFetchApp.fetch('https://api.openai.com/v1/chat/completions', {
        method:  'post',
        headers: headers,
        payload: JSON.stringify({ model, messages: [{ role: 'user', content: prompt }], temperature: 0 }),
        muteHttpExceptions: true,
      });

      const aiData   = JSON.parse(aiResp.getContentText());
      const feedback = aiData.choices ? aiData.choices[0].message.content.trim() : ('Error: ' + (aiData.error?.message || 'unknown'));
      return respond({ status: 'ok', feedback });
    } catch (err) {
      return respond({ status: 'error', message: err.toString() });
    }
  }

  // ── Default: return annotator progress summary ────────────────────────────
  try {
    const ss = SpreadsheetApp.openById(SHEET_ID);

    // Annotators sheet summary — read by header so column reordering or new
    // columns (like 'part') don't break existing rows.
    const annotSheet = ss.getSheetByName('Annotators');
    const annotators = [];
    if (annotSheet) {
      const rows = annotSheet.getDataRange().getValues();
      const h = (name) => {
        const c = colIdx(annotSheet, name);
        return c ? c - 1 : -1;
      };
      const cTime = h('timestamp'),       cPid = h('prolific_id'), cLang = h('lang');
      const cPart = h('part'),             cNat = h('native_language'), cFlu = h('fluency');
      const cAge  = h('age_range'),       cStatus = h('status');
      for (let i = 1; i < rows.length; i++) {
        annotators.push({
          timestamp:       cTime   >= 0 ? rows[i][cTime]   : '',
          prolific_id:     cPid    >= 0 ? rows[i][cPid]    : '',
          lang:            cLang   >= 0 ? rows[i][cLang]   : '',
          part:            cPart   >= 0 ? (rows[i][cPart] === '' ? null : rows[i][cPart]) : null,
          native_language: cNat    >= 0 ? rows[i][cNat]    : '',
          fluency:         cFlu    >= 0 ? rows[i][cFlu]    : '',
          age_range:       cAge    >= 0 ? rows[i][cAge]    : '',
          status:          cStatus >= 0 ? rows[i][cStatus] : ''
        });
      }
    }

    // Responses sheet — count per (prolific_id, lang, part)
    const respSheet = ss.getSheetByName('Responses');
    const counts = {};
    if (respSheet) {
      const rows = respSheet.getDataRange().getValues();
      const cPid  = colIdx(respSheet, 'prolific_id');
      const cLang = colIdx(respSheet, 'lang');
      const cPart = colIdx(respSheet, 'part');
      for (let i = 1; i < rows.length; i++) {
        const pid  = cPid  ? rows[i][cPid  - 1] : '';
        const lang = cLang ? rows[i][cLang - 1] : '';
        const part = cPart ? rows[i][cPart - 1] : '';
        const key  = pid + '|' + lang + '|' + (part === '' ? '' : part);
        counts[key] = (counts[key] || 0) + 1;
      }
    }

    // Attach counts to annotators
    for (const a of annotators) {
      const partKey = a.part === null || a.part === '' ? '' : a.part;
      const key = a.prolific_id + '|' + a.lang + '|' + partKey;
      a.annotations_submitted = counts[key] || 0;
    }

    return respond({ status: 'ok', annotators });

  } catch (err) {
    return respond({ status: 'error', message: err.toString() });
  }
}
