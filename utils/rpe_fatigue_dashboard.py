"""Squad Load and Recovery (RPE & Fatigue) dashboard.

Used by the Performance > View RPE & Fatigue page in app.py. The HTML/CSS/JS
below is a self-contained page; build_rpe_fatigue_html() fills in the data
for one session and returns the HTML to hand to st.components.v1.html().

Source columns in gps_session_data:
  rpe -> session RPE (0-10, higher = harder session)
  rps -> the "fatigue" score, shown as Recovery (0-10, higher = better recovered)
"""

import json

import pandas as pd

TEMPLATE = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Squad Load and Recovery</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
  /* Layout: summary tiles first, then a load-vs-recovery scatter beside a sortable athlete table, scale reference last. */
  :root {
    --bg: #EEF3F6;
    --surface: #FFFFFF;
    --ink: #13222B;
    --muted: #586873;
    --line: #D6E0E6;
    --accent: #0B6E8E;
    --good: #2A7B4C;
    --warn: #A86A0E;
    --crit: #BE3A2B;
    --good-tint: #E1F1E8;
    --warn-tint: #F8EBD2;
    --crit-tint: #F9E1DD;
    --track: #E3EBEF;
    --tint-s: 55%; --tint-l: 91%; --edge-l: 60%; --val-l: 27%;
    --f-display: "Barlow Condensed", "Arial Narrow", sans-serif;
    --f-body: "IBM Plex Sans", system-ui, sans-serif;
    --f-data: "IBM Plex Mono", ui-monospace, monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #0E181F; --surface: #15232C; --ink: #E5EDF1; --muted: #93A4AF; --line: #263A45;
      --accent: #52B9DA; --good: #5CC48A; --warn: #E3AC4F; --crit: #F27F70;
      --good-tint: #17352A; --warn-tint: #3A2D14; --crit-tint: #3D1F1B; --track: #20323C;
      --tint-l: 19%; --edge-l: 40%; --val-l: 72%;
      color-scheme: dark;
    }
  }
  :root[data-theme="dark"] {
    --bg: #0E181F; --surface: #15232C; --ink: #E5EDF1; --muted: #93A4AF; --line: #263A45;
    --accent: #52B9DA; --good: #5CC48A; --warn: #E3AC4F; --crit: #F27F70;
    --good-tint: #17352A; --warn-tint: #3A2D14; --crit-tint: #3D1F1B; --track: #20323C;
    --tint-l: 19%; --edge-l: 40%; --val-l: 72%;
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
  .tile.scaled { background: hsl(var(--h) var(--tint-s) var(--tint-l)); border-color: hsl(var(--h) var(--tint-s) var(--edge-l)); }
  .tile.scaled .v { color: hsl(var(--h) 70% var(--val-l)); }
  .meter { position: relative; height: 8px; border-radius: 4px; margin: 10px 0 4px; }
  .meter.g2r { background: linear-gradient(90deg, hsl(120 55% 42%), hsl(60 65% 46%), hsl(0 65% 50%)); }
  .meter.r2g { background: linear-gradient(90deg, hsl(0 65% 50%), hsl(60 65% 46%), hsl(120 55% 42%)); }
  .meter b { position: absolute; top: -4px; width: 4px; height: 16px; margin-left: -2px; border-radius: 2px; background: var(--ink); border: 1px solid var(--surface); }
  .meter-ends { display: flex; justify-content: space-between; font-family: var(--f-data); font-size: .7rem; color: var(--muted); margin-bottom: 6px; }
  .tile.alert { background: var(--crit-tint); border-color: var(--crit); }
  .tile.alert .v { color: var(--crit); }

  .grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 20px; }
  @media (min-width: 980px) { .grid { grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); } }
  .panel { background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 18px; min-width: 0; display: flex; flex-direction: column; gap: 14px; }

  svg.chart { width: 100%; height: auto; display: block; }
  .chart text { font-family: var(--f-data); font-size: 11px; fill: var(--muted); }
  .chart .lbl { font-family: var(--f-body); font-size: 12.5px; font-weight: 600; fill: var(--ink); }
  .chart .axis { stroke: var(--line); stroke-width: 1; }
  .chart .grid-l { stroke: var(--line); stroke-width: 1; stroke-dasharray: 2 4; }
  .chart .zone { fill: var(--crit-tint); }
  .chart .zone-t { fill: var(--crit); font-weight: 500; }
  .chart .dot-n { fill: var(--surface); font-weight: 600; font-size: 11px; text-anchor: middle; }
  .chart .ax-t { font-size: 11.5px; fill: var(--ink); }

  .table-scroll { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; min-width: 560px; }
  th { text-align: left; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); font-weight: 500; padding: 0 10px 8px; border-bottom: 1px solid var(--line); white-space: nowrap; }
  th button { all: unset; cursor: pointer; display: inline-flex; gap: 4px; align-items: center; }
  th button:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; border-radius: 2px; }
  th[aria-sort="ascending"] button::after { content: "\2191"; }
  th[aria-sort="descending"] button::after { content: "\2193"; }
  td { padding: 10px; border-bottom: 1px solid var(--line); vertical-align: middle; }
  tr:last-child td { border-bottom: 0; }
  td.name { font-weight: 600; }
  .cell { display: grid; grid-template-columns: 2ch 1fr; gap: 2px 10px; align-items: center; min-width: 150px; }
  .num { font-family: var(--f-display); font-weight: 700; font-size: 1.35rem; line-height: 1; font-variant-numeric: tabular-nums; text-align: right; }
  .bar { height: 8px; background: var(--track); border-radius: 4px; overflow: hidden; }
  .bar i { display: block; height: 100%; border-radius: 4px; }
  .desc { grid-column: 2; font-size: .75rem; color: var(--muted); line-height: 1.25; }
  .pill { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font-size: .78rem; font-weight: 600; white-space: nowrap; }
  .pill::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
  .pill.good { background: var(--good-tint); color: var(--good); }
  .pill.warn { background: var(--warn-tint); color: var(--warn); }
  .pill.crit, .pill.caut { background: var(--crit-tint); color: var(--crit); }
  .rule { font-size: .8rem; color: var(--muted); margin: 0; }

  .scales { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 20px; }
  .scale { display: grid; grid-template-columns: 3ch 1fr; gap: 4px 12px; font-size: .88rem; margin: 0; }
  .scale dt { font-family: var(--f-data); color: var(--muted); text-align: right; }
  .scale dd { margin: 0; }
  .scale dd.empty { color: var(--muted); }
  .scale h3 { grid-column: 1 / -1; font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin: 0 0 4px; font-weight: 500; }
  @media (prefers-reduced-motion: no-preference) { .bar i { transition: width .4s ease; } }
