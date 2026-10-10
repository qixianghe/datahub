"""Squad Skinfold Sums dashboard.

Used by the Performance > Skinfold Analysis page in app.py. The HTML/CSS/JS
below is a self-contained page; build_skinfold_html() fills in the data for
one screening date and returns the HTML for st.components.v1.html().

Source: screening_results, column "Skinfold Analysis - Sum of Skinfolds"
(sum of the ISAK 8 skinfold sites, in mm; lower is better).
"""

import json
import re

import pandas as pd

TEMPLATE = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Squad Skinfold Sums</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
  /* Layout: summary tiles, band distribution strip, then a ranked dot chart beside a sortable athlete table, method notes last. */
  :root {
    --bg: #EEF3F6;
    --surface: #FFFFFF;
    --ink: #13222B;
    --muted: #586873;
    --line: #D6E0E6;
    --accent: #0B6E8E;
    --track: #E3EBEF;
    --on-band: #FFFFFF;
    /* one colour per band, best to worst */
    --out: #0B6E8E;  --out-t: #DCEEF4;
    --good: #2A7B4C; --good-t: #E1F1E8;
    --acc: #7A6A08;  --acc-t: #F3EFCB;
    --mon: #B05A0C;  --mon-t: #F8E4D0;
    --bad: #BE3A2B;  --bad-t: #F9E1DD;
    --na: #586873;   --na-t: #E3EBEF;
    --f-display: "Barlow Condensed", "Arial Narrow", sans-serif;
    --f-body: "IBM Plex Sans", system-ui, sans-serif;
    --f-data: "IBM Plex Mono", ui-monospace, monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #0E181F; --surface: #15232C; --ink: #E5EDF1; --muted: #93A4AF; --line: #263A45;
      --accent: #52B9DA; --track: #20323C; --on-band: #0E181F;
      --out: #52B9DA; --out-t: #12313D;
      --good: #5CC48A; --good-t: #17352A;
      --acc: #D6C04A; --acc-t: #38330F;
      --mon: #EE9A4F; --mon-t: #3D2A14;
      --bad: #F27F70; --bad-t: #3D1F1B;
      --na: #93A4AF; --na-t: #20323C;
      color-scheme: dark;
    }
  }
  :root[data-theme="dark"] {
    --bg: #0E181F; --surface: #15232C; --ink: #E5EDF1; --muted: #93A4AF; --line: #263A45;
    --accent: #52B9DA; --track: #20323C; --on-band: #0E181F;
    --out: #52B9DA; --out-t: #12313D;
    --good: #5CC48A; --good-t: #17352A;
    --acc: #D6C04A; --acc-t: #38330F;
    --mon: #EE9A4F; --mon-t: #3D2A14;
    --bad: #F27F70; --bad-t: #3D1F1B;
    --na: #93A4AF; --na-t: #20323C;
    color-scheme: dark;
  }
  * { box-sizing: border-box; }
  body {
    background: var(--bg); color: var(--ink);
    font-family: var(--f-body); font-size: 15px; line-height: 1.5;
    padding-inline: 20px; padding-block: 28px 48px;
  }
  .wrap { max-width: 1120px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }
  header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: end; gap: 8px 24px; }
  h1 { font-family: var(--f-display); font-weight: 700; font-size: 2.4rem; line-height: 1; margin: 0; letter-spacing: .01em; text-wrap: balance; }
  .meta { font-family: var(--f-data); font-size: .8rem; color: var(--muted); }
  h2 { font-family: var(--f-display); font-weight: 600; font-size: 1.25rem; letter-spacing: .04em; text-transform: uppercase; margin: 0; }
  .sub { color: var(--muted); font-size: .85rem; margin: 2px 0 0; }

  .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
  .tile { background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 14px 16px; min-width: 0; }
  .tile .k { font-size: .75rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
  .tile .v { font-family: var(--f-display); font-weight: 700; font-size: 2.6rem; line-height: 1.1; font-variant-numeric: tabular-nums; }
  .tile .v small { font-size: 1.1rem; color: var(--muted); font-weight: 500; }
  .tile .n { font-size: .85rem; color: var(--muted); }
  .tile.banded { background: var(--b-t); border-color: var(--b); }
  .tile.banded .v { color: var(--b); }
  .tile.alert { background: var(--bad-t); border-color: var(--bad); }
  .tile.alert .v { color: var(--bad); }

  .panel { background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 18px; min-width: 0; display: flex; flex-direction: column; gap: 14px; }
  .grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 20px; }
  @media (min-width: 1240px) { .grid { grid-template-columns: minmax(0, 6fr) minmax(0, 5fr); } }

  /* band tokens, set per element through a modifier class */
  .out { --b: var(--out); --b-t: var(--out-t); }
  .good { --b: var(--good); --b-t: var(--good-t); }
  .acc { --b: var(--acc); --b-t: var(--acc-t); }
  .mon { --b: var(--mon); --b-t: var(--mon-t); }
  .bad { --b: var(--bad); --b-t: var(--bad-t); }
  .na { --b: var(--na); --b-t: var(--na-t); }

  /* distribution strip */
  .strip { display: flex; gap: 3px; height: 40px; }
  .seg { flex-grow: var(--n); flex-basis: 0; min-width: 0; background: var(--b); color: var(--on-band); border-radius: 4px; display: flex; align-items: center; justify-content: center; font-family: var(--f-display); font-weight: 700; font-size: 1.3rem; font-variant-numeric: tabular-nums; }
  .legend { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px 16px; margin: 0; padding: 0; list-style: none; }
  .legend li { display: grid; grid-template-columns: 2.4ch 1fr; gap: 0 10px; align-items: center; border-left: 4px solid var(--b); padding-left: 10px; }
  .legend b { font-weight: 600; grid-column: 2; grid-row: 1; }
  .legend .rg { grid-column: 2; grid-row: 2; font-size: .78rem; color: var(--muted); font-family: var(--f-data); }
  .legend .ct { grid-column: 1; grid-row: 1 / span 2; font-family: var(--f-display); font-weight: 700; font-size: 1.8rem; line-height: 1; font-variant-numeric: tabular-nums; text-align: right; }

  /* ranked dot chart, built from HTML so labels stay readable at phone width */
  .rank { display: flex; flex-direction: column; gap: 3px; }
  .raxis, .rrow { display: grid; grid-template-columns: minmax(64px, 112px) minmax(0, 1fr) 3.6em; gap: 10px; align-items: center; }
  .raxis { font-family: var(--f-data); font-size: .7rem; color: var(--muted); height: 18px; }
  .raxis .ticks { position: relative; height: 100%; }
  .raxis .ticks span { position: absolute; top: 0; transform: translateX(-50%); }
  .raxis .unit { text-align: right; }
  .rname { font-size: .85rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .rtrack { position: relative; height: 18px; border-radius: 3px; }
  .rtrack i { position: absolute; top: 50%; width: 12px; height: 12px; margin: -6px 0 0 -6px; border-radius: 50%; background: var(--b); border: 2px solid var(--surface); box-sizing: content-box; width: 8px; height: 8px; margin: -6px 0 0 -6px; }
  .rval { font-family: var(--f-data); font-size: .8rem; font-variant-numeric: tabular-nums; text-align: right; }
  @media (max-width: 560px) { .raxis .t55 { display: none; } }

  .table-scroll { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); font-weight: 500; padding: 0 6px 8px; border-bottom: 1px solid var(--line); white-space: nowrap; }
  th.r, td.r { text-align: right; }
  th button { all: unset; cursor: pointer; display: inline-flex; gap: 4px; align-items: center; }
  th button:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; border-radius: 2px; }
  th[aria-sort="ascending"] button::after { content: "\2191"; }
  th[aria-sort="descending"] button::after { content: "\2193"; }
  td { padding: 8px 6px; border-bottom: 1px solid var(--line); vertical-align: middle; }
  tr:last-child td { border-bottom: 0; }
  td.name { font-weight: 600; }
  td.val { font-family: var(--f-display); font-weight: 700; font-size: 1.3rem; line-height: 1; font-variant-numeric: tabular-nums; }
  td.val small { font-family: var(--f-data); font-weight: 400; font-size: .7rem; color: var(--muted); margin-left: 3px; }
  .pill { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font-size: .78rem; font-weight: 600; white-space: nowrap; background: var(--b-t); color: var(--b); }
  .pill::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
  .rule { font-size: .8rem; color: var(--muted); margin: 0; }
  .rule b { color: var(--ink); font-weight: 600; }
  .notice { border: 1px solid var(--mon); background: var(--mon-t); border-radius: 6px; padding: 10px 14px; font-size: .85rem; }
  .notice b { font-weight: 600; }
  .sites { margin: 0; padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: 6px; }
  .sites li { font-size: .8rem; padding: 3px 10px; border: 1px solid var(--line); border-radius: 999px; }
