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
  }
  return sheet;
}

// ── POST: receive annotation submission ──────────────────────────────────────
function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const type = data.type;

    if (type === 'annotation') {
      const sheet = getOrCreateSheet('Responses', [
        'timestamp', 'prolific_id', 'lang',
        'native_language', 'fluency', 'age_range',
        'utt_id', 'slot', 'removed', 'added', 'text_edit',
        'qc_feedback', 'qc_note'
      ]);
      sheet.appendRow([
        new Date().toISOString(),
        data.prolific_id,
        data.lang,
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
        'timestamp', 'prolific_id', 'lang',
        'native_language', 'fluency', 'age_range',
        'screen', 'utt_id', 'item_index', 'message'
      ]);
      sheet.appendRow([
        new Date().toISOString(),
        data.prolific_id     || '',
        data.lang            || '',
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
        'timestamp', 'prolific_id', 'lang',
        'native_language', 'fluency', 'age_range', 'status'
      ]);
      // Update existing row or add new
      const data_values = sheet.getDataRange().getValues();
      let found = false;
      for (let i = 1; i < data_values.length; i++) {
        if (data_values[i][1] === data.prolific_id && data_values[i][2] === data.lang) {
          sheet.getRange(i + 1, 7).setValue(data.status || 'started');
          found = true;
          break;
        }
      }
      if (!found) {
        sheet.appendRow([
          new Date().toISOString(),
          data.prolific_id,
          data.lang,
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

    // Annotators sheet summary
    const annotSheet = ss.getSheetByName('Annotators');
    const annotators = [];
    if (annotSheet) {
      const rows = annotSheet.getDataRange().getValues();
      for (let i = 1; i < rows.length; i++) {
        annotators.push({
          timestamp:       rows[i][0],
          prolific_id:     rows[i][1],
          lang:            rows[i][2],
          native_language: rows[i][3],
          fluency:         rows[i][4],
          age_range:       rows[i][5],
          status:          rows[i][6]
        });
      }
    }

    // Responses sheet — count per (prolific_id, lang)
    const respSheet = ss.getSheetByName('Responses');
    const counts = {};
    if (respSheet) {
      const rows = respSheet.getDataRange().getValues();
      for (let i = 1; i < rows.length; i++) {
        const key = rows[i][1] + '|' + rows[i][2];
        counts[key] = (counts[key] || 0) + 1;
      }
    }

    // Attach counts to annotators
    for (const a of annotators) {
      const key = a.prolific_id + '|' + a.lang;
      a.annotations_submitted = counts[key] || 0;
    }

    return respond({ status: 'ok', annotators });

  } catch (err) {
    return respond({ status: 'error', message: err.toString() });
  }
}
