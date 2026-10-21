"""Squad Availability ("Player Overview") dashboard.

Used by the Medical > Player Overview page in app.py. A compact, phone-sized
page: counts of available goalkeepers / outfield players on top, then one
row per player (position, name, availability) shaded by availability.
build_overview_html() fills the template and returns HTML for
st.components.v1.html().
"""

import json

TEMPLATE = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Squad Availability</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
  /* Layout: two availability counts on top, then one compact Position / Player / Availability list, built to fit a single phone screen. */
  :root {
    --bg: #EEF3F6; --surface: #FFFFFF; --ink: #13222B; --muted: #586873; --line: #D6E0E6; --accent: #0B6E8E;
    --good: #2A7B4C; --attn: #1E6A3F; --warn: #A86A0E; --crit: #BE3A2B; --na: #586873;
    --good-tint: #E1F1E8; --attn-tint: #C9E6D4; --warn-tint: #F8EBD2; --crit-tint: #F9E1DD; --na-tint: #E3EBEF;
    --f-display: "Barlow Condensed", "Arial Narrow", sans-serif;
    --f-body: "IBM Plex Sans", system-ui, sans-serif;
    --f-data: "IBM Plex Mono", ui-monospace, monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #0E181F; --surface: #15232C; --ink: #E5EDF1; --muted: #93A4AF; --line: #263A45; --accent: #52B9DA;
      --good: #5CC48A; --attn: #7FD8A4; --warn: #E3AC4F; --crit: #F27F70; --na: #93A4AF;
      --good-tint: #17352A; --attn-tint: #1F4A36; --warn-tint: #3A2D14; --crit-tint: #3D1F1B; --na-tint: #20323C;
      color-scheme: dark;
    }
  }
  :root[data-theme="dark"] {
    --bg: #0E181F; --surface: #15232C; --ink: #E5EDF1; --muted: #93A4AF; --line: #263A45; --accent: #52B9DA;
    --good: #5CC48A; --attn: #7FD8A4; --warn: #E3AC4F; --crit: #F27F70; --na: #93A4AF;
    --good-tint: #17352A; --attn-tint: #1F4A36; --warn-tint: #3A2D14; --crit-tint: #3D1F1B; --na-tint: #20323C;
    color-scheme: dark;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; }
  body { background: var(--bg); color: var(--ink); font-family: var(--f-body); font-size: 14px; line-height: 1.3; padding: 12px 12px 14px; }
  .wrap { max-width: 520px; margin: 0 auto; display: flex; flex-direction: column; gap: 10px; }
  header { display: flex; justify-content: space-between; align-items: end; gap: 8px; }
  h1 { font-family: var(--f-display); font-weight: 700; font-size: 1.75rem; line-height: 1; margin: 0; letter-spacing: .01em; }
  .meta { font-family: var(--f-data); font-size: .68rem; color: var(--muted); text-align: right; white-space: nowrap; }

  .tiles { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .tile { background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 8px 12px; min-width: 0; }
  .tile .k { font-size: .66rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
  .tile .v { font-family: var(--f-display); font-weight: 700; font-size: 2.1rem; line-height: 1.05; font-variant-numeric: tabular-nums; }
  .tile .v small { font-size: .95rem; color: var(--muted); font-weight: 500; }
  .tile .v .plus { font-family: var(--f-body); font-size: .72rem; font-weight: 600; color: var(--warn); margin-left: 8px; white-space: nowrap; }
  .tile .v .plus.zero { color: var(--muted); font-weight: 500; }
  .tile.ok .v { color: var(--good); }
  .tile.some .v { color: var(--warn); }
  .tile.none .v { color: var(--crit); }

  .panel { background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 6px 8px 8px; }
  .panel { font-size: var(--fs, .85rem); }
  .row { display: grid; grid-template-columns: 5.6em minmax(0, 1fr) 9.8em; align-items: center; gap: 6px; padding: 0 8px; border-left: 4px solid transparent; }
  .row.head span { font-size: .66em; }
  .row.head { letter-spacing: .06em; text-transform: uppercase; color: var(--muted); padding-bottom: 5px; border-bottom: 1px solid var(--line); margin-bottom: 4px; }
  #rows { display: flex; flex-direction: column; gap: 2px; }
  .row.p { height: var(--rh, 26px); background: var(--t); border-left: 4px solid var(--c); border-radius: 3px; }
  .row.p .pos { font-size: .8em; color: var(--muted); font-weight: 500; white-space: nowrap; }
  .row.p .nm { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .row.p .st { font-size: .8em; font-weight: 600; color: var(--c); white-space: nowrap; display: flex; align-items: center; gap: 5px; }
  .row.p .st::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: currentColor; flex: none; }
  .s-avail { --c: var(--good); --t: var(--good-tint); }
  .s-attn { --c: var(--attn); --t: var(--attn-tint); }
  .s-mod { --c: var(--warn); --t: var(--warn-tint); }
  .s-un { --c: var(--crit); --t: var(--crit-tint); }
  .s-na { --c: var(--na); --t: var(--na-tint); }
  .empty { padding: 14px 8px; color: var(--muted); font-size: .85rem; }
</style>
</head><body>
<div class="wrap">
  <header>
    <h1>Squad Availability</h1>
    <div class="meta" id="meta"></div>
  </header>

  <section class="tiles" id="tiles" aria-label="Available players"></section>

  <section class="panel" aria-label="Player availability">
    <div class="row head"><span>Position</span><span>Player</span><span>Availability</span></div>
    <div id="rows"></div>
  </section>
</div>

<script>
(function () {
  var data = __DATA__;   /* [position, name, status] in display order */
  var META = __META__;
  var STATUS = {
    "Available": { cls: "s-avail", text: "Available", avail: true },
    "Available - Recurring Medical Attention": { cls: "s-attn", text: "Available - Attention", avail: true },
    "Available - Modified": { cls: "s-mod", text: "Available - Modified", avail: true },
    "Unavailable": { cls: "s-un", text: "Unavailable", avail: false }
  };
  var POS = { "Goalkeepers": "Goalkeeper", "Defenders": "Defender", "Midfielders": "Midfielder", "Forwards": "Forward" };
  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function info(status) { return STATUS[status] || { cls: "s-na", text: status ? String(status) : "Unknown", avail: false }; }

  document.getElementById("meta").innerHTML = META.split("|").map(esc).join("<br>");

  var gk = data.filter(function (d) { return d[0] === "Goalkeepers"; });
  var out = data.filter(function (d) { return d[0] !== "Goalkeepers"; });
  var count = function (list, pred) { return list.filter(function (d) { return pred(d[2]); }).length; };
  var isFull = function (st) { return st === "Available" || st === "Available - Recurring Medical Attention"; };
  var isMod = function (st) { return st === "Available - Modified"; };
  function tile(label, list) {
    var a = count(list, isFull), m = count(list, isMod), t = list.length;
    var cls = t === 0 ? "" : (a === t ? "ok" : (a + m === 0 ? "none" : "some"));
    return '<div class="tile ' + cls + '"><div class="k">' + label + '</div><div class="v">' + a + '<small> / ' + t + '</small>' +
      '<span class="plus' + (m ? "" : " zero") + '">+' + m + ' Modified</span></div></div>';
  }
  document.getElementById("tiles").innerHTML = tile("Goalkeepers available", gk) + tile("Outfield available", out);

  /* row height scales with squad size so the whole list fits one phone screen */
  var rh = Math.max(19, Math.min(32, Math.floor(602 / Math.max(data.length, 1))));
  var fs = rh >= 28 ? ".92rem" : (rh >= 23 ? ".84rem" : ".76rem");
  var panel = document.querySelector(".panel"), rowsEl = document.getElementById("rows");
  panel.style.setProperty("--fs", fs);
  rowsEl.style.setProperty("--rh", rh + "px");
  rowsEl.innerHTML = data.length ? data.map(function (d) {
    var s = info(d[2]);
    return '<div class="row p ' + s.cls + '"><span class="pos">' + esc(POS[d[0]] || d[0]) + '</span><span class="nm">' + esc(d[1]) +
      '</span><span class="st">' + esc(s.text) + '</span></div>';
  }).join("") : '<div class="empty">No players found.</div>';
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


def build_overview_rows(roster: dict, current_data: dict, position_order: list) -> list:
    """[[position, name, status], ...] in display order (position group,
    then name). roster is {position: [player_dict, ...]} for one team;
    players with no committed availability record default to 'Available',
    as on the Player Availability page."""
    rows = []
    for position in position_order:
        for player in roster.get(position, []):
            name = player["name"]
            status = current_data.get(name, {}).get("status", "Available")
            rows.append([position, str(name), status])
    return rows


def build_overview_html(rows: list, meta: str) -> str:
    """Fill the template. meta is shown top-right; use '|' for a line break."""

    def _js(value) -> str:
        # "</" would end the <script> block early, so escape it.
        return json.dumps(value).replace("</", "<\\/")

    return TEMPLATE.replace("__DATA__", _js(rows)).replace("__META__", _js(meta))