</style>
</head><body>
<div class="wrap">
  <header>
    <div>
      <h1>Squad Skinfold Sums</h1>
      <p class="sub" id="subtitle"></p>
    </div>
    <div class="meta">Sum of 8 skinfolds, mm. Lower is better.</div>
  </header>

  <div class="notice" id="notice" hidden></div>

  <section class="tiles" id="tiles" aria-label="Squad summary"></section>

  <section class="panel" aria-labelledby="dist-h">
    <div>
      <h2 id="dist-h">Squad by band</h2>
      <p class="sub">Number of athletes in each band.</p>
    </div>
    <div class="strip" id="strip" role="img" aria-label="Athletes per band"></div>
    <ul class="legend" id="legend"></ul>
  </section>

  <section class="grid">
    <div class="panel">
      <div>
        <h2>Ranked sums</h2>
        <p class="sub">Highest sum first. Shaded columns are the bands.</p>
      </div>
      <div class="rank" id="rank"></div>
    </div>

    <div class="panel">
      <div>
        <h2>Athletes</h2>
        <p class="sub">Select a column heading to sort. Highest sum first by default.</p>
      </div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th data-k="name" aria-sort="none"><button type="button">Athlete</button></th>
              <th data-k="v" class="r" aria-sort="descending"><button type="button">Sum (mm)</button></th>
              <th data-k="band" aria-sort="none"><button type="button">Band</button></th>
            </tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
    </div>
  </section>

  <section class="panel">
    <h2>How to read this</h2>
    <p class="rule">Each value is the <b>sum of eight skinfolds</b> from the ISAK 8-site protocol, in millimetres. A lower sum means less subcutaneous fat at the measured sites. Bands are checked from the top, so a value on a cut-off falls in the higher band: 50.0 is Good, 55.0 is Acceptable, 65.0 is Monitor and 75.0 is Bad.</p>
    <ul class="sites" aria-label="ISAK 8 sites">
      <li>Triceps</li><li>Subscapular</li><li>Biceps</li><li>Iliac crest</li><li>Supraspinale</li><li>Abdominal</li><li>Front thigh</li><li>Medial calf</li>
    </ul>
  </section>