</style>
</head><body>
<div class="wrap">
  <header>
    <div>
      <h1>Squad Load and Recovery</h1>
      <p class="sub" id="sub"></p>
    </div>
    <div class="meta" id="meta"></div>
  </header>

  <section class="tiles" id="tiles" aria-label="Squad summary"></section>

  <section class="grid">
    <div class="panel">
      <div>
        <h2>Load vs recovery</h2>
        <p class="sub">Right means harder session. Up means better recovered.</p>
      </div>
      <svg class="chart" id="chart" viewBox="0 0 640 390" role="img" aria-labelledby="chart-d"></svg>
      <p class="rule" id="chart-d"></p>
    </div>

    <div class="panel">
      <div>
        <h2>Athletes</h2>
        <p class="sub">Select a column heading to sort. Lowest recovery first by default.</p>
      </div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th data-k="name" aria-sort="none"><button type="button">Athlete</button></th>
              <th data-k="rpe" aria-sort="none"><button type="button">RPE</button></th>
              <th data-k="rec" aria-sort="ascending"><button type="button">Recovery</button></th>
              <th data-k="sev" aria-sort="none"><button type="button">Status</button></th>
            </tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
      <p class="rule">Status rule: recovery 3 or below is <b>Low recovery</b>. Recovery 4 to 5 after an RPE of 9 or more is <b>Caution</b>. Recovery 4 to 5 at any lower RPE is <b>Monitor</b>. Everything else is <b>Good to go</b>.</p>
    </div>
  </section>

  <section class="panel">
    <h2>Score reference</h2>
    <div class="scales">
      <dl class="scale" id="rpe-scale"></dl>
      <dl class="scale" id="rec-scale"></dl>
    </div>
    <p class="rule">Recovery is the original Fatigue column. 0 is extremely tired and 10 is very well recovered, so a higher number is better. Scores with no label in your scale sheet show the two labels around them.</p>
  </section>
