"""
Team Overview logic, ported from the standalone Match GPS Dashboard app.

Only what the "Team Overview" page needs was kept: the match-matrix chart,
match-label building/sorting, per-90 team metrics, and the match header.
Player Profile, Export PDF, the password gate, and the CSV/Google Sheet
loader were intentionally left out — this app's Upload tab and Supabase
are the only data path now.
"""

import zlib

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

# Column names as this module expects them (i.e. after renaming from the
# sanitized Supabase columns via GPS_DASHBOARD_COLUMN_MAP in app.py).
METRIC_COLUMNS = [
    "Total Distance (m)",
    "High Speed Running (m)",
    "Sprint Distance (m)",
    "High Intensity Actions",
    "High Intensity Distance (m)",
    "Max Speed (km/h)",
    "Game Minutes (mins)",
]
SUMMARY_METRICS = [m for m in METRIC_COLUMNS if m not in ("Max Speed (km/h)", "Game Minutes (mins)")]
IDENTIFIER_COLUMNS = ["Match Date", "Opposition"]
METRIC_LABELS = {
    "Total Distance (m)": "Total Distance",
    "High Speed Running (m)": "High Speed Running",
    "Sprint Distance (m)": "Sprint Distance",
    "High Intensity Actions": "High Intensity Actions",
    "High Intensity Distance (m)": "High Intensity Distance",
    "Max Speed (km/h)": "Max Speed",
    "Game Minutes (mins)": "Game Minutes",
}
MATCH_LABEL_COL = "_match_label"
SORT_DATE_COL = "_sort_date"
MATCH_INFO_COLUMNS = ["Competition", "Home Team", "Away Team", "Home Team Score", "Away Team Score"]
BADGE_PALETTE = ["#1f4e8c", "#e8532b", "#2f9e44", "#7048e8", "#f08c00", "#0c8599", "#c2255c", "#495057"]


def parse_match_date(series):
    s = series.astype(str).str.strip()
    parsed = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    remaining = parsed.isna()
    if remaining.any():
        parsed.loc[remaining] = pd.to_datetime(s[remaining], errors="coerce", dayfirst=True)
    return parsed


def _display_date(series):
    parsed = parse_match_date(series)
    formatted = parsed.dt.strftime("%d %b %Y")
    raw = series.astype(str).str.strip()
    return formatted.where(parsed.notna(), raw)


def build_match_labels(df):
    df = df.copy()
    cols_present = [c for c in IDENTIFIER_COLUMNS if c in df.columns]
    if not cols_present:
        df[MATCH_LABEL_COL] = "Uploaded Match"
        return df, cols_present
    if len(cols_present) == 2:
        date_part = _display_date(df["Match Date"])
        opp_part = df["Opposition"].astype(str).str.strip()
        df[MATCH_LABEL_COL] = date_part + " vs " + opp_part
    elif cols_present[0] == "Match Date":
        df[MATCH_LABEL_COL] = _display_date(df["Match Date"])
    else:
        df[MATCH_LABEL_COL] = df[cols_present[0]].astype(str).str.strip()
    return df, cols_present


def sorted_match_labels(df, cols_present, descending=True):
    subset_cols = [MATCH_LABEL_COL] + (["Match Date"] if "Match Date" in cols_present else [])
    subset = df[subset_cols].drop_duplicates()
    if "Match Date" in cols_present:
        subset[SORT_DATE_COL] = parse_match_date(subset["Match Date"])
        subset = subset.sort_values(SORT_DATE_COL, ascending=not descending)
    return subset[MATCH_LABEL_COL].tolist()


def team_per90(df, metric):
    total_minutes = df["Game Minutes (mins)"].sum()
    if not total_minutes:
        return float("nan")
    return df[metric].sum() / total_minutes * 90



