from flask import Flask, render_template_string, send_from_directory
import os

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HTML = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Monthly Fees Calculator (MMK)</title>

  <link href="https://unpkg.com/tabulator-tables@6.3.0/dist/css/tabulator.min.css" rel="stylesheet">
  <script src="https://unpkg.com/tabulator-tables@6.3.0/dist/js/tabulator.min.js"></script>

  <style>
    body{
      font-family: Arial, sans-serif;
      max-width: 1300px;
      margin: 24px auto;
      padding: 0 16px;
      background-image: url("/assets/Ada.png"); /* Ada.png in same folder as app.py */
      background-size: cover;
      background-position: center;
      background-attachment: fixed;
    }
    .wrap{
      background: rgba(255,255,255,0.88);
      border: 1px solid rgba(0,0,0,0.06);
      border-radius: 18px;
      padding: 16px 16px 20px;
      backdrop-filter: blur(6px);
    }
    h1 { font-size: 20px; margin: 0 0 12px; }
    h2 { font-size: 16px; margin: 18px 0 10px; }
    button { padding: 10px 14px; border: 1px solid #ddd; border-radius: 10px; background:#fff; cursor:pointer; }
    button:hover { background:#f6f6f6; }
    .totals { display:flex; gap:18px; flex-wrap:wrap; margin: 14px 0 10px; align-items: stretch; }
    .card { border: 1px solid #e6e6e6; border-radius: 14px; padding: 12px 14px; min-width: 220px; background: rgba(255,255,255,0.95); }
    .label { color:#666; font-size:12px; margin-bottom:6px; }
    .value { font-size:18px; font-weight:700; }
    .gridbox { border: 1px solid #eee; border-radius: 14px; overflow:hidden; background: rgba(255,255,255,0.96); }
    .rowbar { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin: 8px 0 10px; }
    .hint { color:#666; font-size:12px; margin-top: 10px; line-height: 1.4; }
    .actions { margin: 6px 0 14px; display:flex; gap:10px; flex-wrap:wrap; }
  </style>
</head>

<body>
<div class="wrap">
  <h1>Monthly Fees Calculator (MMK) — Movies & Series</h1>

  <div class="totals">
    <div class="card">
      <div class="label">Movie Total (MMK)</div>
      <div class="value" id="movieTotal">0</div>
    </div>
    <div class="card">
      <div class="label">Series Total (MMK)</div>
      <div class="value" id="seriesTotal">0</div>
    </div>
    <div class="card">
      <div class="label">Grand Total (MMK)</div>
      <div class="value" id="grandTotal">0</div>
    </div>
  </div>

  <div class="actions">
    <button id="exportTxt">📄 Export Note File (.txt)</button>
  </div>

  <h2>🎬 Movies</h2>
  <div class="rowbar">
    <button id="addMovieRow">+ Add Movie Row</button>
    <button id="delMovieRow">🗑️ Delete Selected Movies</button>
  </div>
  <div id="movies-table" class="gridbox"></div>

  <h2>📺 Series</h2>
  <div class="rowbar">
    <button id="addSeriesRow">+ Add Series Row</button>
    <button id="delSeriesRow">🗑️ Delete Selected Series</button>
  </div>
  <div id="series-table" class="gridbox"></div>

  <div class="hint">
    <b>Fees behavior</b>
    <ul>
      <li><b>Type = Exe</b> → Fees is <b>manual</b> (you type it).</li>
      <li><b>Custom Fee = Yes</b> → Fees is <b>manual</b> (even if Blank).</li>
      <li><b>Blank + Custom Fee = No</b> → Fees auto-calc from rules below.</li>
    </ul>
    <b>Auto rules (Blank only)</b>
    <ul>
      <li><b>Movies</b>: Old base 12,000 (limit 1200, extra ×10), New base 15,000 (limit 1200, extra ×15)</li>
      <li><b>Series</b>: Old base 8,000 (limit 800, extra ×10), New base 10,000 (limit 800, extra ×15)</li>
      <li>If lines exceed limit: <b>Fee = base + (extra × rate)</b></li>
    </ul>
    <b>Export (.txt)</b>: exports only <b>Name | Lines | Fees</b> (from both tables).
  </div>
</div>

<script>
  // ---------- formatting + parsing ----------
  function mmkFormat(n){ return (n||0).toLocaleString("en-US"); }

  function toIntMaybe(v){
    const s = String(v ?? "").trim();
    if(!s) return null;
    const cleaned = s.replaceAll(",", "");
    const n = Number(cleaned);
    if(!Number.isFinite(n)) return null;
    return Math.trunc(n);
  }

  // ---------- auto fee calc (Blank + Auto only) ----------
  function calcBlankAutoFee(section, oldNew, lines){
    section = (section||"").toLowerCase();
    oldNew  = (oldNew||"").toLowerCase();

    if(lines === null || lines < 0) return null;
    if(oldNew !== "old" && oldNew !== "new") return null;

    let limit, base, rate;

    if(section === "movie"){
      limit = 1200;
      base = (oldNew === "old") ? 12000 : 15000;
      rate = (oldNew === "old") ? 10 : 15;
    } else if(section === "series"){
      limit = 800;
      base = (oldNew === "old") ? 8000 : 10000;
      rate = (oldNew === "old") ? 10 : 15;
    } else {
      return null;
    }

    if(lines <= limit) return base;
    return base + (lines - limit) * rate;
  }

  function shouldAutoCalc(rowData){
    const type = String(rowData.type ?? "").toLowerCase();
    const customFee = String(rowData.customFee ?? "").toLowerCase(); // yes/no
    if(type === "exe") return false;
    if(customFee === "yes") return false;
    return true; // Blank + No
  }

  // ---------- LIVE editor for Lines (updates Fees + totals while typing) ----------
  function liveLinesEditor(cell, onRendered, success, cancel, editorParams){
    const input = document.createElement("input");
    input.type = "text";
    input.value = cell.getValue() ?? "";
    input.style.width = "100%";
    input.style.boxSizing = "border-box";

    const section = editorParams.section;

    const updateLive = () => {
      const row = cell.getRow();
      const data = row.getData();

      if(shouldAutoCalc(data)){
        const lines = toIntMaybe(input.value);
        const fee = calcBlankAutoFee(section, data.oldNew, lines);
        row.update({ fees: (fee === null ? "" : mmkFormat(fee)) });
      }
      recalcTotals();
    };

    input.addEventListener("input", updateLive);
    onRendered(() => input.focus());

    input.addEventListener("blur", () => success(input.value));
    input.addEventListener("keydown", (e) => {
      if(e.key === "Enter") success(input.value);
      if(e.key === "Escape") cancel();
    });

    return input;
  }

  // ---------- LIVE editor for Fees (manual) ----------
  function liveFeesEditor(cell, onRendered, success, cancel){
    const input = document.createElement("input");
    input.type = "text";
    input.value = cell.getValue() ?? "";
    input.style.width = "100%";
    input.style.boxSizing = "border-box";

    input.addEventListener("input", () => recalcTotals());
    onRendered(() => input.focus());

    input.addEventListener("blur", () => success(input.value));
    input.addEventListener("keydown", (e) => {
      if(e.key === "Enter") success(input.value);
      if(e.key === "Escape") cancel();
    });

    return input;
  }

  function makeRow(no){
    return { no, type: "Blank", customFee: "No", oldNew: "Old", name: "", lines: "", fees: "" };
  }

  function buildTable(el, section){
    let rowNo = 1;
    const data = Array.from({length: 6}, () => makeRow(rowNo++));

    const table = new Tabulator(el, {
      data,
      layout: "fitColumns",
      height: "320px",
      selectable: true,
      reactiveData: true,
      clipboard: true,
      clipboardPasteAction: "replace",
      columns: [
        {title:"No.", field:"no", width:70, editor:false},
        {title:"Type", field:"type", width:120, editor:"list", editorParams:{values:["Exe","Blank"]}},
        {title:"Custom Fee", field:"customFee", width:130, editor:"list", editorParams:{values:["No","Yes"]}},
        {title:"Old/New", field:"oldNew", width:120, editor:"list", editorParams:{values:["Old","New"]}},
        {title:"Name", field:"name", minWidth:240, editor:"input"},
        {title:"Lines", field:"lines", width:120, editor: liveLinesEditor, editorParams:{section}},

        {
          title:"Fees (MMK)",
          field:"fees",
          width:150,
          editor: liveFeesEditor,
          editable: function(cell){
            const d = cell.getRow().getData();
            const type = String(d.type ?? "").toLowerCase();
            const custom = String(d.customFee ?? "").toLowerCase();
            return (type === "exe" || custom === "yes");
          }
        }
      ],

      cellEdited: function(cell){
        const row = cell.getRow();
        const d = row.getData();

        // If Type becomes Exe, force Custom Fee = Yes (so Fees is editable)
        if(String(d.type ?? "").toLowerCase() === "exe" && String(d.customFee ?? "").toLowerCase() !== "yes"){
          row.update({ customFee: "Yes" });
        }

        // If auto-calc row, refresh fees when Old/New or Custom Fee changes, etc.
        if(shouldAutoCalc(d)){
          const lines = toIntMaybe(d.lines);
          const fee = calcBlankAutoFee(section, d.oldNew, lines);
          row.update({ fees: (fee === null ? "" : mmkFormat(fee)) });
        }

        recalcTotals();
      },
    });

    table._rowNo = rowNo;
    table._renumber = () => {
      const rows = table.getData();
      rows.forEach((r, idx) => r.no = idx + 1);
      table._rowNo = rows.length + 1;
      table.replaceData(rows);
    };
    table._addRow = () => {
      table.addRow(makeRow(table._rowNo++), true);
      table._renumber();
      recalcTotals();
    };
    table._deleteSelected = () => {
      table.getSelectedRows().forEach(r => r.delete());
      table._renumber();
      recalcTotals();
    };

    return table;
  }

  const moviesTable = buildTable("#movies-table", "movie");
  const seriesTable = buildTable("#series-table", "series");

  // totals are based on Fees column => updates instantly when Fees changes
  function sumFeesFromTable(table){
    let total = 0;
    table.getData().forEach(r => {
      const fee = toIntMaybe(r.fees);
      if(fee !== null && fee >= 0) total += fee;
    });
    return total;
  }

  function recalcTotals(){
    const movieTotal = sumFeesFromTable(moviesTable);
    const seriesTotal = sumFeesFromTable(seriesTable);
    document.getElementById("movieTotal").textContent = mmkFormat(movieTotal);
    document.getElementById("seriesTotal").textContent = mmkFormat(seriesTotal);
    document.getElementById("grandTotal").textContent = mmkFormat(movieTotal + seriesTotal);
  }

  document.getElementById("addMovieRow").addEventListener("click", () => moviesTable._addRow());
  document.getElementById("delMovieRow").addEventListener("click", () => moviesTable._deleteSelected());
  document.getElementById("addSeriesRow").addEventListener("click", () => seriesTable._addRow());
  document.getElementById("delSeriesRow").addEventListener("click", () => seriesTable._deleteSelected());

  // -------- Export Note File (.txt) --------
  // Export ONLY: Name | Lines | Fees  (from both tables)
  document.getElementById("exportTxt").addEventListener("click", function(){
    const out = [];

    function collect(table){
      table.getData().forEach(r => {
        const name = String(r.name ?? "").trim();
        if(!name) return;

        const lines = String(r.lines ?? "").trim();
        const fees  = String(r.fees ?? "").trim();

        // exactly what you requested: name, lines, fees
        out.push(`${name} | ${lines} | ${fees}`);
      });
    }

    collect(moviesTable);
    collect(seriesTable);

    const content = out.join("\n");
    const blob = new Blob([content], {type: "text/plain;charset=utf-8"});
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = "Monthly_Fees_Note.txt";
    a.click();

    URL.revokeObjectURL(url);
  });

  recalcTotals();
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

# Serve Ada.png (and any other files) from the SAME folder as app.py
@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(BASE_DIR, filename)

if __name__ == "__main__":
    app.run(debug=True)