</div>
<script>
(function () {
  var data = __DATA__;
  var META = __META__;
  var RPE = { 0: "Rest", 1: "Very, very easy", 2: "Easy", 3: "Moderate", 4: "Somewhat hard", 5: "Hard", 7: "Very hard", 10: "Maximal" };
  var REC = { 0: "Extremely tired", 2: "Somewhat tired", 4: "Somewhat recovered", 5: "Adequately recovered", 6: "Moderately recovered", 8: "Well recovered", 10: "Very well recovered" };

  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function fmt(v) { return Number.isInteger(v) ? String(v) : v.toFixed(1); }
  function label(map, v) {
    v = Math.max(0, Math.min(10, Math.round(v)));
    if (map[v] !== undefined) return map[v];
    var lo = v, hi = v;
    while (map[lo] === undefined) lo--;
    while (map[hi] === undefined) hi++;
    return "Between " + map[lo].toLowerCase() + " and " + map[hi].toLowerCase();
  }
  var STATUS = {
    crit: { text: "Low recovery", sev: 0, color: "var(--crit)" },
    caut: { text: "Caution", sev: 1, color: "var(--crit)" },
    warn: { text: "Monitor", sev: 2, color: "var(--warn)" },
    good: { text: "Good to go", sev: 3, color: "var(--good)" }
  };
  data.forEach(function (d) {
    d.st = d.rec <= 3 ? "crit" : (d.rec <= 5 ? (d.rpe >= 9 ? "caut" : "warn") : "good");
    d.sev = STATUS[d.st].sev;
  });

  document.getElementById("sub").textContent =
    "Session RPE against recovery score, " + data.length + " athlete" + (data.length === 1 ? "" : "s");
  document.getElementById("meta").textContent = META;

  var avg = function (k) { return data.reduce(function (s, d) { return s + d[k]; }, 0) / data.length; };
  var avgRpe = avg("rpe"), avgRec = avg("rec");
  var crits = data.filter(function (d) { return d.st === "crit"; });
  var cauts = data.filter(function (d) { return d.st === "caut"; });
  var warns = data.filter(function (d) { return d.st === "warn"; });

  document.getElementById("tiles").innerHTML =
    '<div class="tile scaled" style="--h:' + Math.round(120 * (1 - avgRpe / 10)) + '"><div class="k">Average RPE</div><div class="v">' + avgRpe.toFixed(1) + '<small> / 10</small></div>' +
      '<div class="meter g2r"><b style="left:' + avgRpe * 10 + '%"></b></div><div class="meter-ends"><span>0 rest</span><span>10 maximal</span></div>' +
      '<div class="n">' + label(RPE, avgRpe).toLowerCase().replace("between", "Between") + '</div></div>' +
    '<div class="tile scaled" style="--h:' + Math.round(120 * avgRec / 10) + '"><div class="k">Average recovery</div><div class="v">' + avgRec.toFixed(1) + '<small> / 10</small></div>' +
      '<div class="meter r2g"><b style="left:' + avgRec * 10 + '%"></b></div><div class="meter-ends"><span>0 tired</span><span>10 recovered</span></div>' +
      '<div class="n">' + label(REC, avgRec).toLowerCase().replace("between", "Between") + '</div></div>' +
    '<div class="tile alert"><div class="k">Low recovery</div><div class="v">' + crits.length + '<small> ' + (crits.length === 1 ? 'athlete' : 'athletes') + '</small></div><div class="n">' +
      (crits.length ? crits.map(function (d) { return esc(d.name) + " (" + fmt(d.rec) + ")"; }).join(", ") : "None") + '</div></div>' +
    '<div class="tile alert"><div class="k">Caution</div><div class="v">' + cauts.length + '<small> ' + (cauts.length === 1 ? 'athlete' : 'athletes') + '</small></div><div class="n">' +
      (cauts.length ? cauts.map(function (d) { return esc(d.name) + " (RPE " + fmt(d.rpe) + ", rec " + fmt(d.rec) + ")"; }).join(", ") : "None") + '</div></div>' +
    '<div class="tile"><div class="k">To monitor</div><div class="v">' + warns.length + '<small> ' + (warns.length === 1 ? 'athlete' : 'athletes') + '</small></div><div class="n">' +
      (warns.length ? warns.map(function (d) { return esc(d.name); }).join(", ") + ' (recovery 4 to 5)' : "None") + '</div></div>';

  /* table */
  var sortKey = "rec", sortDir = 1;
  function renderRows() {
    var rows = data.slice().sort(function (a, b) {
      var x = a[sortKey], y = b[sortKey];
      if (typeof x === "string") return x.localeCompare(y) * sortDir;
      return (x - y) * sortDir || a.name.localeCompare(b.name);
    });
    document.getElementById("rows").innerHTML = rows.map(function (d) {
      var st = STATUS[d.st];
      return '<tr><td class="name">' + esc(d.name) + '</td>' +
        '<td><div class="cell"><span class="num">' + fmt(d.rpe) + '</span><div class="bar"><i style="width:' + d.rpe * 10 + '%;background:var(--accent)"></i></div><span class="desc">' + label(RPE, d.rpe) + '</span></div></td>' +
        '<td><div class="cell"><span class="num">' + fmt(d.rec) + '</span><div class="bar"><i style="width:' + d.rec * 10 + '%;background:' + st.color + '"></i></div><span class="desc">' + label(REC, d.rec) + '</span></div></td>' +
        '<td><span class="pill ' + d.st + '">' + st.text + '</span></td></tr>';
    }).join("");
  }
  document.querySelectorAll("th[data-k]").forEach(function (th) {
    th.querySelector("button").addEventListener("click", function () {
      var k = th.getAttribute("data-k");
      sortDir = (sortKey === k) ? -sortDir : (k === "rpe" ? -1 : 1);
      sortKey = k;
      document.querySelectorAll("th[data-k]").forEach(function (o) { o.setAttribute("aria-sort", "none"); });
      th.setAttribute("aria-sort", sortDir === 1 ? "ascending" : "descending");
      renderRows();
    });
  });
  renderRows();

  /* chart: x range follows the data (at least 4 units wide, within 0-10) */
  var lo = Math.max(0, Math.floor(Math.min.apply(null, data.map(function (d) { return d.rpe; }))));
  var hi = Math.min(10, Math.ceil(Math.max.apply(null, data.map(function (d) { return d.rpe; }))));
  while (hi - lo < 3) { if (hi < 10) hi++; else if (lo > 0) lo--; else break; if (hi - lo < 3 && lo > 0) lo--; }
  var W = 640, H = 390, L = 48, R = 24, T = 14, B = 48;
  var x0 = lo - 0.5, x1 = hi + 0.5;
  var sx = function (v) { return L + (v - x0) / (x1 - x0) * (W - L - R); };
  var sy = function (v) { return H - B - v / 10 * (H - T - B); };
  var s = "";
  s += '<rect class="zone" x="' + L + '" y="' + sy(3) + '" width="' + (W - L - R) + '" height="' + (sy(0) - sy(3)) + '"></rect>';
  s += '<text class="zone-t" x="' + (L + 8) + '" y="' + (sy(3) + 16) + '">Low recovery zone (0 to 3)</text>';
  [0, 2, 4, 6, 8, 10].forEach(function (v) {
    s += '<line class="grid-l" x1="' + L + '" x2="' + (W - R) + '" y1="' + sy(v) + '" y2="' + sy(v) + '"></line>';
    s += '<text x="' + (L - 8) + '" y="' + (sy(v) + 4) + '" text-anchor="end">' + v + '</text>';
  });
  for (var t = lo; t <= hi; t++) {
    s += '<line class="axis" x1="' + sx(t) + '" x2="' + sx(t) + '" y1="' + (H - B) + '" y2="' + (H - B + 5) + '"></line>';
    s += '<text x="' + sx(t) + '" y="' + (H - B + 19) + '" text-anchor="middle">' + t + '</text>';
  }
  s += '<line class="axis" x1="' + L + '" x2="' + (W - R) + '" y1="' + (H - B) + '" y2="' + (H - B) + '"></line>';
  s += '<line class="axis" x1="' + L + '" x2="' + L + '" y1="' + T + '" y2="' + (H - B) + '"></line>';
  s += '<text class="ax-t" x="' + ((L + W - R) / 2) + '" y="' + (H - 8) + '" text-anchor="middle">RPE (session load)</text>';
  s += '<text class="ax-t" transform="translate(13 ' + ((T + H - B) / 2) + ') rotate(-90)" text-anchor="middle">Recovery</text>';

  var groups = {};
  data.forEach(function (d) { var k = d.rpe + "," + d.rec; (groups[k] = groups[k] || []).push(d); });
  var shared = [];
  Object.keys(groups).forEach(function (k) {
    var g = groups[k], d = g[0], cx = sx(d.rpe), cy = sy(d.rec), st = STATUS[d.st];
    var names = g.map(function (m) { return esc(m.name); });
    var left = d.rpe >= hi;
    if (g.length > 1) shared.push(g.map(function (m) { return m.name; }).join(" and ") + " share the same scores (RPE " + fmt(d.rpe) + ", recovery " + fmt(d.rec) + ").");
    s += '<g><title>' + names.join(", ") + ': RPE ' + fmt(d.rpe) + ', recovery ' + fmt(d.rec) + ' (' + st.text + ')</title>' +
      '<circle cx="' + cx + '" cy="' + cy + '" r="' + (g.length > 1 ? 11 : 9) + '" fill="' + st.color + '" stroke="var(--surface)" stroke-width="2"></circle>' +
      (g.length > 1 ? '<text class="dot-n" x="' + cx + '" y="' + (cy + 4) + '">' + g.length + '</text>' : '') +
      '<text class="lbl" x="' + (left ? cx - 16 : cx + 16) + '" y="' + (cy + 4) + '" text-anchor="' + (left ? "end" : "start") + '">' + names.join(" + ") + '</text></g>';
  });
  document.getElementById("chart").innerHTML = s;
  document.getElementById("chart-d").textContent =
    "Dot colour matches status: dark red is low recovery or caution, amber is monitor, green is good to go." + (shared.length ? " " + shared.join(" ") : "");

  /* scale reference */
  function scaleHtml(title, map) {
    var h = '<h3>' + title + '</h3>';
    for (var i = 0; i <= 10; i++) {
      h += '<dt>' + i + '</dt>' + (map[i] !== undefined ? '<dd>' + map[i] + '</dd>' : '<dd class="empty">no label</dd>');
    }
    return h;
  }
  document.getElementById("rpe-scale").innerHTML = scaleHtml("RPE", RPE);
  document.getElementById("rec-scale").innerHTML = scaleHtml("Recovery (Fatigue column)", REC);
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


def build_rpe_rows(session_df: pd.DataFrame) -> list:
    """[{'name', 'rpe', 'rec'}, ...] from one session's gps_session_data rows.

    Players with no rpe or rps value are skipped. If a player has more than
    one row for the session, their scores are averaged.
    """
    if session_df.empty or not {"player", "rpe", "rps"} <= set(session_df.columns):
        return []
    df = session_df[["player", "rpe", "rps"]].copy()
    df["rpe"] = pd.to_numeric(df["rpe"], errors="coerce")
    df["rps"] = pd.to_numeric(df["rps"], errors="coerce")
    df = df.dropna(subset=["player", "rpe", "rps"])
    df = df.groupby("player", as_index=False)[["rpe", "rps"]].mean()
    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "name": str(r["player"]),
                "rpe": round(float(r["rpe"]), 1),
                "rec": round(float(r["rps"]), 1),
            }
        )
    return rows


def build_rpe_fatigue_html(rows: list, meta: str) -> str:
    """Fill the template with one session's rows and a header line."""

    def _js(value) -> str:
        # "</" would end the <script> block early, so escape it.
        return json.dumps(value).replace("</", "<\\/")

    return TEMPLATE.replace("__DATA__", _js(rows)).replace("__META__", _js(meta))