# Club logo URLs, keyed by a normalized team name (see _normalize_team_name).
# These are placeholders — swap in real hosted logo URLs when available.
# Any team not listed here (or any name that doesn't normalize to a match)
# falls back to the colored-initials badge below.
TEAM_LOGOS = {
    "hougang united": "https://placehold.co/64x64?text=HUFC",
    "brunei dpmm": "https://placehold.co/64x64?text=DPMM",
    "albirex niigata": "https://placehold.co/64x64?text=ALB",
    "jurong": "https://placehold.co/64x64?text=FCJ",
    "geylang international": "https://placehold.co/64x64?text=GIFC",
    "tanjong pagar united": "https://placehold.co/64x64?text=TPU",
    "balestier khalsa": "https://placehold.co/64x64?text=BKFC",
    "tampines rovers": "https://placehold.co/64x64?text=TRFC",
    "young lions": "https://placehold.co/64x64?text=YL",
}


def _normalize_team_name(name):
    """Lowercase, drop 'FC'/'F.C.', collapse whitespace, so e.g.
    'Tampines Rovers FC' and 'Tampines Rovers' both hit the same
    TEAM_LOGOS key regardless of how the name was entered on Tab 1."""
    if not isinstance(name, str):
        return ""
    cleaned = name.replace("F.C.", "").replace("FC", "")
    return " ".join(cleaned.lower().split())


def _team_logo_url(name):
    """Look up a club logo URL for a team name. Returns None if the team
    isn't in TEAM_LOGOS, in which case the caller should fall back to the
    initials badge."""
    return TEAM_LOGOS.get(_normalize_team_name(name))


def _team_initials(name):
    if not isinstance(name, str) or not name.strip():
        return "?"
    parts = [p for p in name.replace("FC", "").split() if p]
    if not parts:
        return name[:2].upper()
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def _initials_badge_html(name, size=44):
    color = BADGE_PALETTE[zlib.crc32(str(name).encode()) % len(BADGE_PALETTE)]
    return (
        f"<div style='width:{size}px;height:{size}px;border-radius:50%;background:{color};"
        f"display:flex;align-items:center;justify-content:center;color:white;"
        f"font-weight:700;font-size:{size*0.38}px;margin:0 auto;'>{_team_initials(name)}</div>"
    )


def _team_badge_html(name, size=44):
    """Club logo if we have a URL for this team, else the colored-initials
    badge. The logo is scaled to fit within a size x size box (preserving
    its own aspect ratio, not cropped to a circle) and centered. The <img>
    also carries an onerror handler that swaps in the initials badge
    client-side if the logo URL 404s or fails to load, so a bad/placeholder
    URL never leaves a broken-image icon on screen."""
    logo_url = _team_logo_url(name)
    if not logo_url:
        return _initials_badge_html(name, size)

    fallback_html = _initials_badge_html(name, size).replace("'", "\\'")
    return (
        f"<div style='width:{size}px;height:{size}px;display:flex;"
        f"align-items:center;justify-content:center;margin:0 auto;'>"
        f"<img src='{logo_url}' alt='{_team_initials(name)}' "
        f"style='max-width:{size}px;max-height:{size}px;width:auto;height:auto;"
        f"object-fit:contain;display:block;' "
        f"onerror=\"this.parentElement.outerHTML='{fallback_html}';\" />"
        f"</div>"
    )


