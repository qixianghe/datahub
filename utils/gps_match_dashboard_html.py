"""GPS Match Dashboard (HTML version).

Used by the Performance > GPS Match Dashboard (c) page in app.py. Builds the
same content as the original Streamlit page (scoreline, team per-90 summary
with change vs all other matches, and the player-by-metric Team Overview with
the last 5 matches on hover) as one self-contained HTML page for
st.components.v1.html(). All maths reuses utils/gps_dashboard.py so the
numbers match the original page.
"""

import json
import zlib

import pandas as pd

from utils import gps_dashboard as gpsd

TEMPLATE = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GPS Match Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
  /* Layout: scoreline, per-90 team summary tiles, then a player-by-metric bar matrix (sortable, hover/tap for the last 5 matches). */
  :root {
    --bg: #EEF3F6; --surface: #FFFFFF; --ink: #13222B; --muted: #586873; --line: #D6E0E6; --accent: #0B6E8E;
    --good: #2A7B4C; --crit: #BE3A2B; --track: #E3EBEF; --bar-h: 208; --bar-s: 62%; --lo: #1F5FA8; --mid: #B26A00; --hi: #C62828; --on-bar: #FFFFFF;
    --f-display: "Barlow Condensed", "Arial Narrow", sans-serif;
    --f-body: "IBM Plex Sans", system-ui, sans-serif;
    --f-data: "IBM Plex Mono", ui-monospace, monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #0E181F; --surface: #15232C; --ink: #E5EDF1; --muted: #93A4AF; --line: #263A45; --accent: #52B9DA;
      --good: #5CC48A; --crit: #F27F70; --track: #20323C; --lo: #5AA6EE; --mid: #E3A33F; --hi: #F27F70; --on-bar: #0E181F; color-scheme: dark;
    }
  }
  :root[data-theme="dark"] {
    --bg: #0E181F; --surface: #15232C; --ink: #E5EDF1; --muted: #93A4AF; --line: #263A45; --accent: #52B9DA;
    --good: #5CC48A; --crit: #F27F70; --track: #20323C; --lo: #5AA6EE; --mid: #E3A33F; --hi: #F27F70; --on-bar: #0E181F; color-scheme: dark;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; }
  body { background: var(--bg); color: var(--ink); font-family: var(--f-body); font-size: 15px; line-height: 1.5; padding: 24px 16px 40px; }
  .wrap { max-width: 1280px; margin: 0 auto; display: flex; flex-direction: column; gap: 18px; }
  header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: end; gap: 6px 24px; }
  h1 { font-family: var(--f-display); font-weight: 700; font-size: 2.2rem; line-height: 1; margin: 0; letter-spacing: .01em; }
  h2 { font-family: var(--f-display); font-weight: 600; font-size: 1.2rem; letter-spacing: .04em; text-transform: uppercase; margin: 0; }
  .meta { font-family: var(--f-data); font-size: .8rem; color: var(--muted); }
  .sub { color: var(--muted); font-size: .85rem; margin: 2px 0 0; }
  .panel { background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 16px; min-width: 0; display: flex; flex-direction: column; gap: 12px; }

  /* scoreline */
  .comp { text-align: center; font-size: .72rem; letter-spacing: .16em; text-transform: uppercase; color: var(--muted); }
  .score { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: 10px 18px; }
  .team { display: flex; align-items: center; gap: 12px; min-width: 0; }
  .team.home { justify-content: flex-end; text-align: right; }
  .team .nm { font-family: var(--f-display); font-weight: 700; font-size: 1.7rem; line-height: 1.05; overflow-wrap: anywhere; }
  .badge { flex: none; width: 46px; height: 46px; display: inline-flex; align-items: center; justify-content: center; }
  .badge img { max-width: 46px; max-height: 46px; width: auto; height: auto; object-fit: contain; display: block; }
  .badge .ini { width: 46px; height: 46px; border-radius: 50%; color: #fff; font-weight: 700; font-size: 1.05rem; display: flex; align-items: center; justify-content: center; }
  .res { font-family: var(--f-display); font-weight: 700; font-size: 2.8rem; line-height: 1; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .res i { font-style: normal; color: var(--muted); padding: 0 .25em; }
  @media (max-width: 640px) {
    .score { grid-template-columns: 1fr; justify-items: center; }
    .team, .team.home { justify-content: center; text-align: center; }
    .team.home { order: 1; } .res { order: 2; } .team.away { order: 3; }
    .team .nm { font-size: 1.35rem; }
  }

  /* summary tiles */
  .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
  .tile { background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 12px 14px; min-width: 0; }
  .tile .k { font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
  .tile .v { font-family: var(--f-display); font-weight: 700; font-size: 2.3rem; line-height: 1.1; font-variant-numeric: tabular-nums; }
  .tile .v small { font-size: 1rem; color: var(--muted); font-weight: 500; }
  .tile .d { font-size: .85rem; font-weight: 600; font-variant-numeric: tabular-nums; }
  .tile .d.up { color: var(--good); } .tile .d.down { color: var(--crit); }
  .tile .d.none { color: var(--muted); font-weight: 400; }

  /* player x metric bar matrix */
  .scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .mx { display: grid; grid-template-columns: minmax(130px, 1.25fr) repeat(var(--nm), minmax(104px, 1fr)); min-width: calc(130px + var(--nm) * 104px); }
  .mx > div { min-width: 0; }
  .hd { position: sticky; top: 0; font-size: .7rem; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); padding: 0 6px 8px; border-bottom: 1px solid var(--line); background: var(--surface); text-align: center; }
  .hd.pl { text-align: left; left: 0; z-index: 3; padding-left: 4px; }
  .hd button { all: unset; cursor: pointer; display: inline-flex; gap: 4px; align-items: center; justify-content: center; }
  .hd button:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; border-radius: 2px; }
  .hd[aria-sort="ascending"] button::after { content: "\2191"; }
  .hd[aria-sort="descending"] button::after { content: "\2193"; }
  .pn { position: sticky; left: 0; z-index: 2; background: var(--surface); font-weight: 600; font-size: .88rem; padding: 0 8px 0 4px; display: flex; align-items: center; height: 30px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border-bottom: 1px solid var(--line); }
  .cl { height: 30px; padding: 4px 5px; border-bottom: 1px solid var(--line); }
  .bar { position: relative; height: 100%; border-radius: 0 4px 4px 0; background: transparent; cursor: default; }
  .bar b { position: absolute; left: 0; top: 0; bottom: 0; width: calc(var(--w) * 1%); min-width: 2px; border-radius: 0 4px 4px 0; background: hsl(var(--bar-h) var(--bar-s) calc(56% - var(--f) * 24%)); }
  .bar span { position: absolute; top: 50%; transform: translateY(-50%); font-family: var(--f-data); font-size: .76rem; font-weight: 500; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .bar.in span { left: 6px; color: #fff; font-weight: 600; }
  .bar.out span { left: calc(var(--w) * 1% + 4px); color: var(--ink); }
  .bar.lo b { background: var(--lo); } .bar.mid b { background: var(--mid); } .bar.hi b { background: var(--hi); }
  .bar.pm.in span { color: var(--on-bar); }
  .hd small { display: block; font-family: var(--f-data); font-size: .62rem; letter-spacing: 0; text-transform: none; margin-top: 1px; }
  .ctl { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; }
  .sw { display: inline-flex; align-items: center; gap: 10px; cursor: pointer; font-size: .88rem; font-weight: 500; user-select: none; }
  .sw input { position: absolute; opacity: 0; width: 0; height: 0; }
  .sw .tr { width: 42px; height: 24px; border-radius: 12px; background: var(--track); border: 1px solid var(--line); position: relative; transition: background .15s; flex: none; }
  .sw .tr::after { content: ""; position: absolute; top: 2px; left: 2px; width: 18px; height: 18px; border-radius: 50%; background: var(--muted); transition: transform .15s, background .15s; }
  .sw input:checked + .tr { background: var(--accent); border-color: var(--accent); }
  .sw input:checked + .tr::after { transform: translateX(18px); background: #fff; }
  .sw input:focus-visible + .tr { outline: 2px solid var(--accent); outline-offset: 2px; }
  .key { display: none; gap: 4px 14px; font-size: .78rem; color: var(--muted); }
  .key.on { display: flex; flex-wrap: wrap; }
  .key span::before { content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; background: var(--c); }
  .bar:hover b, .bar.sel b { outline: 2px solid var(--accent); outline-offset: 1px; }
  .rule { font-size: .8rem; color: var(--muted); margin: 0; }

  /* hover / tap tooltip with the last matches */
  #tip { position: fixed; z-index: 10; max-width: 270px; pointer-events: none; background: var(--ink); color: var(--bg); border-radius: 6px; padding: 8px 10px; font-size: .78rem; line-height: 1.35; box-shadow: 0 4px 14px rgba(0,0,0,.25); display: none; }
  #tip b { font-weight: 600; }
  #tip .tm { margin-top: 5px; padding-top: 5px; border-top: 1px solid rgba(255,255,255,.25); display: grid; grid-template-columns: 1fr auto; gap: 1px 12px; }
  #tip .tm .cur { font-weight: 600; }
  #tip .tm span:nth-child(even) { font-family: var(--f-data); text-align: right; }
</style>
</head><body>
<div class="wrap">
  <header>
    <div>
      <h1>GPS Match Dashboard</h1>
      <p class="sub" id="sub"></p>
    </div>
    <div class="meta" id="meta"></div>
  </header>

  <section class="panel" id="scorepanel" hidden>
    <div class="comp" id="comp"></div>
    <div class="score" id="score"></div>
  </section>

  <section>
    <h2>Team data summary</h2>
    <p class="sub" id="sumsub"></p>
    <div class="tiles" id="tiles" style="margin-top:10px"></div>
  </section>

  <section class="panel">
    <div>
      <h2>Team overview</h2>
      <p class="sub">Select a column heading to sort. Bars are scaled within each column. Hover or tap a bar to see the last matches.</p>
    </div>
    <div class="scroll"><div class="mx" id="mx"></div></div>
    <p class="rule" id="rule"></p>
    <div class="ctl">
      <label class="sw"><input type="checkbox" id="pm"><span class="tr"></span><span>Show per minute (&divide; game minutes)</span></label>
      <div class="key" id="key"><span style="--c:var(--lo)">Low</span><span style="--c:var(--mid)">Medium</span><span style="--c:var(--hi)">High</span><span>Cut-offs shown under each column heading</span></div>
    </div>
  </section>
</div>
<div id="tip" role="tooltip"></div>

<script>
(function () {
  var D = __DATA__;
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  var nf = function (v, dp) { return v.toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp }); };

  document.getElementById("meta").textContent = D.date || "";
  document.getElementById("sub").textContent = D.label || "";

  /* scoreline */
  function badge(t) {
    if (t.logo) return '<span class="badge"><img src="' + esc(t.logo) + '" alt="' + esc(t.initials) + '" data-i="' + esc(t.initials) + '" data-c="' + esc(t.color) + '"></span>';
    return '<span class="badge"><span class="ini" style="background:' + esc(t.color) + '">' + esc(t.initials) + '</span></span>';
  }
  if (D.match) {
    var m = D.match, sc = function (v) { return v === null ? "&ndash;" : v; };
    document.getElementById("scorepanel").hidden = false;
    document.getElementById("comp").textContent = m.competition || "";
    document.getElementById("score").innerHTML =
      '<div class="team home"><span class="nm">' + esc(m.home.name) + '</span>' + badge(m.home) + '</div>' +
      '<div class="res">' + sc(m.hs) + '<i>-</i>' + sc(m.as) + '</div>' +
      '<div class="team away">' + badge(m.away) + '<span class="nm">' + esc(m.away.name) + '</span></div>';
    document.querySelectorAll(".badge img").forEach(function (img) {
      img.addEventListener("error", function () {
        var s = document.createElement("span");
        s.className = "ini"; s.style.background = img.getAttribute("data-c"); s.textContent = img.getAttribute("data-i");
        img.replaceWith(s);
      });
    });
  }

  /* team per-90 summary */
  document.getElementById("sumsub").textContent = "Team per-90 rate" + (D.hasHist ? ", compared with all other matches." : ".");
  document.getElementById("tiles").innerHTML = D.summary.map(function (s) {
    var d = '<div class="d none">&nbsp;</div>';
    if (s.hist !== null && s.value !== null) {
      var diff = s.value - s.hist, pct = diff / s.hist * 100, up = diff >= 0;
      d = '<div class="d ' + (up ? "up" : "down") + '">' + (up ? "&#9650;" : "&#9660;") + " " + (diff >= 0 ? "+" : "") + nf(diff, 1) + " (" + (pct >= 0 ? "+" : "") + nf(pct, 1) + "%)</div>";
    }
    return '<div class="tile"><div class="k">' + esc(s.label) + '</div><div class="v">' + (s.value === null ? "&ndash;" : nf(s.value, 1)) + '<small>' + esc(s.unit) + '</small></div>' + d + '</div>';
  }).join("");

  /* matrix */
  var M = D.metrics, P = D.players, MI = D.minIdx;
  var perMin = false;
  var sortKey = D.sortKey, sortDir = -1;
  var mx = document.getElementById("mx");
  mx.style.setProperty("--nm", M.length);
  /* displayed value: per minute played for the five load metrics when the toggle is on */
  function val(p, i) {
    var v = p.v[i];
    if (v === null) return null;
    if (perMin && M[i].band) { var mins = p.v[MI]; return mins > 0 ? v / mins : null; }
    return v;
  }
  function level(m, v) { return v < m.band[0] ? "lo" : (v >= m.band[1] ? "hi" : "mid"); }
  function fmtVal(m, v) { return (perMin && m.band) ? nf(v, m.pdp) : (m.dp ? nf(v, 1) : String(Math.round(v))); }
  function render() {
    var max = M.map(function (m, i) {
      var v = P.map(function (p) { return val(p, i); }).filter(function (x) { return x !== null; });
      return v.length ? Math.max.apply(null, v) : 1;
    });
    var rows = P.map(function (p, i) { return i; }).sort(function (a, b) {
      var A = P[a], B = P[b];
      if (sortKey === -1) return A.name.localeCompare(B.name) * sortDir;
      var x = val(A, sortKey), y = val(B, sortKey);
      if (x === null && y === null) return A.name.localeCompare(B.name);
      if (x === null) return 1;
      if (y === null) return -1;
      return (x - y) * sortDir || A.name.localeCompare(B.name);
    });
    var h = '<div class="hd pl" data-k="-1" aria-sort="' + (sortKey === -1 ? (sortDir === 1 ? "ascending" : "descending") : "none") + '"><button type="button">Player</button></div>';
    M.forEach(function (m, i) {
      var pm = perMin && m.band;
      h += '<div class="hd" data-k="' + i + '" aria-sort="' + (sortKey === i ? (sortDir === 1 ? "ascending" : "descending") : "none") + '"><button type="button">' + esc(m.label) + (pm ? " /min" : "") + '</button>' +
        (pm ? '<small>&lt;' + m.band[0] + ' &middot; &ge;' + m.band[1] + '</small>' : "") + '</div>';
    });
    rows.forEach(function (pi) {
      var p = P[pi];
      h += '<div class="pn" title="' + esc(p.name) + '">' + esc(p.name) + '</div>';
      M.forEach(function (m, i) {
        var v = val(p, i);
        if (v === null) { h += '<div class="cl"></div>'; return; }
        var pm = perMin && m.band;
        var f = max[i] > 0 ? Math.max(0, Math.min(1, v / max[i])) : 0;
        var label = fmtVal(m, v);
        var inside = f >= Math.max(0.18, Math.min(0.75, label.length * 0.06));
        h += '<div class="cl"><div class="bar ' + (inside ? "in" : "out") + (pm ? " pm " + level(m, v) : "") + '" style="--w:' + (f * 100).toFixed(1) + ';--f:' + f.toFixed(3) + '" data-p="' + pi + '" data-m="' + i + '"><b></b><span>' + label + '</span></div></div>';
      });
    });
    mx.innerHTML = h;
  }
  render();
  mx.addEventListener("click", function (e) {
    var th = e.target.closest(".hd");
    if (!th) return;
    var k = Number(th.getAttribute("data-k"));
    sortDir = (sortKey === k) ? -sortDir : (k === -1 ? 1 : -1);
    sortKey = k;
    render();
  });
  var baseRule = "Sorted by " + (sortKey >= 0 ? M[sortKey].label : "player") + " by default, highest to lowest. Players with no recorded Total Distance in this match are left out.";
  document.getElementById("rule").textContent = baseRule;
  document.getElementById("pm").addEventListener("change", function (e) {
    perMin = e.target.checked;
    document.getElementById("key").classList.toggle("on", perMin);
    document.getElementById("rule").textContent = baseRule + (perMin ? " Total Distance, High Speed Running, Sprint Distance, High Intensity Actions and High Intensity Distance are per minute played." : "");
    hide();
    render();
  });

  /* tooltip: hover on desktop, tap on touch */
  var tip = document.getElementById("tip"), selEl = null;
  function tipHtml(bar) {
    var p = P[bar.getAttribute("data-p")], i = Number(bar.getAttribute("data-m")), m = M[i];
    var pm = perMin && m.band, v = val(p, i);
    var h = "<b>" + esc(p.name) + "</b> &middot; " + esc(m.label) + "<br>" + (pm ? nf(v, m.pdp) : (m.dp ? nf(v, 1) : nf(v, 0))) + (pm ? " " + esc(m.punit) : (m.unit ? " " + esc(m.unit) : ""));
    if (D.window.length > 1 && p.h) {
      h += '<div class="tm">' + D.window.map(function (w, j) {
        var raw = p.h[i][j], t = "—";
        if (raw !== null) {
          if (pm) { t = p.hm[j] > 0 ? nf(raw / p.hm[j], m.pdp) : "—"; }
          else { t = m.dp ? nf(raw, 1) : String(Math.round(raw)); }
        }
        return '<span class="' + (j === 0 ? "cur" : "") + '">' + esc(w) + '</span><span class="' + (j === 0 ? "cur" : "") + '">' + t + '</span>';
      }).join("") + "</div>";
    }
    return h;
  }
  function place(x, y) {
    tip.style.display = "block";
    var w = tip.offsetWidth, h = tip.offsetHeight, vw = window.innerWidth, vh = window.innerHeight;
    var left = x + 14, top = y + 14;
    if (left + w > vw - 6) left = Math.max(6, x - w - 14);
    if (top + h > vh - 6) top = Math.max(6, y - h - 14);
    tip.style.left = left + "px"; tip.style.top = top + "px";
  }
  function hide() { tip.style.display = "none"; if (selEl) { selEl.classList.remove("sel"); selEl = null; } }
  mx.addEventListener("mousemove", function (e) {
    var b = e.target.closest(".bar");
    if (!b) { tip.style.display = "none"; return; }
    tip.innerHTML = tipHtml(b); place(e.clientX, e.clientY);
  });
  mx.addEventListener("mouseleave", function () { tip.style.display = "none"; });
  mx.addEventListener("click", function (e) {
    var b = e.target.closest(".bar");
    if (!b) { hide(); return; }
    if (selEl === b) { hide(); return; }
    hide(); selEl = b; b.classList.add("sel");
    tip.innerHTML = tipHtml(b); place(e.clientX, e.clientY);
  });
  document.addEventListener("click", function (e) { if (!e.target.closest(".mx")) hide(); });
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

# metric column -> (unit shown next to the value, decimal places on bars)
_METRIC_UNITS = {
    "Total Distance (m)": ("m", 0),
    "High Speed Running (m)": ("m", 0),
    "Sprint Distance (m)": ("m", 0),
    "High Intensity Actions": ("", 0),
    "High Intensity Distance (m)": ("m", 0),
    "Max Speed (km/h)": ("km/h", 1),
    "Game Minutes (mins)": ("min", 0),
}


def _num(v):
    """float or None (NaN/None -> None) so the value is JSON-safe."""
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _team_info(name) -> dict:
    name = str(name)
    return {
        "name": name,
        "logo": gpsd._team_logo_url(name),
        "initials": gpsd._team_initials(name),
        "color": gpsd.BADGE_PALETTE[zlib.crc32(name.encode()) % len(gpsd.BADGE_PALETTE)],
    }


def build_gps_match_payload(
    selected_df, raw, match_order_desc, selected_label, has_multiple_matches, per_min_bands=None
) -> dict:
    """Everything the HTML page needs for one match.

    selected_df: rows of the chosen match; raw: all matches for the team
    (both already renamed to gps_dashboard column names, with the match
    label column added by gpsd.build_match_labels).

    per_min_bands: optional {gps_dashboard column: (low_upper, high_lower)} for
    the load metrics that get a per-minute view; value < low_upper is Low,
    value >= high_lower is High, otherwise Medium.
    """
    per_min_bands = per_min_bands or {}
    # ---- header / scoreline ----
    first = selected_df.iloc[0]
    date_text = ""
    if "Match Date" in selected_df.columns:
        date_text = str(gpsd._display_date(pd.Series([first.get("Match Date")])).iloc[0])

    match = None
    if all(c in first.index for c in gpsd.MATCH_INFO_COLUMNS) and pd.notna(first.get("Home Team")):
        hs, as_ = first.get("Home Team Score"), first.get("Away Team Score")
        comp = first.get("Competition")
        match = {
            "competition": None if pd.isna(comp) else str(comp),
            "home": _team_info(first["Home Team"]),
            "away": _team_info(first["Away Team"]),
            "hs": None if pd.isna(hs) else int(hs),
            "as": None if pd.isna(as_) else int(as_),
        }

    # ---- team per-90 summary (selected match vs all other matches) ----
    historical_df = (
        raw[raw[gpsd.MATCH_LABEL_COL] != selected_label] if has_multiple_matches else None
    )
    has_hist = historical_df is not None and not historical_df.empty
    summary = []
    for metric in gpsd.SUMMARY_METRICS:
        value = _num(gpsd.team_per90(selected_df, metric))
        hist = _num(gpsd.team_per90(historical_df, metric)) if has_hist else None
        if not hist:  # None or 0 -> no comparison (can't take a % of 0)
            hist = None
        summary.append(
            {
                "label": gpsd.METRIC_LABELS[metric],
                "value": value,
                "hist": hist,
                "unit": "" if metric == "High Intensity Actions" else " m",
            }
        )

    # ---- player overview (same rules as gpsd.render_matrix_chart) ----
    df = selected_df
    if "Total Distance (m)" in df.columns:
        df = df[df["Total Distance (m)"].fillna(0) != 0]
    df = df.sort_values("Game Minutes (mins)", ascending=False)

    if selected_label in match_order_desc:
        idx = match_order_desc.index(selected_label)
        window = match_order_desc[idx: idx + 5]
    else:
        window = [selected_label]

    metrics_cols = list(gpsd.METRIC_COLUMNS)
    hist_lookup = {}
    if len(window) > 1:
        hist_rows = raw[
            raw["Player Name"].isin(df["Player Name"].unique())
            & raw[gpsd.MATCH_LABEL_COL].isin(window)
        ]
        for _, r in hist_rows.drop_duplicates(subset=["Player Name", gpsd.MATCH_LABEL_COL]).iterrows():
            hist_lookup[(r["Player Name"], r[gpsd.MATCH_LABEL_COL])] = r

    players = []
    for _, row in df.iterrows():
        entry = {"name": str(row["Player Name"]), "v": [_num(row.get(c)) for c in metrics_cols]}
        if len(window) > 1:
            # raw numbers (None = no data); the page formats them so it can
            # also divide by the minutes for the per-minute view
            def _hv(w, c):
                r = hist_lookup.get((row["Player Name"], w))
                return None if r is None else _num(r[c])

            entry["h"] = [[_hv(w, c) for w in window] for c in metrics_cols]
            entry["hm"] = [_hv(w, "Game Minutes (mins)") for w in window]
        players.append(entry)

    metrics = []
    for c in metrics_cols:
        unit, dp = _METRIC_UNITS.get(c, ("", 0))
        band = per_min_bands.get(c)
        metrics.append(
            {
                "label": gpsd.METRIC_LABELS[c],
                "unit": unit,
                "dp": dp,
                "band": list(band) if band else None,
                "pdp": 1 if c == "Total Distance (m)" else 2,
                "punit": "m/min" if unit == "m" else "/min",
            }
        )

    return {
        "label": str(selected_label),
        "date": date_text,
        "match": match,
        "summary": summary,
        "hasHist": has_hist,
        "metrics": metrics,
        "sortKey": metrics_cols.index("Game Minutes (mins)"),
        "minIdx": metrics_cols.index("Game Minutes (mins)"),
        "window": [str(w) for w in window],
        "players": players,
    }


def build_gps_match_html(payload: dict) -> str:
    """Fill the template with one match's payload."""
    # "</" would end the <script> block early, so escape it.
    return TEMPLATE.replace("__DATA__", json.dumps(payload).replace("</", "<\\/"))