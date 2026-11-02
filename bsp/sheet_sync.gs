// BSP Card Generator
// Copyright (C) 2026 William Becker
// Licensed under the GNU General Public License v3 or later. See LICENSE.
//
// Motor Pool <-> Google Sheet link. Paste this into the Sheet's
// Extensions > Apps Script, set SECRET, then Deploy > New deployment >
// Web app (Execute as: Me, Who has access: Anyone), then give the web app URL
// and the same secret to `python -m bsp.sheet setup`. Full steps: README.md,
// "Google Sheet pull and push".
//
// Only that command-line tool calls this; the Motor Pool app never reads the
// Sheet. Without the secret the link does nothing.

const SECRET = "change-me";   // any long phrase; the same one goes into `python -m bsp.sheet setup`

function doPost(e) {
  let req;
  try {
    req = JSON.parse(e.postData.contents);
  } catch (err) {
    return reply({ok: false, error: "Request was not JSON."});
  }
  if (SECRET === "change-me" || req.key !== SECRET) {
    return reply({ok: false, error: "Wrong secret (check SECRET in the Apps Script and run python -m bsp.sheet setup)."});
  }
  const book = SpreadsheetApp.getActiveSpreadsheet();
  const tabs = book.getSheets().map(s => s.getName());
  if (req.action === "tabs") {
    return reply({ok: true, tabs: tabs});
  }
  if (req.action === "pull") {
    const sheet = book.getSheetByName(req.tab);
    if (!sheet) {
      return reply({ok: false, error: `No tab named "${req.tab}". Tabs: ${tabs.join(", ")}`});
    }
    // Display values: exactly what the Sheet shows, so "6/12/18" stays text.
    return reply({ok: true, tab: req.tab, rows: sheet.getDataRange().getDisplayValues()});
  }
  if (req.action === "push") {
    const rows = req.rows || [];
    if (!rows.length) return reply({ok: false, error: "Nothing to push."});
    // Always a brand-new tab: never overwrite anything already in the Sheet.
    let name = req.tab, n = 2;
    while (book.getSheetByName(name)) name = `${req.tab} (${n++})`;
    const sheet = book.insertSheet(name, book.getSheets().length);
    const range = sheet.getRange(1, 1, rows.length, rows[0].length);
    range.setNumberFormat("@");   // plain text: no dates or formulas made from card values
    range.setValues(rows);
    sheet.setFrozenRows(1);
    sheet.getRange(1, 1, 1, rows[0].length).setFontWeight("bold");
    return reply({ok: true, tab: name, rows: rows.length - 1});
  }
  return reply({ok: false, error: `Unknown action "${req.action}".`});
}

function reply(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
