"""
Performance > Medical Screening page.

Ported from the standalone screening_app.py. Everything the standalone
app did at module level (page config, sidebar, st.stop()) now lives
inside render_screening_page(), so app.py can call it as one branch of
its nav router without it taking over the page or halting the script.

Data comes from the Supabase 'screening_results' table (see
schema_screening.sql). app.py reads it with its cached read_table() and
passes the DataFrame in, so this module never touches Supabase itself.

Variable names, scales, ranges and thresholds all come from
utils/screening_spec.py -- edit that file, not this one, to change the
protocol.
"""

import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.screening_spec import (
    SCALES,
    REGION_COLORS,
    SINGLE_CHOICE_TESTS,
    NUMBER_TESTS,
    ANTHRO_FIELDS,
    SKINFOLD_FIELDS,
    MOBILITY_THRESHOLDS,
    REGIONS,
    col_name,
    all_expected_columns,
    count_single_choice_fields,
)

# Scoped to this page only (the page is the only place this is injected).
# The standalone app's global overrides (.stApp background, .block-container
# width, html/body font) were dropped so they don't restyle the rest of the
# dashboard; the font is applied to the .st-key-screening_root container
# instead.
SCREENING_CSS = """<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600;700&display=swap');

    .st-key-screening_root, .st-key-screening_root * { font-family: 'Inter', sans-serif; }

    .sg-header {
        font-size: 1.6rem; font-weight: 700; color: #0F172A; margin-bottom: 0;
    }
    .sg-subheader {
        font-size: 0.95rem; color: #64748B; margin-top: 2px; margin-bottom: 1.2rem;
    }

    .test-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-left: 4px solid var(--region-color, #94A3B8);
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .test-name {
        font-size: 13px; font-weight: 600; color: #334155; margin-bottom: 8px;
    }
    .test-note {
        font-size: 11px; color: #94A3B8; font-style: italic;
        margin-top: -6px; margin-bottom: 8px;
    }
    .side-row { display: flex; gap: 28px; flex-wrap: wrap; }
    .side-block { flex: 1; min-width: 220px; }
    .side-label {
        font-size: 10px; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.06em; color: #94A3B8; margin-bottom: 4px;
    }

    .pill-row { display: flex; gap: 6px; flex-wrap: wrap; }
    .pill {
        padding: 4px 10px; border-radius: 999px; font-size: 11.5px;
        font-weight: 500; border: 1px solid #CBD5E1; color: #94A3B8;
        background: transparent; white-space: nowrap; line-height: 1.6;
    }
    .pill.selected {
        color: #ffffff; border-color: transparent; font-weight: 700;
        box-shadow: 0 1px 2px rgba(0,0,0,0.18);
    }
    .pill.na {
        opacity: 0.45; font-style: italic;
    }

    .gauge-value {
        font-family: 'IBM Plex Mono', monospace; font-weight: 700;
        font-size: 20px; color: #0F172A;
    }
    .gauge-unit {
        font-family: 'IBM Plex Mono', monospace; font-weight: 500;
        font-size: 12px; color: #94A3B8; margin-left: 3px;
    }
    .gauge-track {
        position: relative; height: 8px; background: #E2E8F0;
        border-radius: 4px; margin-top: 8px;
    }
    .gauge-fill {
        position: absolute; left: 0; top: 0; height: 100%;
        background: #0D9488; border-radius: 4px;
    }
    .gauge-labels {
        display: flex; justify-content: space-between; font-size: 10px;
        color: #94A3B8; margin-top: 3px; font-family: 'IBM Plex Mono', monospace;
    }

    .summary-card {
        background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px;
        padding: 14px 18px; text-align: left;
    }
    .summary-value {
        font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: 26px;
    }
    .summary-label {
        font-size: 11px; color: #64748B; text-transform: uppercase;
        letter-spacing: 0.05em; margin-top: 2px;
    }

    .anthro-row { display: flex; gap: 36px; flex-wrap: wrap; }
    .anthro-item { display: flex; flex-direction: column; gap: 2px; }
    .anthro-label {
        font-size: 10px; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.06em; color: #94A3B8;
    }
    .anthro-value {
        font-family: 'IBM Plex Mono', monospace; font-weight: 700;
        font-size: 18px; color: #0F172A;
    }

    .lrbar-row {
        display: flex; align-items: center; gap: 10px; margin-top: 8px;
    }
    .lrbar-label {
        width: 16px; font-size: 11px; font-weight: 700; color: #94A3B8; flex-shrink: 0;
    }
    .lrbar-track {
        flex: 1; height: 14px; background: #E2E8F0; border-radius: 999px; overflow: hidden;
    }
    .lrbar-fill {
        height: 100%; border-radius: 999px;
    }
    .lrbar-value {
        width: 68px; text-align: right; flex-shrink: 0;
        font-family: 'IBM Plex Mono', monospace; font-size: 12px; font-weight: 600; color: #334155;
    }
    .diff-bubble {
        display: inline-block; padding: 4px 12px; border-radius: 999px;
        font-size: 12px; font-weight: 700;
    }
    .diff-bubble-balanced { background: #DCFCE7; color: #15803D; }
    .diff-bubble-watch { background: #FEF3C7; color: #B45309; }
    .diff-bubble-flag { background: #FEE2E2; color: #B91C1C; }
    .diff-bubble-na { background: #F1F5F9; color: #94A3B8; }
    </style>"""