</div>
<script>
(function () {
  var RAW = __DATA__;
  var META = __META__;
  var BANDS = [
    { key: "out",  label: "Outstanding", lo: -Infinity, hi: 50,       range: "Under 50 mm" },
    { key: "good", label: "Good",        lo: 50,        hi: 55,       range: "50 to under 55 mm" },
    { key: "acc",  label: "Acceptable",  lo: 55,        hi: 65,       range: "55 to under 65 mm" },
    { key: "mon",  label: "Monitor",     lo: 65,        hi: 75,       range: "65 to under 75 mm" },
    { key: "bad",  label: "Bad",         lo: 75,        hi: Infinity, range: "75 mm and over" }
  ];

  function esc(v) {
    return String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function bandIndex(v) {
    for (var i = 0; i < BANDS.length; i++) if (v >= BANDS[i].lo && v < BANDS[i].hi) return i;
    return BANDS.length - 1;
  }
  var all = RAW.map(function (r) {
    var v = Number(r[1]);
    var ok = isFinite(v) && v > 0;
    return { name: esc(r[0]), raw: r[0], v: ok ? v : null, ok: ok, band: ok ? bandIndex(v) : -1 };
  });
  var data = all.filter(function (d) { return d.ok; });
  var missing = all.filter(function (d) { return !d.ok; });
  var f1 = function (n) { return n.toFixed(1); };

  document.getElementById("subtitle").textContent =
    "ISAK 8-site sum of skinfolds, " + data.length + " athlete" + (data.length === 1 ? "" : "s") + " measured" + (META ? " · " + META : "");
  if (missing.length) {
    var n = document.getElementById("notice");
    n.hidden = false;
    n.innerHTML = "<b>Not included in the figures:</b> " + missing.map(function (d) { return d.name; }).join(", ") +
      " (recorded as 0 mm, which is not a possible skinfold sum, so it is treated as not measured). Re-measure or correct the entry.";
  }

  /* summary */
  var vals = data.map(function (d) { return d.v; }).sort(function (a, b) { return a - b; });
  var mean = vals.reduce(function (s, x) { return s + x; }, 0) / vals.length;
  var mid = vals.length % 2 ? vals[(vals.length - 1) / 2] : (vals[vals.length / 2 - 1] + vals[vals.length / 2]) / 2;
  var byVal = data.slice().sort(function (a, b) { return a.v - b.v; });
  var lowest = byVal[0], highest = byVal[byVal.length - 1];
  var attention = data.filter(function (d) { return d.band >= 3; }).sort(function (a, b) { return b.v - a.v; });
  var counts = BANDS.map(function (b, i) { return data.filter(function (d) { return d.band === i; }).length; });

  document.getElementById("tiles").innerHTML =
    '<div class="tile banded ' + BANDS[bandIndex(mean)].key + '"><div class="k">Squad average</div><div class="v">' + f1(mean) + '<small> mm</small></div><div class="n">' + BANDS[bandIndex(mean)].label + ' band</div></div>' +
    '<div class="tile banded ' + BANDS[bandIndex(mid)].key + '"><div class="k">Median</div><div class="v">' + f1(mid) + '<small> mm</small></div><div class="n">' + BANDS[bandIndex(mid)].label + ' band</div></div>' +
    '<div class="tile"><div class="k">Range (mm)</div><div class="v">' + f1(lowest.v) + '–' + f1(highest.v) + '</div><div class="n">' + lowest.name + ' to ' + highest.name + '</div></div>' +
    '<div class="tile alert"><div class="k">Monitor or Bad</div><div class="v">' + attention.length + '<small> ' + (attention.length === 1 ? 'athlete' : 'athletes') + '</small></div><div class="n">' +
      (attention.length ? attention.map(function (d) { return d.name + " (" + f1(d.v) + ")"; }).join(", ") : "None this session") + '</div></div>';

  /* distribution */
  document.getElementById("strip").innerHTML = BANDS.map(function (b, i) {
    return counts[i] ? '<div class="seg ' + b.key + '" style="--n:' + counts[i] + '" title="' + b.label + ': ' + counts[i] + '">' + counts[i] + '</div>' : "";
  }).join("");
  document.getElementById("legend").innerHTML = BANDS.map(function (b, i) {
    return '<li class="' + b.key + '"><span class="ct">' + counts[i] + '</span><b>' + b.label + '</b><span class="rg">' + b.range + '</span></li>';
  }).join("");

  /* ranked dot chart */
  var axLo = Math.min(30, Math.floor(vals[0] / 10) * 10);
  var axHi = Math.max(85, Math.ceil(vals[vals.length - 1] / 10) * 10);
  var pct = function (v) { return Math.max(0, Math.min(100, (v - axLo) / (axHi - axLo) * 100)); };
  var cuts = [50, 55, 65, 75].map(pct);
  var bg = "linear-gradient(90deg, var(--out-t) 0 " + cuts[0] + "%, var(--good-t) " + cuts[0] + "% " + cuts[1] +
    "%, var(--acc-t) " + cuts[1] + "% " + cuts[2] + "%, var(--mon-t) " + cuts[2] + "% " + cuts[3] + "%, var(--bad-t) " + cuts[3] + "% 100%)";
  var html = '<div class="raxis"><span></span><div class="ticks">' +
    [50, 55, 65, 75].map(function (c) { return '<span class="t' + c + '" style="left:' + pct(c) + '%">' + c + '</span>'; }).join("") +
    '</div><span class="unit">mm</span></div>';
  html += byVal.slice().reverse().map(function (d) {
    return '<div class="rrow ' + BANDS[d.band].key + '"><span class="rname" title="' + d.name + '">' + d.name + '</span>' +
      '<div class="rtrack" style="background:' + bg + '"><i style="left:' + pct(d.v) + '%" title="' + d.name + ': ' + f1(d.v) + ' mm, ' + BANDS[d.band].label + '"></i></div>' +
      '<span class="rval">' + f1(d.v) + '</span></div>';
  }).join("");
  document.getElementById("rank").innerHTML = html;

  /* table */
  var sortKey = "v", sortDir = -1;
  function renderRows() {
    var rows = data.slice().sort(function (a, b) {
      if (sortKey === "name") return a.raw.localeCompare(b.raw) * sortDir;
      var x = sortKey === "band" ? a.band : a.v, y = sortKey === "band" ? b.band : b.v;
      return (x - y) * sortDir || b.v - a.v || a.raw.localeCompare(b.raw);
    });
    document.getElementById("rows").innerHTML = rows.map(function (d) {
      return '<tr class="' + BANDS[d.band].key + '"><td class="name">' + d.name + '</td><td class="val r">' + f1(d.v) + '</td>' +
        '<td><span class="pill">' + BANDS[d.band].label + '</span></td></tr>';
    }).join("") + missing.map(function (d) {
      return '<tr class="na"><td class="name">' + d.name + '</td><td class="val r">–</td><td><span class="pill">Not measured</span></td></tr>';
    }).join("");
  }
  document.querySelectorAll("th[data-k]").forEach(function (th) {
    th.querySelector("button").addEventListener("click", function () {
      var k = th.getAttribute("data-k");
      sortDir = (sortKey === k) ? -sortDir : (k === "name" ? 1 : -1);
      sortKey = k;
      document.querySelectorAll("th[data-k]").forEach(function (o) { o.setAttribute("aria-sort", "none"); });
      th.setAttribute("aria-sort", sortDir === 1 ? "ascending" : "descending");
      renderRows();
    });
  });
  renderRows();
})();
</script>
<script>
/* Resize the embedding iframe to the content height (falls back to the fixed height Streamlit gives it). */
(function () {
  function fit() {
    try {
      var h = Math.ceil(document.body.getBoundingClientRect().height) + 2;
      if (window.frameElement) window.frameElement.style.height = h + "px";
    } catch (e) {}
  }
  window.addEventListener("load", fit);
  window.addEventListener("resize", fit);
  fit();
  setTimeout(fit, 400);
})();
</script>
</body></html>'''


def _norm(name: str) -> str:
    """'Skinfold Analysis - Sum of Skinfolds' -> 'skinfold_analysis_sum_of_skinfolds'."""
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")


def find_column(df: pd.DataFrame, candidates: list, contains: str = None):
    """First column whose normalised name matches a candidate (in order),
    else the first column whose normalised name contains `contains`."""
    by_norm = {_norm(c): c for c in df.columns}
    for cand in candidates:
        if cand in by_norm:
            return by_norm[cand]
    if contains:
        for n, c in by_norm.items():
            if contains in n:
                return c
    return None


SKINFOLD_COLUMN_NAME = "skinfold_analysis_sum_of_skinfolds"
PLAYER_COLUMN_CANDIDATES = ["player", "player_name", "athlete", "athlete_name", "name"]
DATE_COLUMN_CANDIDATES = [
    "screening_date", "session_date", "test_date", "assessment_date",
    "measurement_date", "date_of_screening", "date",
]


def build_skinfold_rows(day_df: pd.DataFrame, player_col: str, value_col: str) -> list:
    """[[name, sum_mm], ...] for one screening date.

    Rows with no skinfold value at all are skipped (that player wasn't
    measured on this date). A recorded 0 is kept: the dashboard flags it as
    "not measured". If a player has several rows on the date, the last one
    is used.
    """
    df = day_df[[player_col, value_col]].copy()
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df = df.dropna(subset=[player_col, value_col])
    df = df.drop_duplicates(subset=player_col, keep="last")
    return [[str(r[player_col]), round(float(r[value_col]), 1)] for _, r in df.iterrows()]


def build_skinfold_html(rows: list, meta: str) -> str:
    """Fill the template with one date's rows and a short date label."""

    def _js(value) -> str:
        # "</" would end the <script> block early, so escape it.
        return json.dumps(value).replace("</", "<\\/")

    return TEMPLATE.replace("__DATA__", _js(rows)).replace("__META__", _js(meta))