def render_match_header(match_row):
    """[Competition] then [badge][Home] score - score [Away][badge].
    Falls back to a plain title if match-info columns aren't present
    (i.e. this wasn't tagged as a Match upload)."""
    has_info = all(c in match_row.index for c in MATCH_INFO_COLUMNS) and pd.notna(match_row.get("Home Team"))
    if not has_info:
        st.subheader("GPS Match Dashboard")
        return

    competition = match_row.get("Competition")
    home_team, away_team = str(match_row["Home Team"]), str(match_row["Away Team"])
    hs, as_ = match_row.get("Home Team Score"), match_row.get("Away Team Score")
    hs_str = "–" if pd.isna(hs) else str(int(hs))
    as_str = "–" if pd.isna(as_) else str(int(as_))

    if pd.notna(competition):
        st.markdown(
            f"<div style='text-align:center;color:#888;font-size:0.8rem;"
            f"letter-spacing:1.5px;text-transform:uppercase;margin-bottom:4px;'>{competition}</div>",
            unsafe_allow_html=True,
        )

    c1, c2, c3, c4, c5, c6, c7 = st.columns([1, 3, 1, 0.6, 1, 3, 1])
    with c1:
        st.markdown(_team_badge_html(home_team), unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div style='text-align:right;font-size:1.4rem;font-weight:700;padding-top:6px;'>{home_team}</div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div style='text-align:center;font-size:1.8rem;font-weight:800;padding-top:2px;'>{hs_str}</div>", unsafe_allow_html=True)
    with c4:
        st.markdown("<div style='text-align:center;font-size:1.8rem;font-weight:800;padding-top:2px;color:#999;'>-</div>", unsafe_allow_html=True)
    with c5:
        st.markdown(f"<div style='text-align:center;font-size:1.8rem;font-weight:800;padding-top:2px;'>{as_str}</div>", unsafe_allow_html=True)
    with c6:
        st.markdown(f"<div style='text-align:left;font-size:1.4rem;font-weight:700;padding-top:6px;'>{away_team}</div>", unsafe_allow_html=True)
    with c7:
        st.markdown(_team_badge_html(away_team), unsafe_allow_html=True)


def _single_metric_chart(long_df_subset, tooltip_fields, player_order, chart_height, show_y_labels):
    """One metric's bar+label chart as its own top-level Altair spec (not
    faceted). Vega-Lite's "container" width sizing only reliably works on
    a single view — a faceted or concatenated chart can't be resized to
    fill its parent the way Streamlit's use_container_width expects — so
    each metric gets its own chart here and they're placed side by side
    in Streamlit columns instead of Altair facet columns. Player-name
    labels are only drawn on the first (leftmost) chart, matching how the
    old shared-axis facet looked."""
    long_df_subset = long_df_subset.copy()

    # Vega-Lite can't measure rendered text width to decide layout, so
    # this approximates "does the label fit inside the bar": a label
    # needs roughly this fraction of the metric's own max value to have
    # enough bar length behind it, scaling with how many characters the
    # label has. Bars clearing that threshold get the label inside at
    # the base; shorter bars get it just past the bar's end instead.
    domain_max = long_df_subset["Value"].max()
    if pd.isna(domain_max) or domain_max <= 0:
        domain_max = 1.0
    needed_fraction = (long_df_subset["Label"].str.len() * 0.045).clip(lower=0.18, upper=0.75)
    long_df_subset["LabelInside"] = (long_df_subset["Value"] / domain_max) >= needed_fraction

    base = alt.Chart(long_df_subset).encode(
        y=alt.Y(
            "Player Name:N",
            sort=player_order,
            title=None,
            axis=alt.Axis(labels=show_y_labels, ticks=show_y_labels),
        ),
    )
    bars = base.mark_bar(cornerRadiusEnd=5).encode(
        x=alt.X("Value:Q", title=None, axis=alt.Axis(labels=False, ticks=False, grid=True)),
        color=alt.Color("Value:Q", scale=alt.Scale(scheme="blues"), legend=None),
        tooltip=tooltip_fields,
    )
    labels_inside = base.transform_filter(alt.datum.LabelInside).mark_text(
        align="left", baseline="middle", fontSize=18, fontWeight="bold", color="#ffffff"
    ).encode(
        x=alt.value(6),
        text=alt.Text("Label:N"),
        tooltip=tooltip_fields,
    )
    labels_outside = base.transform_filter(alt.datum.LabelInside == False).mark_text(
        align="left", baseline="middle", dx=4, fontSize=18, color="#333333"
    ).encode(
        x=alt.X("Value:Q"),
        text=alt.Text("Label:N"),
        tooltip=tooltip_fields,
    )
    return (
        (bars + labels_inside + labels_outside)
        .properties(height=chart_height, width="container")
        .configure_view(strokeWidth=0)
    )


def render_matrix_chart(df, raw_df=None, window_labels=None, row_height=26, sort_by="Game Minutes (mins)"):
    """Render the Team Overview bar-chart grid directly (one Streamlit
    column per metric, each holding its own full-width chart — see
    _single_metric_chart for why). Players with no recorded Total
    Distance for this match (0 or missing — i.e. an unused sub, not a
    real 0 worth graphing) are dropped from every one of these bar
    graphs first."""
    if "Total Distance (m)" in df.columns:
        df = df[df["Total Distance (m)"].fillna(0) != 0].copy()

    if df.empty:
        st.info("No player data with recorded distance for this match.")
        return

    player_order = df.sort_values(sort_by, ascending=False)["Player Name"].tolist()
    metric_order = [METRIC_LABELS[m] for m in METRIC_COLUMNS]
    max_speed_label = METRIC_LABELS["Max Speed (km/h)"]

    long_df = df.melt(id_vars="Player Name", value_vars=METRIC_COLUMNS, var_name="Metric", value_name="Value")
    long_df["Metric"] = long_df["Metric"].map(METRIC_LABELS)
    long_df = long_df.dropna(subset=["Value"])
    is_speed = long_df["Metric"] == max_speed_label
    long_df["Label"] = np.where(
        is_speed,
        long_df["Value"].map(lambda v: f"{v:.1f}"),
        long_df["Value"].round(0).astype(int).astype(str),
    )

    tooltip_fields = [
        alt.Tooltip("Player Name:N", title="Player"),
        alt.Tooltip("Metric:N"),
        alt.Tooltip("Value:Q", title="Value", format=",.1f"),
    ]

    if raw_df is not None and window_labels and len(window_labels) > 1:
        hist = raw_df[raw_df["Player Name"].isin(long_df["Player Name"].unique()) & raw_df[MATCH_LABEL_COL].isin(window_labels)]
        hist_long = hist.melt(id_vars=["Player Name", MATCH_LABEL_COL], value_vars=METRIC_COLUMNS, var_name="MetricCol", value_name="V")
        hist_long["Metric"] = hist_long["MetricCol"].map(METRIC_LABELS)
        pivot = hist_long.pivot_table(index=["Player Name", "Metric"], columns=MATCH_LABEL_COL, values="V", aggfunc="first")
        pivot = pivot.reindex(columns=window_labels).reset_index()
        long_df = long_df.merge(pivot, on=["Player Name", "Metric"], how="left")

        for lbl in window_labels:
            is_speed_row = long_df["Metric"] == max_speed_label
            raw_vals = long_df[lbl]
            formatted = []
            for val, speed_row in zip(raw_vals, is_speed_row):
                if pd.isna(val):
                    formatted.append("—")
                elif speed_row:
                    formatted.append(f"{val:.1f}")
                else:
                    formatted.append(str(int(round(val))))
            long_df[lbl] = formatted
            tooltip_fields.append(alt.Tooltip(f"{lbl}:N", title=lbl))

    chart_height = max(240, row_height * df["Player Name"].nunique())

    # Relative column widths: the bar-range metrics (distances, actions)
    # read more easily with more room, while Max Speed and Game Minutes —
    # much narrower value ranges — stay legible in a slimmer column.
    METRIC_COLUMN_WEIGHTS = {
        "Total Distance": 1.9,
        "High Speed Running": 1.3,
        "Sprint Distance": 1.3,
        "High Intensity Actions": 1.3,
        "High Intensity Distance": 1.3,
        "Max Speed": 0.7,
        "Game Minutes": 0.7,
    }

    metrics_present = [lbl for lbl in metric_order if lbl in set(long_df["Metric"])]
    columns = st.columns([METRIC_COLUMN_WEIGHTS.get(lbl, 1.0) for lbl in metrics_present])
    for i, (col, metric_label) in enumerate(zip(columns, metrics_present)):
        subset = long_df[long_df["Metric"] == metric_label]
        with col:
            st.markdown(
                f"<div style='text-align:center; font-weight:700; font-size:0.75rem; "
                f"margin-bottom:6px;'>{metric_label}</div>",
                unsafe_allow_html=True,
            )
            chart = _single_metric_chart(
                subset, tooltip_fields, player_order, chart_height, show_y_labels=(i == 0)
            )
            st.altair_chart(chart, use_container_width=True)