# ----------------------------------------------------------------------
# RENDER HELPERS
# ----------------------------------------------------------------------
def render_pill_row(value, scale_key: str) -> str:
    scale = SCALES[scale_key]
    if pd.isna(value) or value == "":
        pills = "".join(f'<span class="pill na">{opt}</span>' for opt in scale["options"])
        return f'<div class="pill-row">{pills}</div>'
    pills = []
    for opt in scale["options"]:
        if str(value).strip() == opt:
            color = scale["colors"][opt]
            pills.append(
                f'<span class="pill selected" style="background:{color};">{opt}</span>'
            )
        else:
            pills.append(f'<span class="pill">{opt}</span>')
    return f'<div class="pill-row">{"".join(pills)}</div>'


def parse_numeric(val, unit: str = ""):
    """Best-effort parse of a value to float, tolerating a unit suffix
    that's already baked into the string (e.g. '8 mm' or '188.0cm') --
    this is what was causing units to render twice: a value like '8 mm'
    failed float() outright, fell through to a fallback that then
    appended the unit again, producing '8 mmmm'. Returns None if the
    value is missing or genuinely not numeric."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    if unit and s.lower().endswith(unit.lower()):
        s = s[: -len(unit)].strip()
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def format_measurement(val, unit: str, dp: int) -> str:
    num = parse_numeric(val, unit)
    if num is not None:
        return f"{num:.{dp}f}{unit}"
    if pd.isna(val):
        return "\u2014"
    return str(val).strip()  # unparseable -- show as-is, never re-append the unit


def compute_skinfold_sum(row: pd.Series):
    """8-site skinfold sum. Returns None (not a partial total) unless
    all 8 sites have a value, since the standard sum isn't meaningful
    with sites missing."""
    total = 0.0
    for region, test, unit, _dp in SKINFOLD_FIELDS:
        num = parse_numeric(row.get(col_name(region, test), pd.NA), unit)
        if num is None:
            return None
        total += num
    return total


# Bands for the 8-site skinfold sum. Edit the thresholds/colors here if
# your protocol uses different cutoffs.
SKINFOLD_SUM_BANDS = [
    ("< 65 (Low)", lambda v: v < 65, "#22C55E"),
    ("65\u201375 (Moderate)", lambda v: 65 <= v <= 75, "#F97316"),
    ("> 75 (High)", lambda v: v > 75, "#EF4444"),
]


def render_skinfold_sum_card(row: pd.Series) -> str:
    accent = REGION_COLORS["Skinfold Analysis"]
    total = compute_skinfold_sum(row)

    if total is None:
        pills = "".join(f'<span class="pill na">{label}</span>' for label, _cond, _color in SKINFOLD_SUM_BANDS)
        return (
            f'<div class="test-card" style="--region-color:{accent};">'
            f'<div class="test-name">8-site Skinfold Sum</div>'
            f'<div class="gauge-value" style="color:#CBD5E1;">No data</div>'
            f'<div class="pill-row" style="margin-top:8px;">{pills}</div>'
            f'</div>'
        )

    pills = []
    matched_color = "#0F172A"
    for label, cond, color in SKINFOLD_SUM_BANDS:
        if cond(total):
            pills.append(f'<span class="pill selected" style="background:{color};">{label}</span>')
            matched_color = color
        else:
            pills.append(f'<span class="pill">{label}</span>')

    return (
        f'<div class="test-card" style="--region-color:{accent};">'
        f'<div class="test-name">8-site Skinfold Sum</div>'
        f'<div><span class="gauge-value" style="color:{matched_color};">{total:.1f}</span>'
        f'<span class="gauge-unit">mm</span></div>'
        f'<div class="pill-row" style="margin-top:8px;">{"".join(pills)}</div>'
        f'</div>'
    )


def render_text_fields_row(fields, row: pd.Series, accent_region: str, extra_items_html: str = "") -> str:
    """Render a list of (region, test, unit, decimal_places) fields as
    plain text in one row (no scale/gauge -- just label + value).
    Used for Height/Weight/Bodyfat and for the Skinfold measurements.
    extra_items_html lets a caller splice in additional computed items
    (e.g. the skinfold sum) into the same row cleanly."""
    items_html = []
    for region, test, unit, dp in fields:
        val = row.get(col_name(region, test), pd.NA)
        value_str = format_measurement(val, unit, dp)
        # test name without the "(unit)" suffix already baked into it, e.g. "Height (cm)" -> "Height"
        label = test.split(" (")[0].replace(" Skinfold", "")
        items_html.append(
            f'<div class="anthro-item">'
            f'<div class="anthro-label">{label}</div>'
            f'<div class="anthro-value">{value_str}</div>'
            f'</div>'
        )
    accent = REGION_COLORS[accent_region]
    return (
        f'<div class="test-card" style="--region-color:{accent};">'
        f'<div class="anthro-row">{"".join(items_html)}{extra_items_html}</div>'
        f'</div>'
    )


def render_anthro_row(row: pd.Series) -> str:
    """Height / Weight / Bodyfat, plus the computed 8-site skinfold sum,
    all shown together as plain text in one row."""
    total = compute_skinfold_sum(row)
    total_str = f"{total:.1f}mm" if total is not None else "\u2014"
    extra_item = (
        f'<div class="anthro-item">'
        f'<div class="anthro-label">8-site Skinfold Sum</div>'
        f'<div class="anthro-value">{total_str}</div>'
        f'</div>'
    )
    return render_text_fields_row(ANTHRO_FIELDS, row, "Athlete Profile", extra_items_html=extra_item)


def render_skinfold_row(row: pd.Series) -> str:
    """The 8 skinfold measurements shown together as plain text in one row."""
    return render_text_fields_row(SKINFOLD_FIELDS, row, "Skinfold Analysis")


WEIGHT_COL = col_name("Athlete Profile", "Weight (kg)")


def compute_normalized_team_average(df: pd.DataFrame, region: str, test: str, side, unit: str):
    """Mean of (value / bodyweight) across every row in the currently
    loaded dataset that has both a valid value for this test/side and a
    valid Weight (kg). Returns None if no row qualifies."""
    col = col_name(region, test, side)
    if col not in df.columns or WEIGHT_COL not in df.columns:
        return None
    normed = []
    for _, r in df.iterrows():
        v = parse_numeric(r.get(col, pd.NA), unit)
        w = parse_numeric(r.get(WEIGHT_COL, pd.NA), "kg")
        if v is not None and w is not None and w > 0:
            normed.append(v / w)
    if not normed:
        return None
    return sum(normed) / len(normed)


def render_team_avg_bubble(label_prefix: str, value, weight, team_avg) -> str:
    """'<label>XX% above/below team average', normalizing value by
    bodyweight and comparing to the pre-computed team average of the
    same normalized metric. label_prefix already includes any trailing
    punctuation/spacing, e.g. 'Left Side: ' or ''."""
    if value is None or weight is None or weight <= 0:
        return f'<span class="diff-bubble diff-bubble-na">{label_prefix}No data</span>'
    if team_avg is None or team_avg == 0:
        return f'<span class="diff-bubble diff-bubble-na">{label_prefix}No team data yet</span>'
    normed = value / weight
    pct = (normed - team_avg) / team_avg * 100
    direction = "above" if pct >= 0 else "below"
    band_class = "diff-bubble-balanced" if pct >= 0 else "diff-bubble-flag"  # green for above, red for below
    return f'<span class="diff-bubble {band_class}">{label_prefix}{abs(pct):.0f}% {direction} team average</span>'


def render_lr_bar_card(region: str, test: str, row: pd.Series, df: pd.DataFrame, vmin, vmax, unit: str) -> str:
    """A pair of stacked, same-direction ('unidirectional') rounded bars
    for Left vs Right, a bubble showing the % difference and which side
    is stronger, plus two bodyweight-normalized team-average bubbles
    (one per side). Scaled against the test's estimated min-max range
    (like the gauge cards) so bar lengths stay comparable across
    timepoints, not just relative to each other."""
    accent = REGION_COLORS[region]
    left_val = parse_numeric(row.get(col_name(region, test, "Left"), pd.NA), unit)
    right_val = parse_numeric(row.get(col_name(region, test, "Right"), pd.NA), unit)
    weight = parse_numeric(row.get(WEIGHT_COL, pd.NA), "kg")

    def bar_row(label, val):
        if val is None:
            pct, value_str, fill_color = 0.0, "No data", "#E2E8F0"
        else:
            pct = max(0.0, min(1.0, (val - vmin) / (vmax - vmin))) * 100
            value_str, fill_color = f"{val:g}{unit}", accent
        return (
            f'<div class="lrbar-row">'
            f'<div class="lrbar-label">{label}</div>'
            f'<div class="lrbar-track"><div class="lrbar-fill" '
            f'style="width:{pct:.1f}%;background:{fill_color};"></div></div>'
            f'<div class="lrbar-value">{value_str}</div>'
            f'</div>'
        )

    bars_html = bar_row("L", left_val) + bar_row("R", right_val)

    if left_val is None or right_val is None:
        diff_bubble_html = '<span class="diff-bubble diff-bubble-na">No data for comparison</span>'
    elif left_val == right_val:
        diff_bubble_html = '<span class="diff-bubble diff-bubble-balanced">Balanced (0% difference)</span>'
    else:
        stronger_side = "left" if left_val > right_val else "right"
        pct_diff = abs(left_val - right_val) / max(left_val, right_val) * 100
        # Band thresholds follow commonly-cited limb-symmetry-index
        # cutoffs (<10% typical, 10-15% monitor, >15% flag) -- adjust to
        # your own protocol's thresholds if they differ.
        if pct_diff < 10:
            band_class = "diff-bubble-balanced"
        elif pct_diff < 15:
            band_class = "diff-bubble-watch"
        else:
            band_class = "diff-bubble-flag"
        diff_bubble_html = f'<span class="diff-bubble {band_class}">{pct_diff:.0f}% stronger on {stronger_side}</span>'

    left_avg = compute_normalized_team_average(df, region, test, "Left", unit)
    right_avg = compute_normalized_team_average(df, region, test, "Right", unit)
    left_bubble_html = render_team_avg_bubble("Left Side: ", left_val, weight, left_avg)
    right_bubble_html = render_team_avg_bubble("Right Side: ", right_val, weight, right_avg)

    return (
        f'<div class="test-card" style="--region-color:{accent};">'
        f'<div class="test-name">{test}</div>'
        f'{bars_html}'
        f'<div style="margin-top:10px; display:flex; flex-wrap:wrap; gap:8px;">'
        f'{diff_bubble_html}{left_bubble_html}{right_bubble_html}'
        f'</div>'
        f'</div>'
    )


def render_gym_single_card(region: str, test: str, row: pd.Series, df: pd.DataFrame, vmin, vmax, unit: str) -> str:
    """For Gym Performance Testing fields with no Left/Right split (e.g.
    IMTP): the usual gauge, plus a single bodyweight-normalized
    team-average bubble."""
    accent = REGION_COLORS[region]
    val = parse_numeric(row.get(col_name(region, test), pd.NA), unit)
    weight = parse_numeric(row.get(WEIGHT_COL, pd.NA), "kg")
    team_avg = compute_normalized_team_average(df, region, test, None, unit)
    bubble_html = render_team_avg_bubble("", val, weight, team_avg)

    return (
        f'<div class="test-card" style="--region-color:{accent};">'
        f'<div class="test-name">{test}</div>'
        f'{render_gauge(val, vmin, vmax, unit)}'
        f'<div style="margin-top:10px;">{bubble_html}</div>'
        f'</div>'
    )


def is_flagged(num, threshold) -> bool:
    if threshold is None or num is None:
        return False
    if threshold["direction"] == "below":
        return num < threshold["value"]
    return num > threshold["value"]


def render_gauge(value, vmin, vmax, unit, threshold=None) -> str:
    num = parse_numeric(value, unit)
    if num is None:
        return (
            '<div class="gauge-value" style="color:#CBD5E1;">No data</div>'
            '<div class="gauge-track"><div class="gauge-fill" style="width:0%;background:#E2E8F0;"></div></div>'
            f'<div class="gauge-labels"><span>{vmin}</span><span>{vmax}{unit}</span></div>'
        )
    pct = max(0.0, min(1.0, (num - vmin) / (vmax - vmin))) * 100
    flagged = is_flagged(num, threshold)
    value_color = "#EF4444" if flagged else "#0F172A"
    fill_color = "#EF4444" if flagged else "#0D9488"
    return (
        f'<div><span class="gauge-value" style="color:{value_color};">{num:g}</span>'
        f'<span class="gauge-unit">{unit}</span></div>'
        f'<div class="gauge-track"><div class="gauge-fill" style="width:{pct:.1f}%;background:{fill_color};"></div></div>'
        f'<div class="gauge-labels"><span>{vmin}</span><span>{vmax}{unit}</span></div>'
    )


def render_test_card(region: str, test: str, row: pd.Series, kind: str, meta, sided: bool = True, threshold=None) -> str:
    accent = REGION_COLORS[region]
    note_html = f'<div class="test-note">{threshold["note"]}</div>' if threshold else ""

    if not sided:
        val = row.get(col_name(region, test), pd.NA)
        if kind == "single_choice":
            body_html = render_pill_row(val, meta)
        else:
            vmin, vmax, unit = meta
            body_html = render_gauge(val, vmin, vmax, unit, threshold)
        return (
            f'<div class="test-card" style="--region-color:{accent};">'
            f'<div class="test-name">{test}</div>'
            f'{note_html}'
            f'{body_html}'
            f'</div>'
        )

    left_col = col_name(region, test, "Left")
    right_col = col_name(region, test, "Right")
    left_val = row.get(left_col, pd.NA)
    right_val = row.get(right_col, pd.NA)

    if kind == "single_choice":
        left_html = render_pill_row(left_val, meta)
        right_html = render_pill_row(right_val, meta)
    else:
        vmin, vmax, unit = meta
        left_html = render_gauge(left_val, vmin, vmax, unit, threshold)
        right_html = render_gauge(right_val, vmin, vmax, unit, threshold)

    return (
        f'<div class="test-card" style="--region-color:{accent};">'
        f'<div class="test-name">{test}</div>'
        f'{note_html}'
        f'<div class="side-row">'
        f'<div class="side-block">'
        f'<div class="side-label">Left</div>'
        f'{left_html}'
        f'</div>'
        f'<div class="side-block">'
        f'<div class="side-label">Right</div>'
        f'{right_html}'
        f'</div>'
        f'</div>'
        f'</div>'
    )


def compute_flag_count(row: pd.Series) -> int:
    count = 0
    for region, tests in SINGLE_CHOICE_TESTS.items():
        for test, scale_key, sided in tests:
            sides = ("Left", "Right") if sided else (None,)
            for side in sides:
                val = row.get(col_name(region, test, side), pd.NA)
                if pd.notna(val) and str(val).strip() in SCALES[scale_key]["flagged"]:
                    count += 1
    return count


def build_template_csv() -> bytes:
    cols = all_expected_columns()
    buf = io.StringIO()
    df = pd.DataFrame(columns=cols)
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def _strip_excel_guard(val):
    """Undo the Excel formula-injection guard (a leading "'" prepended before
    values like "=- (Good)" or "+ (Sub-optimal)" so Excel treats them as text).
    Excel hides that quote, but if the CSV was edited/read another way the
    literal quote may still be there, so strip it before matching SCALES."""
    if isinstance(val, str) and val[:1] == "'" and val[1:2] in ("=", "+", "-", "@"):
        return val[1:]
    return val


def _prepare_screening_df(raw: pd.DataFrame) -> pd.DataFrame:
    """Clean a raw screening_results DataFrame for display."""
    df = raw.copy()
    df = df.map(_strip_excel_guard) if hasattr(df, "map") else df.applymap(_strip_excel_guard)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df


def _render_template_download():
    with st.expander("CSV template for importing results"):
        st.caption(
            "Headers match the screening_results table, so a filled-in copy can be "
            "imported via the Supabase table editor (Insert > Import data from CSV)."
        )
        st.download_button(
            "Download blank CSV template",
            data=build_template_csv(),
            file_name="screening_template.csv",
            mime="text/csv",
            key="scr_template_download",
        )


def render_screening_page(raw_df: pd.DataFrame):
    """raw_df: the full screening_results table (may be empty)."""
    st.markdown(SCREENING_CSS, unsafe_allow_html=True)

    with st.container(key="screening_root"):
        _render_screening_body(raw_df)


def _render_screening_body(raw_df: pd.DataFrame):
    if raw_df is None or raw_df.empty or "Name" not in raw_df.columns or "Date" not in raw_df.columns:
        st.info(
            "No screening results found in Supabase yet. Import rows into the "
            "'screening_results' table (run schema_screening.sql first if it "
            "doesn't exist)."
        )
        _render_template_download()
        return

    df = _prepare_screening_df(raw_df)

    missing_cols = [c for c in all_expected_columns() if c not in df.columns]
    if missing_cols:
        with st.expander(f"\u26a0\ufe0f {len(missing_cols)} expected column(s) not found"):
            for c in missing_cols:
                st.write(f"- {c}")

    if df["Date"].isna().any():
        st.warning("Some rows have an unparseable Date and will be excluded from date lists.")

    names = sorted(df["Name"].dropna().unique().tolist())
    if not names:
        st.warning("No athlete names found in the screening data.")
        return

    _render_template_download()

    sel_col1, sel_col2 = st.columns(2)
    with sel_col1:
        selected_name = st.selectbox("Name", names, key="scr_name")

    person_df = df[df["Name"] == selected_name].sort_values("Date")
    dates = person_df["Date"].dropna().dt.date.unique().tolist()

    if not dates:
        st.warning(f"No valid dated records found for {selected_name}.")
        return

    with sel_col2:
        selected_date = st.selectbox(
            "Timepoint",
            dates,
            index=len(dates) - 1,
            format_func=lambda d: d.strftime("%d %b %Y"),
            key=f"scr_date_{selected_name}",  # per-athlete key so default resets on name change
        )

    row = person_df[person_df["Date"].dt.date == selected_date].iloc[-1]
    timepoint_idx = dates.index(selected_date) + 1

    # ------------------------------------------------------------------
    # HEADER
    # ------------------------------------------------------------------
    st.markdown(f'<div class="sg-header">{selected_name}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sg-subheader">{selected_date.strftime("%d %b %Y")} '
        f'&middot; Timepoint {timepoint_idx} of {len(dates)}</div>',
        unsafe_allow_html=True,
    )

    flag_count = compute_flag_count(row)
    n_single_choice = count_single_choice_fields()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f'<div class="summary-card"><div class="summary-value" style="color:#0F172A;">{len(dates)}</div>'
            f'<div class="summary-label">Timepoints recorded</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        color = "#EF4444" if flag_count else "#22C55E"
        st.markdown(
            f'<div class="summary-card"><div class="summary-value" style="color:{color};">{flag_count}</div>'
            f'<div class="summary-label">Flagged findings (of {n_single_choice})</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="summary-card"><div class="summary-value" style="color:#0F172A;">{row["Date"].strftime("%d %b %Y")}</div>'
            f'<div class="summary-label">Current timepoint</div></div>',
            unsafe_allow_html=True,
        )

    st.write("")

    # ------------------------------------------------------------------
    # TABS
    # ------------------------------------------------------------------
    tab_results, tab_trends = st.tabs(["Screening Results", "Trends Over Time"])

    with tab_results:
        region_tabs = st.tabs(REGIONS)
        for region_tab, region in zip(region_tabs, REGIONS):
            with region_tab:
                if region == "Athlete Profile":
                    st.markdown(render_anthro_row(row), unsafe_allow_html=True)
                if region == "Skinfold Analysis":
                    st.markdown(render_skinfold_sum_card(row), unsafe_allow_html=True)
                    st.markdown(render_skinfold_row(row), unsafe_allow_html=True)
                if region in SINGLE_CHOICE_TESTS:
                    for test, scale_key, sided in SINGLE_CHOICE_TESTS[region]:
                        st.markdown(
                            render_test_card(region, test, row, "single_choice", scale_key, sided),
                            unsafe_allow_html=True,
                        )
                if region in NUMBER_TESTS:
                    for test, vmin, vmax, unit, sided in NUMBER_TESTS[region]:
                        if region == "Gym Performance Testing" and sided:
                            st.markdown(
                                render_lr_bar_card(region, test, row, df, vmin, vmax, unit),
                                unsafe_allow_html=True,
                            )
                        elif region == "Gym Performance Testing":
                            st.markdown(
                                render_gym_single_card(region, test, row, df, vmin, vmax, unit),
                                unsafe_allow_html=True,
                            )
                        else:
                            threshold = MOBILITY_THRESHOLDS.get(test) if region == "Mobility" else None
                            st.markdown(
                                render_test_card(region, test, row, "number", (vmin, vmax, unit), sided, threshold),
                                unsafe_allow_html=True,
                            )

    with tab_trends:
        # Build a flat, labeled list of variables to choose from
        options = []
        for region, tests in SINGLE_CHOICE_TESTS.items():
            for test, scale_key, sided in tests:
                if sided:
                    for side in ("Left", "Right"):
                        options.append((f"{region} \u2014 {test} ({side})", col_name(region, test, side), "single_choice", scale_key))
                else:
                    options.append((f"{region} \u2014 {test}", col_name(region, test), "single_choice", scale_key))
        for region, tests in NUMBER_TESTS.items():
            for test, vmin, vmax, unit, sided in tests:
                if sided:
                    for side in ("Left", "Right"):
                        options.append((f"{region} \u2014 {test} ({side})", col_name(region, test, side), "number", (vmin, vmax, unit)))
                else:
                    options.append((f"{region} \u2014 {test}", col_name(region, test), "number", (vmin, vmax, unit)))
        # Anthro fields (Height/Weight/Bodyfat) aren't in NUMBER_TESTS since
        # they're shown as plain text, not gauges -- but they can still be
        # trended over time here. Ranges below are just for the chart axis.
        ANTHRO_TREND_RANGES = {
            "Height (cm)": (150, 210),
            "Weight (kg)": (40, 120),
            "Bodyfat Percentage (%)": (5, 30),
        }
        for region, test, unit, _dp in ANTHRO_FIELDS:
            vmin, vmax = ANTHRO_TREND_RANGES.get(test, (0, 100))
            options.append((f"{region} \u2014 {test}", col_name(region, test), "number", (vmin, vmax, unit)))
        # Skinfold measurements -- same treatment, not in NUMBER_TESTS but
        # still trendable. 0-40mm covers the typical range for these sites.
        for region, test, unit, _dp in SKINFOLD_FIELDS:
            options.append((f"{region} \u2014 {test}", col_name(region, test), "number", (0, 40, unit)))

        labels = [o[0] for o in options]
        picked_label = st.selectbox(
            f"Variable to trend for {selected_name}", labels, key="scr_trend_variable"
        )
        picked = next(o for o in options if o[0] == picked_label)
        _, picked_col, picked_kind, picked_meta = picked

        trend_df = person_df[["Date", picked_col]].dropna(subset=["Date"]).sort_values("Date")

        if trend_df.empty:
            st.info("No records available for this person.")
        elif picked_kind == "number":
            vmin, vmax, unit = picked_meta
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=trend_df["Date"],
                    y=trend_df[picked_col],
                    mode="lines+markers",
                    line=dict(color="#0D9488", width=2.5),
                    marker=dict(size=8, color="#0D9488"),
                    name=picked_label,
                    connectgaps=True,
                )
            )
            fig.update_yaxes(range=[vmin, vmax], title=f"Value ({unit})")
            fig.update_xaxes(title="Date")
            fig.update_layout(
                height=420,
                margin=dict(t=20, l=10, r=10, b=10),
                plot_bgcolor="white",
                paper_bgcolor="white",
                font=dict(family="Inter, sans-serif", color="#334155"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            scale = SCALES[picked_meta]
            rows_html = []
            for _, r in trend_df.iterrows():
                val = r[picked_col]
                color = scale["colors"].get(str(val).strip(), "#CBD5E1") if pd.notna(val) else "#E2E8F0"
                label = val if pd.notna(val) else "No data"
                rows_html.append(
                    f'<div style="display:flex;align-items:center;gap:12px;padding:8px 0;'
                    f'border-bottom:1px solid #F1F5F9;">'
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:12px;'
                    f'color:#64748B;width:110px;">{r["Date"].strftime("%d %b %Y")}</div>'
                    f'<div style="width:12px;height:12px;border-radius:50%;background:{color};'
                    f'flex-shrink:0;"></div>'
                    f'<div style="font-size:13px;color:#334155;">{label}</div>'
                    f'</div>'
                )
            st.markdown(
                f'<div class="test-card" style="--region-color:#94A3B8;">{"".join(rows_html)}</div>',
                unsafe_allow_html=True,
            )