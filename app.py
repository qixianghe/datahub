import base64
import html
import re
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
import pandas as pd
from supabase import create_client

from utils.columns import sanitize_columns
from utils import gps_dashboard as gpsd

try:
    from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

    HAS_AGGRID = True
except ImportError:
    HAS_AGGRID = False

st.set_page_config(page_title="LCSFC Performance & Medical Database", page_icon="📊", layout="wide")

# ---------------------------------------------------------------------------
# Config: one entry per data source. Each source maps to its own Supabase
# table (see schema.sql for gps_session_data; use scripts/generate_schema.py
# to create the SQL for a new source's table).
# ---------------------------------------------------------------------------
SOURCE_TABLES = {
    "GPS Session Data": "gps_session_data",
}

TEAMS = ["First Team", "SPL2", "U19"]
SESSION_TYPES = ["Training", "Match", "Testing", "Recovery", "Other"]

# Player Availability — "National Team" quick filter. Selecting it on the
# page filters out this whole group of players straightaway (in addition
# to whatever's picked in the regular player filter). Edit this list here
# whenever the national-team call-up group changes.
NATIONAL_TEAM_PLAYERS = [
    "Glenn Kweh",
    "Song Uiyoung",
    "Hariss Harun",
    "Lionel Tan",
    "Hami Syahin",
    "Nur Adam Abdullah",
    "Farhan Zulkifli",
    "Kyoga Nakamura",
    "Ryhan Stewart",
    "Ilhan Fandi",
    "Shawal Anuar",
]

AVAILABILITY_TABLE = "player_availability"
PLAYERS_TABLE = "players"
MEDICAL_TABLE = "medical_records"
RPE_TABLE = "session_rpe"
TREATMENT_TABLE = "treatment_observations"

# Player position groups. This ordering (not the player data itself) is
# structural, not sensitive, so it stays a code constant — actual player
# names/ages/photos now live in the Supabase 'players' master table
# instead of the old hardcoded utils/roster.py.
POSITION_ORDER = ["Goalkeepers", "Defenders", "Midfielders", "Forwards"]

INJURY_TYPES = ["New Injury", "New Illness", "Old Injury", "Old Illness"]

# "Diagnosis" group options on Add Medical Information.
BODY_REGIONS = [
    "Head",
    "Neck",
    "Shoulder",
    "Upper arm",
    "Elbow",
    "Forearm",
    "Wrist",
    "Hand",
    "Chest",
    "Thoracic",
    "Lumbar",
    "Abdominal",
    "Groin/hip",
    "Thigh",
    "Knee",
    "Lower leg",
    "Ankle",
    "Foot",
    "Sacrum",
]
PATHOLOGY_TYPES = [
    "Muscle injury",
    "Muscle contusion",
    "Tendinopathy",
    "Joint sprain",
    "Fracture",
    "Bone contusion",
    "Synovitis/capsulitis",
    "Cartilage injury",
    "Bursitis",
    "Skin contusion",
    "Laceration",
    "Brain/spinal injury",
    "Peripheral nerve injury",
    "LGRP",
    "Impingement",
    "Meniscal injury",
    "Tendon rupture",
    "Bone stress injury",
    "Chronic instability",
    "Abrasion",
    "Pain without tissue type specified",
]
SIDE_OPTIONS = ["Left", "Center", "Right", "Bilateral", "NA"]
ONSET_TYPES = [
    "Sudden onset, non-contact",
    "Sudden onset, indirect contact",
    "Sudden onset, direct contact",
    "Gradual onset",
    "Other",
]

# "Occurred in" options on Add Medical Information — Initial Information.
# Previously a dropdown built from distinct gps_session_data sessions
# (see build_occurred_in_options, still used by Record RPE below); this is
# now a fixed list unrelated to uploaded GPS data.
OCCURRED_IN_OPTIONS = [
    "Match",
    "Performance/Gym",
    "Team Training",
    "Individual Training",
    "Non-football Activity",
    "Daily Life / Non-sport",
]

# "Injury Mechanism" options on Add Medical Information — Diagnosis.
# Presented as a searchable dropdown that also accepts free text
# (st.selectbox(..., accept_new_options=True)) rather than a strict enum.
INJURY_MECHANISM_OPTIONS = [
    "Blocking ball",
    "Body check by opponent",
    "Change of direction",
    "Contact twisting",
    "Contact with opponent",
    "Cramping",
    "Deadlift",
    "Deceleration",
    "Diving (GK)",
    "Fall on ground",
    "Gradual onset",
    "Hit by ball",
    "Hyper-extended",
    "Non-contact twisting",
    "Overuse",
    "Passing ball",
    "Shooting ball",
    "Sprinting",
    "Squatting",
    "Stuck in ground",
    "Tackle by opponent",
    "Jumping",
    "Landing",
]

# Options for both the Overall RPE and Local RPE dropdowns on Record RPE.
RPE_LABELS = [
    "1: Rest",
    "2: Very easy",
    "3: Easy",
    "4: Light",
    "5: Moderate",
    "6: Somewhat hard",
    "7: Hard",
    "8: Very hard",
    "9: Extremely hard",
    "10: Maximum",
]

STATUS_OPTIONS = [
    "Available",
    "Available - Recurring Medical Attention",
    "Available - Modified",
    "Unavailable",
]
STATUS_DISPLAY = {
    "Available": "🟢 Available",
    "Available - Recurring Medical Attention": "🟢 Available - Attention",
    "Available - Modified": "🟠 Available - Modified",
    "Unavailable": "🔴 Unavailable",
}
# Shorter label for the status pill on player cards — the full status
# name wraps/overflows the card width, so this is a display-only
# shortening. The underlying status value stored/saved is unchanged.
STATUS_CARD_LABELS = {
    "Available - Recurring Medical Attention": "Available - Attention",
}
# Background/border tint per status, used to shade each card.
STATUS_CARD_COLORS = {
    "Available": {"bg": "#e6f4ea", "border": "#34a853"},
    "Available - Recurring Medical Attention": {"bg": "#c8e6c9", "border": "#2e7d32"},
    "Available - Modified": {"bg": "#fff4e0", "border": "#f9a825"},
    "Unavailable": {"bg": "#fdecea", "border": "#e53935"},
}
# Solid fill for the status pill itself (needs more contrast than the
# light card tint above, since the pill sits on top of the shaded card).
STATUS_PILL_COLORS = {
    "Available": "#34a853",
    "Available - Recurring Medical Attention": "#2e7d32",
    "Available - Modified": "#f9a825",
    "Unavailable": "#e53935",
}
POSITION_ABBR = {
    "Goalkeepers": "GK",
    "Defenders": "D",
    "Midfielders": "M",
    "Forwards": "F",
}
# Deliberately distinct from STATUS_PILL_COLORS (green/orange/red) so the
# position badge and status pill don't get visually confused on the card.
POSITION_COLORS = {
    "Goalkeepers": "#8e44ad",   # purple
    "Defenders": "#2980b9",     # blue
    "Midfielders": "#16a085",   # teal
    "Forwards": "#34495e",      # slate
}
CARD_GRID_COLUMNS = 7  # a 21-30 player squad fits in ~3-4 rows at 7 columns

# Extra fields entered manually in the Upload tab only when Session Type
# is "Match" (Participation Status instead comes pre-filled in the CSV
# itself, so it isn't collected here).
MATCH_INFO_FIELDS = ["Competition", "Opposition", "Match Date", "Home Team", "Away Team", "Home Team Score", "Away Team Score"]

# Maps sanitized Supabase columns (gps_session_data) to the display names
# utils/gps_dashboard.py expects (ported as-is from the standalone dashboard).
GPS_DASHBOARD_COLUMN_MAP = {
    "player": "Player Name",
    "total_distance_m": "Total Distance (m)",
    "hsr_distance_m": "High Speed Running (m)",
    "sprint_distance_m": "Sprint Distance (m)",
    "hi_actions": "High Intensity Actions",
    "hmld_m": "High Intensity Distance (m)",
    "max_speed_km_per_h": "Max Speed (km/h)",
    "active_duration_min": "Game Minutes (mins)",
    "match_date": "Match Date",
    "opposition": "Opposition",
    "competition": "Competition",
    "home_team": "Home Team",
    "away_team": "Away Team",
    "home_team_score": "Home Team Score",
    "away_team_score": "Away Team Score",
}


PROFILE_PIC_DIR = Path(__file__).parent / "utils" / "profilepic"


@st.cache_data
def load_local_avatar_data_uri(filename: str):
    """Reads utils/profilepic/<filename> and returns a base64 data URI, or
    None if the file doesn't exist. Data URIs work everywhere (local dev,
    Streamlit Cloud, etc.) since the browser never needs direct filesystem
    access — the image bytes are embedded right in the HTML.

    Cached since the same file's bytes/encoding never change between
    reruns — avoids re-reading and re-encoding every player's photo from
    disk on every single page rerun (a big chunk of the old "everything
    reloads" lag, on top of the per-card fragments above).
    """
    path = PROFILE_PIC_DIR / filename
    if not path.exists():
        return None
    ext = path.suffix.lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "jpeg")
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/{mime};base64,{encoded}"


def get_initials(name: str) -> str:
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper()


def render_avatar_html(player: dict, color: str) -> str:
    """Absolutely-positioned avatar for a card's top-right corner.

    Looks for a photo in this order:
      1. player['photo_path'] — a filename inside utils/profilepic/
         (e.g. "liam_carter.jpg"), loaded and embedded as a data URI.
      2. player['photo_url'] — a plain web URL.
      3. Falls back to a colored initials circle if neither is set.

    Add either key per player in utils/roster.py once real photos exist.
    """
    photo_src = None
    if player.get("photo_path"):
        photo_src = load_local_avatar_data_uri(player["photo_path"])
    if not photo_src and player.get("photo_url"):
        photo_src = player["photo_url"]

    if photo_src:
        return (
            f"<img src='{photo_src}' style='position:absolute; top:8px; right:5px; "
            f"width:56px; height:56px; border-radius:50%; object-fit:cover; z-index:2;' />"
        )
    initials = get_initials(player["name"])
    return (
        f"<div style='position:absolute; top:8px; right:5px; width:56px; height:56px; "
        f"border-radius:50%; background-color:{color}; color:#ffffff; display:flex; "
        f"align-items:center; justify-content:center; font-size:1.1rem; font-weight:700; "
        f"z-index:2;'>{initials}</div>"
    )


def slugify(text: str) -> str:
    """Safe suffix for Streamlit container keys / CSS class names."""
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", text)


@st.cache_resource
def get_supabase_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def write_to_supabase(df: pd.DataFrame, table_name: str):
    supabase = get_supabase_client()
    records = df.to_dict(orient="records")
    # Insert in chunks to stay well under request size limits on large files.
    chunk_size = 500
    for i in range(0, len(records), chunk_size):
        supabase.table(table_name).insert(records[i : i + chunk_size]).execute()


@st.cache_data(ttl=60)
def read_table(table_name: str) -> pd.DataFrame:
    """Fetch every row from a Supabase table, paginating past PostgREST's
    default max-rows-per-request cap (commonly 1000) so large tables (e.g.
    gps_session_data with thousands of rows) aren't silently truncated."""
    supabase = get_supabase_client()
    page_size = 1000
    start = 0
    all_rows = []
    while True:
        response = (
            supabase.table(table_name)
            .select("*")
            .range(start, start + page_size - 1)
            .execute()
        )
        rows = response.data
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        start += page_size
    return pd.DataFrame(all_rows)


@st.cache_data(ttl=30)
def get_current_player_data(team: str) -> dict:
    """Latest committed status + medical notes per player for a team.

    Keyed by player name. Players with no committed record yet are simply
    absent — callers should default to 'Available' / empty notes.
    """
    supabase = get_supabase_client()
    response = (
        supabase.table(AVAILABILITY_TABLE)
        .select("*")
        .eq("team", team)
        .order("recorded_at", desc=True)
        .execute()
    )
    df = pd.DataFrame(response.data)
    if df.empty:
        return {}
    latest = df.drop_duplicates(subset="player", keep="first")
    return {
        row["player"]: {
            "status": row["status"],
            "medical_notes": "" if pd.isna(row.get("medical_notes")) else row.get("medical_notes"),
            "modification_notes": "" if pd.isna(row.get("modification_notes")) else row.get("modification_notes"),
        }
        for _, row in latest.iterrows()
    }


def write_availability(records: list):
    supabase = get_supabase_client()
    supabase.table(AVAILABILITY_TABLE).insert(records).execute()


def build_roster_dict(players_df: pd.DataFrame) -> dict:
    """{team: {position: [player_dict, ...]}}, sourced from the Supabase
    'players' master reference table — replaces the old hardcoded
    utils/roster.py. Inactive players (active == False) are excluded.
    """
    roster = {}
    if players_df.empty:
        return roster
    df = players_df.copy()
    if "active" in df.columns:
        df = df[df["active"] != False]  # keep True/missing, drop explicit False
    for team, team_df in df.groupby("team"):
        team_roster = {}
        for position, pos_df in team_df.groupby("position"):
            team_roster[position] = [
                {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "age": row.get("age"),
                    "photo_path": row.get("photo_path") if pd.notna(row.get("photo_path")) else None,
                    "photo_url": row.get("photo_url") if pd.notna(row.get("photo_url")) else None,
                }
                for _, row in pos_df.sort_values("name").iterrows()
            ]
        roster[team] = team_roster
    return roster


def get_team_players(players_df: pd.DataFrame, team: str) -> list:
    """Flat, name-sorted list of active player dicts for one team, used to
    populate the 'Athlete' dropdown on the Add Medical Information tab."""
    if players_df.empty or "team" not in players_df.columns:
        return []
    df = players_df[players_df["team"] == team]
    if "active" in df.columns:
        df = df[df["active"] != False]
    return sorted(df.to_dict(orient="records"), key=lambda p: str(p.get("name", "")))


def build_occurred_in_options(sessions_df: pd.DataFrame, team: str) -> dict:
    """{'01 Aug 2026 — Match': (raw_session_date, session_type), ...} built
    from the distinct (session_date, session_type) pairs already uploaded
    to gps_session_data for a team, most recent first."""
    if sessions_df.empty or "team" not in sessions_df.columns:
        return {}
    df = sessions_df[sessions_df["team"] == team]
    if df.empty or "session_date" not in df.columns or "session_type" not in df.columns:
        return {}
    pairs = df[["session_date", "session_type"]].dropna().drop_duplicates()
    pairs["_sort"] = pd.to_datetime(pairs["session_date"], errors="coerce")
    pairs = pairs.sort_values("_sort", ascending=False)

    options = {}
    for _, row in pairs.iterrows():
        parsed = pd.to_datetime(row["session_date"], errors="coerce")
        display_date = parsed.strftime("%d %b %Y") if pd.notna(parsed) else str(row["session_date"])
        label = f"{display_date} — {row['session_type']}"
        options[label] = (row["session_date"], row["session_type"])
    return options


def write_medical_record(record: dict):
    supabase = get_supabase_client()
    supabase.table(MEDICAL_TABLE).insert(record).execute()


def update_medical_record(record_id, updates: dict):
    supabase = get_supabase_client()
    supabase.table(MEDICAL_TABLE).update(updates).eq("id", record_id).execute()


def write_rpe_records(records: list):
    supabase = get_supabase_client()
    supabase.table(RPE_TABLE).insert(records).execute()


def write_treatment_observation(record: dict):
    supabase = get_supabase_client()
    supabase.table(TREATMENT_TABLE).insert(record).execute()


def get_recent_session_history(team: str, player: str, limit: int = 5):
    """Last N sessions' active_duration_min + opposition for a player.

    Returns a list of formatted strings, or a single string with an
    explanatory message if the data isn't available yet (e.g. the
    'opposition' column hasn't been added to gps_session_data).
    """
    try:
        supabase = get_supabase_client()
        response = (
            supabase.table("gps_session_data")
            .select("session_date, active_duration_min, opposition")
            .eq("team", team)
            .eq("player", player)
            .order("session_date", desc=True)
            .limit(limit)
            .execute()
        )
        rows = response.data
        if not rows:
            return "No session data found for this player yet."
        lines = []
        for row in rows:
            duration = row.get("active_duration_min", "?")
            opposition = row.get("opposition") or "Unknown opponent"
            lines.append(f"{duration}min vs {opposition}")
        return lines
    except Exception as e:
        return (
            f"Session data unavailable: {e}. This needs an 'opposition' "
            "column on gps_session_data — add it when that data is ready."
        )


# ---------------------------------------------------------------------------
# Sidebar navigation (the only place page navigation lives from here on).
# All sections/subsections are shown at once, pre-expanded, under a bold
# section heading, each with a monochrome text-symbol prefix. Default
# Streamlit button styling is left as-is; subsections get a small visual
# indent via an empty spacer column rather than any custom CSS.
# ---------------------------------------------------------------------------
NAV_STRUCTURE = {
    "Performance": [
        ("↑", "Upload"),
        ("▦", "GPS Match Dashboard"),
        ("◐", "Record RPE"),
        ("▤", "Match History"),
    ],
    "Medical": [
        ("⚕", "View Medical Information"),
        ("+", "Add Medical Information"),
        ("✎", "Add/Edit Observations"),
        ("●", "Player Availability"),
    ],
}

if "nav_section" not in st.session_state:
    st.session_state.nav_section = "Medical"
if "nav_page" not in st.session_state:
    st.session_state.nav_page = "Player Availability"

st.sidebar.title("Navigation")
for section, pages in NAV_STRUCTURE.items():
    st.sidebar.markdown(f"**{section}**")
    for symbol, page in pages:
        is_active = (
            st.session_state.nav_section == section and st.session_state.nav_page == page
        )
        indent_col, btn_col = st.sidebar.columns([0.12, 0.88])
        with btn_col:
            if st.button(
                f"{symbol}    {page}",
                key=f"navbtn_{section}_{page}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.nav_section = section
                st.session_state.nav_page = page
                st.rerun()

nav_section = st.session_state.nav_section
nav_page = st.session_state.nav_page

# ---------------------------------------------------------------------------
# Header: app title + club logo top-right, a two-line "breadcrumb" (section,
# then page), and a divider with some vertical padding in place of the old
# per-page caption text.
# ---------------------------------------------------------------------------
title_col, logo_col = st.columns([8, 1])
with title_col:
    st.title("LCSFC Performance & Medical Database")
with logo_col:
    st.image(
        "https://upload.wikimedia.org/wikipedia/en/e/e3/Lion_City_Sailors_FC_logo.svg",
        width=70,
    )

st.markdown(
    f"<div style='margin-top:-8px; font-size:1.3rem; font-weight:700;'>{nav_section}</div>"
    f"<div style='font-size:1rem; font-weight:500; color:#555555;'>{nav_page}</div>",
    unsafe_allow_html=True,
)
st.divider()
st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

if nav_section == "Performance" and nav_page == "Upload":
    col1, col2 = st.columns(2)
    with col1:
        source_label = st.selectbox("Data source", list(SOURCE_TABLES.keys()))
        table_name = SOURCE_TABLES[source_label]
        team = st.selectbox("Team", TEAMS)
    with col2:
        session_date = st.date_input("Session date")
        session_type = st.selectbox("Session type", SESSION_TYPES)
        if session_type == "Other":
            session_type = st.text_input("Specify session type") or "Other"

    match_info = {}
    if session_type == "Match":
        st.markdown("**Match details**")
        mcol1, mcol2 = st.columns(2)
        with mcol1:
            match_info["Competition"] = st.text_input("Competition")
            match_info["Opposition"] = st.text_input("Opposition")
            match_info["Match Date"] = st.date_input("Match Date", key="match_date_input")
        with mcol2:
            match_info["Home Team"] = st.text_input("Home Team")
            match_info["Away Team"] = st.text_input("Away Team")
            score_col1, score_col2 = st.columns(2)
            with score_col1:
                match_info["Home Team Score"] = st.number_input("Home Team Score", min_value=0, step=1)
            with score_col2:
                match_info["Away Team Score"] = st.number_input("Away Team Score", min_value=0, step=1)

    uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])

    if uploaded_file:
        df = pd.read_csv(uploaded_file, encoding="utf-8-sig")
        df.columns = sanitize_columns(df.columns)

        # Stamp session tagging onto every row.
        df.insert(0, "team", team)
        df.insert(1, "session_date", session_date.isoformat())
        df.insert(2, "session_type", session_type)

        # Match-only fields, also stamped onto every row (same pattern as
        # team/session_date above) — only present when Session Type = Match.
        if session_type == "Match":
            df["competition"] = match_info["Competition"]
            df["opposition"] = match_info["Opposition"]
            df["match_date"] = match_info["Match Date"].isoformat()
            df["home_team"] = match_info["Home Team"]
            df["away_team"] = match_info["Away Team"]
            df["home_team_score"] = match_info["Home Team Score"]
            df["away_team_score"] = match_info["Away Team Score"]

        st.subheader("Preview")
        st.dataframe(df.head(20), use_container_width=True)
        st.caption(
            f"{len(df)} rows will be written to '{table_name}' as "
            f"{team} / {session_date} / {session_type}."
        )

        if st.button("Upload to Supabase", type="primary"):
            with st.spinner("Writing data..."):
                try:
                    write_to_supabase(df, table_name)
                    read_table.clear()  # invalidate cached preview used elsewhere in the app
                    st.success(f"Wrote {len(df)} rows to '{table_name}'.")
                except Exception as e:
                    st.error(
                        f"Failed to write data: {e}\n\n"
                        "Common causes: the table doesn't exist yet in Supabase, "
                        "or a column in the CSV doesn't match the table schema."
                    )


elif nav_section == "Performance" and nav_page == "GPS Match Dashboard":
    # Print / "Save as PDF": only the scoreline, Team Data Summary and Team
    # Overview sections (each wrapped in its own st.container(key=...)
    # below) stay visible when the page is printed from the browser;
    # everything else on this page — selectors, sidebar, Streamlit chrome —
    # is hidden. visibility (not display) is used on the wrapping
    # containers so their contents can still opt back in, while the
    # selector row is simply removed with display:none since nothing
    # inside it needs to print.
    st.markdown(
        """
        <style>
        @media print {
            section[data-testid="stSidebar"],
            header[data-testid="stHeader"],
            div[data-testid="stToolbar"],
            div[data-testid="stDecoration"],
            #MainMenu,
            footer {
                display: none !important;
            }
            .st-key-print_hide_filters {
                display: none !important;
            }
            /* The Team Overview bar charts size themselves to their
               column via a ResizeObserver, which doesn't refire for
               print — so on-screen they fill the column, but in print
               they keep whatever pixel width they last rendered at on
               screen. Forcing the chart's SVG to 100% width (with
               height:auto to keep it undistorted) makes it fill the
               column in print too. */
            .st-key-print_team_overview [data-testid="stVegaLiteChart"],
            .st-key-print_team_overview .vega-embed {
                width: 100% !important;
            }
            .st-key-print_team_overview [data-testid="stVegaLiteChart"] svg,
            .st-key-print_team_overview .vega-embed svg,
            .st-key-print_team_overview .vega-embed canvas {
                width: 100% !important;
                height: auto !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Keep the dashboard selectors together in one row (hidden when printing).
    with st.container(key="print_hide_filters"):
        filter_col1, filter_col2 = st.columns([1, 2])

        with filter_col1:
            gps_team = st.selectbox("Team", TEAMS, key="gps_dash_team")

    try:
        raw = read_table("gps_session_data")
    except Exception as e:
        raw = pd.DataFrame()
        st.info(f"Could not load gps_session_data yet ({e}).")

    if not raw.empty and "session_type" in raw.columns:
        raw = raw[(raw["team"] == gps_team) & (raw["session_type"] == "Match")].copy()

    if raw.empty:
        st.info("No match data uploaded yet for this team. Upload a CSV in the Upload tab with Session Type = Match.")
    else:
        # Rename sanitized Supabase columns to what utils/gps_dashboard.py expects.
        rename_map = {k: v for k, v in GPS_DASHBOARD_COLUMN_MAP.items() if k in raw.columns}
        raw = raw.rename(columns=rename_map)

        missing_required = [c for c in gpsd.METRIC_COLUMNS + ["Player Name"] if c not in raw.columns]
        if missing_required:
            st.warning(f"Missing expected column(s) for this chart: {', '.join(missing_required)}.")
        else:
            for m in gpsd.METRIC_COLUMNS:
                raw[m] = pd.to_numeric(raw[m], errors="coerce")

            raw, id_cols_present = gpsd.build_match_labels(raw)
            match_order_desc = gpsd.sorted_match_labels(raw, id_cols_present, descending=True)
            has_multiple_matches = raw[gpsd.MATCH_LABEL_COL].nunique() > 1

            with filter_col2:
                if has_multiple_matches:
                    selected_match_label = st.selectbox(
                        "Match (Date + Opposition)", options=match_order_desc, key="gps_dash_match_select"
                    )
                else:
                    selected_match_label = raw[gpsd.MATCH_LABEL_COL].iloc[0]

            selected_df = raw[raw[gpsd.MATCH_LABEL_COL] == selected_match_label].copy()
            all_players = sorted(raw["Player Name"].dropna().unique().tolist())

            # Add visual breathing room between the selectors and scoreline.
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)

            with st.container(key="print_scoreline"):
                gpsd.render_match_header(selected_df.iloc[0])

            # Greater breathing room between the scoreline and the summary section.
            st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

            with st.container(key="print_team_summary"):
                st.subheader("Team Data Summary")
                historical_df = raw[raw[gpsd.MATCH_LABEL_COL] != selected_match_label] if has_multiple_matches else None

                # One connected strip of cards (shared border, no gaps
                # between them) rather than separate st.metric widgets.
                card_html_parts = []
                for i, metric in enumerate(gpsd.SUMMARY_METRICS):
                    selected_val = gpsd.team_per90(selected_df, metric)
                    label = html.escape(gpsd.METRIC_LABELS[metric])

                    delta_html = ""
                    if historical_df is not None and not historical_df.empty:
                        hist_val = gpsd.team_per90(historical_df, metric)
                        if hist_val:
                            diff = selected_val - hist_val
                            pct = diff / hist_val * 100
                            delta_color = "#2e7d32" if diff >= 0 else "#c62828"
                            arrow = "▲" if diff >= 0 else "▼"
                            delta_html = (
                                f"<div style='font-size:1.05rem; font-weight:600; "
                                f"color:{delta_color}; margin-top:3px;'>{arrow} "
                                f"{diff:+,.1f} ({pct:+.1f}%)</div>"
                            )

                    unit_suffix = "" if metric == "High Intensity Actions" else " m"

                    border_style = (
                        "" if i == len(gpsd.SUMMARY_METRICS) - 1 else "border-right:1px solid #e2e2e2;"
                    )
                    card_html_parts.append(
                        f"<div style='flex:1; min-width:0; padding:14px 10px; text-align:center; "
                        f"{border_style}' title='Team per-90 rate — {label} "
                        f"(selected match vs. all other matches)'>"
                        f"<div style='font-size:0.78rem; color:#6b6b6b; text-transform:uppercase; "
                        f"letter-spacing:0.5px; margin-bottom:4px;'>{label}</div>"
                        f"<div style='font-size:1.35rem; font-weight:700; color:#1a1a1a;'>"
                        f"{selected_val:,.1f}{unit_suffix}</div>"
                        f"{delta_html}"
                        f"</div>"
                    )

                st.markdown(
                    "<div style='display:flex; border:1px solid #e2e2e2; border-radius:10px; "
                    "overflow:hidden; background:#ffffff;'>" + "".join(card_html_parts) + "</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("---")
            with st.container(key="print_team_overview"):
                st.subheader("Team Overview")
                overview_df = selected_df
                if overview_df.empty:
                    st.warning("No player data available for this match.")
                else:
                    if selected_match_label in match_order_desc:
                        idx = match_order_desc.index(selected_match_label)
                        window_labels = match_order_desc[idx: idx + 5]
                    else:
                        window_labels = [selected_match_label]
                    gpsd.render_matrix_chart(
                        overview_df, raw_df=raw, window_labels=window_labels, sort_by="Game Minutes (mins)"
                    )
                st.caption("Sorted by Game Minutes, highest to lowest. Hover a bar to see the 5 most recent matches.")

elif nav_section == "Performance" and nav_page == "Record RPE":
    rpe_team = st.selectbox("Team", TEAMS, key="rpe_team")

    try:
        rpe_sessions_df = read_table("gps_session_data")
    except Exception as e:
        rpe_sessions_df = pd.DataFrame()
        st.info(f"Could not load session data yet ({e}).")

    session_options = build_occurred_in_options(rpe_sessions_df, rpe_team)

    if not session_options:
        st.info(
            f"No sessions found for {rpe_team} in gps_session_data yet — "
            "upload one in the Upload page first."
        )
    else:
        session_label = st.selectbox(
            "Session (Date + Session Type)", list(session_options.keys()), key="rpe_session"
        )
        session_date, session_type_val = session_options[session_label]

        try:
            players_df = read_table(PLAYERS_TABLE)
        except Exception as e:
            players_df = pd.DataFrame()
            st.info(
                f"Could not load the players table yet ({e}). Run "
                "schema_players.sql in Supabase and add your roster there."
            )

        team_players = get_team_players(players_df, rpe_team)

        if not team_players:
            st.warning(f"No players found for {rpe_team}. Add players to the 'players' table first.")
        else:
            st.markdown(f"**{len(team_players)} player(s) — {session_label}**")

            rpe_selections = {}
            for player in team_players:
                name = player["name"]
                st.markdown(f"**{name}**")
                rcol1, rcol2 = st.columns(2)
                with rcol1:
                    overall_label = st.selectbox(
                        "Overall RPE", RPE_LABELS, key=f"rpe_overall_{rpe_team}_{name}"
                    )
                with rcol2:
                    local_label = st.selectbox(
                        "Local RPE", RPE_LABELS, key=f"rpe_local_{rpe_team}_{name}"
                    )
                rpe_selections[name] = (overall_label, local_label)

            if st.button("Save RPE Entries", type="primary"):
                records = []
                for player in team_players:
                    name = player["name"]
                    overall_label, local_label = rpe_selections[name]
                    records.append(
                        {
                            "player_id": player.get("id"),
                            "player_name": name,
                            "team": rpe_team,
                            "session_date": str(session_date),
                            "session_type": session_type_val,
                            "overall_rpe": int(overall_label.split(":")[0]),
                            "local_rpe": int(local_label.split(":")[0]),
                            "recorded_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                try:
                    write_rpe_records(records)
                    read_table.clear()
                    st.success(f"Saved RPE for {len(records)} player(s).")
                except Exception as e:
                    st.error(
                        f"Save failed: {e}. If the table doesn't exist "
                        "yet, run schema_rpe.sql."
                    )

elif nav_section == "Performance" and nav_page == "Match History":
    try:
        sessions_df = read_table("gps_session_data")
    except Exception as e:
        sessions_df = pd.DataFrame()
        st.info(f"Could not load session data yet ({e}).")

    if sessions_df.empty or "session_type" not in sessions_df.columns:
        st.info("No session data uploaded yet.")
    else:
        match_df = sessions_df[sessions_df["session_type"] == "Match"].copy()
        if match_df.empty or "player" not in match_df.columns:
            st.info("No Match-type sessions uploaded yet — upload one in the Upload page first.")
        else:
            player_options = sorted(match_df["player"].dropna().unique().tolist())
            if not player_options:
                st.info("No player data found in the uploaded match sessions.")
            else:
                selected_player = st.selectbox("Player", player_options, key="match_history_player")
                player_matches = match_df[match_df["player"] == selected_player].copy()

                def _build_result(row):
                    """'[own score]-[opposition score] (W/L/D)', worked out
                    by matching the 'opposition' text against home_team /
                    away_team to figure out which side is the player's own
                    team. Returns None if the match info doesn't line up
                    (e.g. opposition doesn't match either side exactly) or
                    either score is missing."""
                    home, away, opp = row.get("home_team"), row.get("away_team"), row.get("opposition")
                    home_score, away_score = row.get("home_team_score"), row.get("away_team_score")
                    if pd.isna(home) or pd.isna(away) or pd.isna(opp):
                        return None
                    if pd.isna(home_score) or pd.isna(away_score):
                        return None

                    home_n = str(home).strip().lower()
                    away_n = str(away).strip().lower()
                    opp_n = str(opp).strip().lower()

                    if away_n == opp_n:
                        own_score, opp_score = home_score, away_score
                    elif home_n == opp_n:
                        own_score, opp_score = away_score, home_score
                    else:
                        return None

                    own_score, opp_score = int(own_score), int(opp_score)
                    if own_score > opp_score:
                        outcome = "W"
                    elif own_score < opp_score:
                        outcome = "L"
                    else:
                        outcome = "D"

                    return f"{own_score}-{opp_score} ({outcome})"

                player_matches["result"] = player_matches.apply(_build_result, axis=1)

                # Latest match first, by actual session date.
                player_matches["_sort_date"] = pd.to_datetime(
                    player_matches.get("session_date"), errors="coerce"
                )
                player_matches = player_matches.sort_values("_sort_date", ascending=False)

                def _fmt_match_date(value):
                    parsed = pd.to_datetime(value, errors="coerce")
                    return parsed.strftime("%d %b %Y") if pd.notna(parsed) else str(value)

                if "session_date" in player_matches.columns:
                    player_matches["session_date"] = player_matches["session_date"].apply(_fmt_match_date)

                display_cols_map = {
                    "session_date": "Session Date",
                    "opposition": "Opposition",
                    "competition": "Competition",
                    "result": "Result",
                    "participation_status": "Participation Status",
                    "active_duration_min": "Active Duration (min)",
                    "total_distance_m": "Total Distance (m)",
                    "hsr_distance_m": "HSR Distance (m)",
                    "sprint_distance_m": "Sprint Distance (m)",
                    "hi_actions": "HI Actions",
                    "hmld_m": "HMLD (m)",
                }
                available_cols = [c for c in display_cols_map if c in player_matches.columns]
                display_df = (
                    player_matches[available_cols]
                    .rename(columns=display_cols_map)
                    .reset_index(drop=True)
                )

                if display_df.empty:
                    st.info(f"No match history found for {selected_player}.")
                elif HAS_AGGRID:
                    gb = GridOptionsBuilder.from_dataframe(display_df)
                    gb.configure_default_column(resizable=True, sortable=True, filter=True)
                    if "Result" in display_df.columns:
                        gb.configure_column("Result", cellStyle={"fontWeight": "700"})

                    # Always show these headers in full (wrapped onto a
                    # second line if needed) rather than letting
                    # fit_columns_on_grid_load's auto-sizing truncate them.
                    for full_header_col in ("Opposition", "Participation Status", "Active Duration (min)"):
                        if full_header_col in display_df.columns:
                            gb.configure_column(
                                full_header_col, wrapHeaderText=True, autoHeaderHeight=True
                            )

                    # Shade "Active Duration (min)" light-to-dark green
                    # across a fixed 0-90 range (values are clamped to
                    # that range for the colour, not for the number shown).
                    if "Active Duration (min)" in display_df.columns:
                        duration_cell_style = JsCode(
                            """
                            function(params) {
                                var v = Number(params.value);
                                if (params.value === null || params.value === undefined || isNaN(v)) {
                                    return {};
                                }
                                var t = Math.max(0, Math.min(90, v)) / 90;
                                var r = Math.round(232 + (27 - 232) * t);
                                var g = Math.round(245 + (94 - 245) * t);
                                var b = Math.round(233 + (32 - 233) * t);
                                return {
                                    backgroundColor: 'rgb(' + r + ',' + g + ',' + b + ')',
                                    color: t > 0.55 ? 'white' : 'black'
                                };
                            }
                            """
                        )
                        gb.configure_column("Active Duration (min)", cellStyle=duration_cell_style)

                    grid_options = gb.build()
                    AgGrid(
                        display_df,
                        gridOptions=grid_options,
                        fit_columns_on_grid_load=True,
                        theme="balham",
                        allow_unsafe_jscode=True,
                    )
                else:
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    st.caption(
                        "Install `streamlit-aggrid` (add it to requirements.txt) "
                        "for a styled, sortable/filterable grid here."
                    )

elif nav_section == "Medical" and nav_page == "View Medical Information":
    try:
        medical_df = read_table(MEDICAL_TABLE)
    except Exception as e:
        medical_df = pd.DataFrame()
        st.info(
            f"Could not load medical_records yet ({e}). Run "
            "schema_medical.sql in Supabase to create the table."
        )

    if medical_df.empty:
        st.info("No medical entries logged yet.")
    else:
        # Pull in 'status' from player_availability. Add Medical Information
        # writes both tables with the same recorded_at timestamp for a given
        # submission, so joining on (player, team, recorded_at) recovers the
        # status that was set alongside each medical entry. Entries logged
        # before this join existed, or whose status was later changed
        # elsewhere, will show a blank status here.
        try:
            availability_df = read_table(AVAILABILITY_TABLE)
        except Exception:
            availability_df = pd.DataFrame()

        if not availability_df.empty and {"player", "team", "recorded_at", "status"}.issubset(
            availability_df.columns
        ):
            status_lookup = availability_df[["player", "team", "recorded_at", "status"]].rename(
                columns={"player": "player_name"}
            )
            medical_df = medical_df.merge(
                status_lookup, on=["player_name", "team", "recorded_at"], how="left"
            )
        elif "status" not in medical_df.columns:
            medical_df["status"] = None

        mv1, mv2, mv3 = st.columns(3)
        with mv1:
            team_filter_m = st.multiselect(
                "Team", sorted(medical_df["team"].dropna().unique()), key="med_view_team"
            )
        with mv2:
            player_filter_m = st.multiselect(
                "Athlete", sorted(medical_df["player_name"].dropna().unique()), key="med_view_player"
            )
        with mv3:
            injury_filter_m = st.multiselect(
                "Injury Type", sorted(medical_df["injury_type"].dropna().unique()), key="med_view_injury"
            )

        filtered_m = medical_df.copy()
        if team_filter_m:
            filtered_m = filtered_m[filtered_m["team"].isin(team_filter_m)]
        if player_filter_m:
            filtered_m = filtered_m[filtered_m["player_name"].isin(player_filter_m)]
        if injury_filter_m:
            filtered_m = filtered_m[filtered_m["injury_type"].isin(injury_filter_m)]

        sort_col = "recorded_at" if "recorded_at" in filtered_m.columns else "player_name"
        filtered_m = filtered_m.sort_values(sort_col, ascending=False)

        display_cols = [
            c
            for c in [
                "player_name",
                "injury_type",
                "date_of_injury",
                "body_region",
                "pathology",
                "specific_description",
                "status",
            ]
            if c in filtered_m.columns
        ]
        display_df = filtered_m[display_cols].reset_index(drop=True)

        def _shade_by_status(row):
            color = STATUS_CARD_COLORS.get(row.get("status"), {}).get("bg", "")
            return [f"background-color: {color}" if color else "" for _ in row]

        st.dataframe(
            display_df.style.apply(_shade_by_status, axis=1),
            use_container_width=True,
        )


elif nav_section == "Medical" and nav_page == "Add Medical Information":
    try:
        players_df = read_table(PLAYERS_TABLE)
    except Exception as e:
        players_df = pd.DataFrame()
        st.info(
            f"Could not load the players table yet ({e}). Run "
            "schema_players.sql in Supabase and add your roster there."
        )

    med_team = st.selectbox("Team", TEAMS, key="med_add_team")
    team_players = get_team_players(players_df, med_team)

    if not team_players:
        st.warning(f"No players found for {med_team}. Add players to the 'players' table first.")
    else:
        player_options = {p["name"]: p for p in team_players}

        st.subheader("Initial Information")
        mcol1, mcol2 = st.columns(2)
        with mcol1:
            injury_type = st.selectbox("Injury Type", INJURY_TYPES, key="med_injury_type")
            athlete_name = st.selectbox("Athlete", list(player_options.keys()), key="med_athlete")
        with mcol2:
            date_of_injury = st.date_input("Date of Injury", key="med_date_injury")
            date_of_examination = st.date_input("Date of Examination", key="med_date_exam")

        occurred_in = st.selectbox(
            "Occurred in", OCCURRED_IN_OPTIONS, key="med_occurred_in"
        )
        occurred_in_detail = st.text_input(
            "Occurred in - Additional Detail",
            key="med_occurred_in_detail",
            help=(
                "Provide additional context here, for example: "
                "'National Team vs Malaysia' or 'SPL vs Young Lions FC'; "
                "'Stepped on glass'; 'Padel'"
            ),
        )

        st.divider()
        st.subheader("Diagnosis")
        dcol1, dcol2 = st.columns(2)
        with dcol1:
            body_region = st.selectbox("Body Region", BODY_REGIONS, key="med_body_region")
            pathology = st.selectbox("Pathology", PATHOLOGY_TYPES, key="med_pathology")
            specific_description = st.text_input(
                "Specific Description", key="med_specific_description"
            )
        with dcol2:
            side = st.pills(
                "Side", SIDE_OPTIONS, selection_mode="single", default="NA", key="med_side"
            )
            onset_type = st.selectbox("Onset Type", ONSET_TYPES, key="med_onset_type")
            # Searchable dropdown that also accepts free text not in the
            # preset list (typed value is used as-is if it's not a match).
            injury_mechanism = st.selectbox(
                "Injury Mechanism",
                INJURY_MECHANISM_OPTIONS,
                index=None,
                accept_new_options=True,
                filter_mode="fuzzy",
                placeholder="Choose or type a mechanism...",
                key="med_injury_mechanism",
            )

        st.divider()
        st.subheader("Status")
        st.caption("Written to Supabase 'player_availability', same as the Player Availability page.")
        status = st.selectbox("Status", STATUS_OPTIONS, key="med_status")
        medical_notes = st.text_area("Medical Notes", key="med_medical_notes")
        modification_notes = st.text_area("Modification Notes", key="med_modification_notes")

        if st.button("Save Medical Entry", type="primary"):
            selected_player = player_options[athlete_name]
            now_iso = datetime.now(timezone.utc).isoformat()

            medical_record = {
                "player_id": selected_player.get("id"),
                "player_name": athlete_name,
                "team": med_team,
                "injury_type": injury_type,
                "date_of_injury": date_of_injury.isoformat(),
                "date_of_examination": date_of_examination.isoformat(),
                "occurred_in": occurred_in,
                "occurred_in_additional_detail": occurred_in_detail or None,
                "body_region": body_region,
                "pathology": pathology,
                "specific_description": specific_description or None,
                "side": side,
                "onset_type": onset_type,
                "injury_mechanism": injury_mechanism or None,
                "recorded_at": now_iso,
            }
            availability_record = {
                "team": med_team,
                "player": athlete_name,
                "position": selected_player.get("position"),
                "status": status,
                "medical_notes": medical_notes or None,
                "modification_notes": modification_notes or None,
                "recorded_at": now_iso,
            }
            try:
                write_medical_record(medical_record)
                write_availability([availability_record])
                read_table.clear()
                st.success(
                    f"Medical entry saved for {athlete_name} — availability set to '{status}'."
                )
            except Exception as e:
                st.error(
                    f"Save failed: {e}. If the tables don't exist "
                    "yet, run schema_medical.sql and schema_availability.sql."
                )


elif nav_section == "Medical" and nav_page == "Add/Edit Observations":
    if "obs_selected_team" not in st.session_state:
        st.session_state.obs_selected_team = None
    if "obs_selected_player" not in st.session_state:
        st.session_state.obs_selected_player = None

    if st.session_state.obs_selected_player is None:
        # ---- Card grid: pick a player to view/edit their injuries ----
        st.markdown(
            """
            <style>
            div[data-testid="stVerticalBlockBorderWrapper"] { padding: 0.35rem 0.6rem !important; min-height: 200px; }
            div[data-testid="stVerticalBlock"] { gap: 0.25rem; }
            </style>
            """,
            unsafe_allow_html=True,
        )

        try:
            players_df = read_table(PLAYERS_TABLE)
        except Exception as e:
            players_df = pd.DataFrame()
            st.info(
                f"Could not load the players table yet ({e}). Run "
                "schema_players.sql in Supabase and add your roster there."
            )
        roster_by_team = build_roster_dict(players_df)

        obs_team = st.selectbox("Team", TEAMS, key="obs_team")
        roster = roster_by_team.get(obs_team, {})
        if not roster:
            st.info(f"No players found for {obs_team} in the players table yet.")
        else:
            try:
                current_data = get_current_player_data(obs_team)
            except Exception:
                current_data = {}

            flat_players = [
                (position, player)
                for position in POSITION_ORDER
                for player in roster.get(position, [])
            ]

            # Card shading, same status colors as Player Availability.
            card_css_rules = []
            for position, player in flat_players:
                name = player["name"]
                status = current_data.get(name, {}).get("status", "Available")
                colors = STATUS_CARD_COLORS[status]
                key_slug = slugify(f"obscard_{obs_team}_{name}")
                card_css_rules.append(
                    f'.st-key-{key_slug} {{ '
                    f'background-color: {colors["bg"]} !important; '
                    f'border: 1px solid {colors["border"]} !important; '
                    f'position: relative; '
                    f'}}'
                )
            st.markdown(f"<style>{''.join(card_css_rules)}</style>", unsafe_allow_html=True)

            columns = st.columns(CARD_GRID_COLUMNS)
            for i, (position, player) in enumerate(flat_players):
                name = player["name"]
                age = player["age"]
                status = current_data.get(name, {}).get("status", "Available")
                pos_color = POSITION_COLORS[position]
                pill_color = STATUS_PILL_COLORS[status]
                card_key = slugify(f"obscard_{obs_team}_{name}")

                with columns[i % CARD_GRID_COLUMNS]:
                    with st.container(border=True, key=card_key):
                        st.markdown(render_avatar_html(player, pos_color), unsafe_allow_html=True)
                        st.markdown(
                            f"<div style='padding-right:64px; margin-bottom:6px;'><b>{name}</b></div>",
                            unsafe_allow_html=True,
                        )
                        st.caption(f"Age {age}")
                        pill_label = STATUS_CARD_LABELS.get(status, status)
                        st.markdown(
                            f"<div style='display:flex; align-items:center; gap:6px; margin-bottom:12px;'>"
                            f"<div style='width:22px; height:22px; border-radius:50%; "
                            f"background-color:{pos_color}; color:#ffffff; display:flex; "
                            f"align-items:center; justify-content:center; font-size:0.65rem; "
                            f"font-weight:700; flex-shrink:0;'>{POSITION_ABBR[position]}</div>"
                            f"<span style='background-color:{pill_color}; color:#ffffff; "
                            f"padding:2px 10px; border-radius:10px; font-size:0.75rem; "
                            f"font-weight:600; display:inline-block;'>{pill_label}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
                        if st.button(
                            "View Injuries",
                            key=f"obs_select_{obs_team}_{name}",
                            use_container_width=True,
                        ):
                            st.session_state.obs_selected_team = obs_team
                            st.session_state.obs_selected_player = name
                            st.rerun()

    else:
        # ---- Detail page: this player's logged injuries/illnesses, or SOAP ----
        sel_team = st.session_state.obs_selected_team
        sel_player = st.session_state.obs_selected_player

        if "obs_selected_injury_id" not in st.session_state:
            st.session_state.obs_selected_injury_id = None
        if "obs_detail_view" not in st.session_state:
            st.session_state.obs_detail_view = "Injuries"

        def _fmt_date(value):
            parsed = pd.to_datetime(value, errors="coerce")
            return parsed.strftime("%d %b %Y") if pd.notna(parsed) else "—"

        def _fmt(value):
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return "—"
            text = str(value).strip()
            return text if text else "—"

        if st.button("← Back to all players", key="obs_back"):
            st.session_state.obs_selected_player = None
            st.session_state.obs_selected_team = None
            st.session_state.obs_selected_injury_id = None
            st.rerun()

        st.subheader(sel_player)
        st.caption(sel_team)
        st.write("")

        # Injuries/SOAP toggle rendered as two rounded rectangular card
        # buttons rather than a plain radio, for a clearer tab-like look.
        view_col1, view_col2 = st.columns(2)
        with view_col1:
            if st.button(
                "Injuries",
                key="obs_view_injuries_btn",
                use_container_width=True,
                type="primary" if st.session_state.obs_detail_view == "Injuries" else "secondary",
            ):
                st.session_state.obs_detail_view = "Injuries"
                st.rerun()
        with view_col2:
            if st.button(
                "SOAP",
                key="obs_view_soap_btn",
                use_container_width=True,
                type="primary" if st.session_state.obs_detail_view == "SOAP" else "secondary",
            ):
                st.session_state.obs_detail_view = "SOAP"
                st.rerun()
        st.write("")

        if st.session_state.obs_detail_view == "Injuries":
            try:
                medical_df = read_table(MEDICAL_TABLE)
            except Exception as e:
                medical_df = pd.DataFrame()
                st.info(
                    f"Could not load medical_records yet ({e}). Run "
                    "schema_medical.sql in Supabase to create the table."
                )

            if st.session_state.obs_selected_injury_id is None:
                # ---- List of this player's injuries/illnesses ----
                if medical_df.empty:
                    st.info("No injuries or illnesses logged yet.")
                else:
                    player_records = medical_df[medical_df["player_name"] == sel_player].copy()
                    if player_records.empty:
                        st.info(f"No injuries or illnesses logged for {sel_player} yet.")
                    else:
                        # Latest injury first, by actual injury date (not
                        # when the record happened to be entered).
                        player_records["_sort_date"] = pd.to_datetime(
                            player_records["date_of_injury"], errors="coerce"
                        )
                        player_records = player_records.sort_values("_sort_date", ascending=False)

                        # One card per injury/illness entry — sentence-case labels
                        # written directly in the markup rather than relying on
                        # the raw snake_case Supabase column names.
                        for _, rec in player_records.iterrows():
                            injury_date_parsed = pd.to_datetime(rec.get("date_of_injury"), errors="coerce")
                            resolved_value = rec.get("injury_resolved_date")
                            resolved_parsed = pd.to_datetime(resolved_value, errors="coerce")
                            is_resolved = pd.notna(resolved_parsed)

                            with st.container(border=True):
                                head_col, date_col = st.columns([3, 1])
                                with head_col:
                                    st.markdown(f"**{_fmt(rec.get('injury_type'))}**")
                                with date_col:
                                    status_label = "Resolved" if is_resolved else "Ongoing"
                                    status_color = "#2e7d32" if is_resolved else "#e53935"
                                    st.markdown(
                                        f"<div style='text-align:right;'>"
                                        f"<div style='font-size:1.05rem; font-weight:700;'>"
                                        f"{_fmt_date(rec.get('date_of_injury'))}</div>"
                                        f"<div style='color:{status_color}; font-size:1rem; "
                                        f"font-weight:700; margin-top:2px;'>{status_label}</div>"
                                        f"</div>",
                                        unsafe_allow_html=True,
                                    )

                                row1_col1, row1_col2, row1_col3 = st.columns(3)
                                with row1_col1:
                                    st.markdown(
                                        f"<div style='color:#888888; font-size:0.75rem; "
                                        f"text-transform:uppercase; letter-spacing:0.5px;'>Body region</div>"
                                        f"<div>{_fmt(rec.get('body_region'))}</div>",
                                        unsafe_allow_html=True,
                                    )
                                with row1_col2:
                                    st.markdown(
                                        f"<div style='color:#888888; font-size:0.75rem; "
                                        f"text-transform:uppercase; letter-spacing:0.5px;'>Pathology</div>"
                                        f"<div>{_fmt(rec.get('pathology'))}</div>",
                                        unsafe_allow_html=True,
                                    )
                                with row1_col3:
                                    st.markdown(
                                        f"<div style='color:#888888; font-size:0.75rem; "
                                        f"text-transform:uppercase; letter-spacing:0.5px;'>Onset type</div>"
                                        f"<div>{_fmt(rec.get('onset_type'))}</div>",
                                        unsafe_allow_html=True,
                                    )

                                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

                                row2_col1, row2_col2, row2_col3 = st.columns(3)
                                with row2_col1:
                                    st.markdown(
                                        f"<div style='color:#888888; font-size:0.75rem; "
                                        f"text-transform:uppercase; letter-spacing:0.5px;'>Side</div>"
                                        f"<div>{_fmt(rec.get('side'))}</div>",
                                        unsafe_allow_html=True,
                                    )
                                with row2_col2:
                                    st.markdown(
                                        f"<div style='color:#888888; font-size:0.75rem; "
                                        f"text-transform:uppercase; letter-spacing:0.5px;'>Date of examination</div>"
                                        f"<div>{_fmt_date(rec.get('date_of_examination'))}</div>",
                                        unsafe_allow_html=True,
                                    )
                                with row2_col3:
                                    st.markdown(
                                        f"<div style='color:#888888; font-size:0.75rem; "
                                        f"text-transform:uppercase; letter-spacing:0.5px;'>Description</div>"
                                        f"<div>{_fmt(rec.get('specific_description'))}</div>",
                                        unsafe_allow_html=True,
                                    )

                                if is_resolved:
                                    days_to_resolve = (
                                        (resolved_parsed - injury_date_parsed).days
                                        if pd.notna(injury_date_parsed)
                                        else None
                                    )
                                    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                                    days_line = (
                                        f"<div style='color:#888888; font-size:0.8rem; margin-top:2px;'>"
                                        f"{days_to_resolve} day(s) to resolve</div>"
                                        if days_to_resolve is not None
                                        else ""
                                    )
                                    st.markdown(
                                        f"<div style='color:#888888; font-size:0.75rem; "
                                        f"text-transform:uppercase; letter-spacing:0.5px;'>Injury resolved date</div>"
                                        f"<div style='font-size:1.05rem; font-weight:700;'>"
                                        f"{_fmt_date(resolved_value)}</div>"
                                        f"{days_line}",
                                        unsafe_allow_html=True,
                                    )

                                st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
                                if st.button(
                                    "Update / Resolve",
                                    key=f"obs_injury_select_{rec.get('id')}",
                                    use_container_width=True,
                                ):
                                    st.session_state.obs_selected_injury_id = rec.get("id")
                                    st.rerun()

            else:
                # ---- Edit page for a single injury: resolved date + availability ----
                if st.button("← Back to injuries list", key="obs_back_to_injuries"):
                    st.session_state.obs_selected_injury_id = None
                    st.rerun()

                injury_id = st.session_state.obs_selected_injury_id
                rec_match = (
                    medical_df[medical_df["id"] == injury_id] if not medical_df.empty else pd.DataFrame()
                )

                if rec_match.empty:
                    st.warning("This injury entry could not be found — it may have been removed.")
                else:
                    rec = rec_match.iloc[0]
                    st.subheader(f"{sel_player} — {_fmt(rec.get('injury_type'))}")
                    st.caption(
                        f"{_fmt(rec.get('body_region'))} · {_fmt(rec.get('pathology'))} · "
                        f"Injured {_fmt_date(rec.get('date_of_injury'))}"
                    )
                    st.write("")

                    existing_resolved = pd.to_datetime(rec.get("injury_resolved_date"), errors="coerce")
                    resolved_date = st.date_input(
                        "Injury Resolved Date",
                        value=existing_resolved.date() if pd.notna(existing_resolved) else None,
                        key=f"obs_resolved_date_{injury_id}",
                    )

                    try:
                        players_df = read_table(PLAYERS_TABLE)
                    except Exception:
                        players_df = pd.DataFrame()
                    team_players = get_team_players(players_df, sel_team)
                    player_match = next((p for p in team_players if p["name"] == sel_player), None)

                    try:
                        current_data = get_current_player_data(sel_team)
                    except Exception:
                        current_data = {}
                    default_status = current_data.get(sel_player, {}).get("status", "Available")
                    status_index = (
                        STATUS_OPTIONS.index(default_status) if default_status in STATUS_OPTIONS else 0
                    )

                    status = st.selectbox(
                        "Player Availability",
                        STATUS_OPTIONS,
                        index=status_index,
                        key=f"obs_status_{injury_id}",
                    )

                    if st.button("Save", type="primary", key=f"obs_save_{injury_id}"):
                        try:
                            update_medical_record(
                                injury_id,
                                {
                                    "injury_resolved_date": (
                                        resolved_date.isoformat() if resolved_date else None
                                    ),
                                },
                            )
                            write_availability(
                                [
                                    {
                                        "team": sel_team,
                                        "player": sel_player,
                                        "position": player_match.get("position") if player_match else None,
                                        "status": status,
                                        "medical_notes": None,
                                        "modification_notes": None,
                                        "recorded_at": datetime.now(timezone.utc).isoformat(),
                                    }
                                ]
                            )
                            read_table.clear()
                            st.session_state.obs_selected_injury_id = None
                            st.success(f"Updated {sel_player}'s injury and set availability to '{status}'.")
                            st.rerun()
                        except Exception as e:
                            st.error(
                                f"Save failed: {e}. If 'injury_resolved_date' doesn't exist "
                                "yet on medical_records, run migrations/007_add_injury_resolved_date.sql."
                            )

        else:
            # ---- SOAP: Subjective, Objective, Assessment, Plan ----
            if "obs_soap_adding" not in st.session_state:
                st.session_state.obs_soap_adding = False

            if not st.session_state.obs_soap_adding:
                if st.button("+ Add New SOAP Entry", type="primary", key=f"soap_add_toggle_{sel_team}_{sel_player}"):
                    st.session_state.obs_soap_adding = True
                    st.rerun()
            else:
                st.caption("Written to Supabase 'treatment_observations'.")

                soap_date = st.date_input("Date", key=f"soap_date_{sel_team}_{sel_player}")
                subjective = st.text_area("Subjective", key=f"soap_subjective_{sel_team}_{sel_player}")
                objective = st.text_area("Objective", key=f"soap_objective_{sel_team}_{sel_player}")
                assessment = st.text_area("Assessment", key=f"soap_assessment_{sel_team}_{sel_player}")
                plan = st.text_area("Plan", key=f"soap_plan_{sel_team}_{sel_player}")

                save_col, cancel_col = st.columns([1, 1])
                with save_col:
                    save_clicked = st.button(
                        "Save SOAP Entry",
                        type="primary",
                        use_container_width=True,
                        key=f"soap_save_{sel_team}_{sel_player}",
                    )
                with cancel_col:
                    if st.button(
                        "Cancel",
                        use_container_width=True,
                        key=f"soap_cancel_{sel_team}_{sel_player}",
                    ):
                        st.session_state.obs_soap_adding = False
                        st.rerun()

                if save_clicked:
                    try:
                        players_df = read_table(PLAYERS_TABLE)
                    except Exception:
                        players_df = pd.DataFrame()
                    team_players = get_team_players(players_df, sel_team)
                    player_match = next((p for p in team_players if p["name"] == sel_player), None)

                    record = {
                        "player_id": player_match.get("id") if player_match else None,
                        "player_name": sel_player,
                        "team": sel_team,
                        "date": soap_date.isoformat(),
                        "subjective": subjective or None,
                        "objective": objective or None,
                        "assessment": assessment or None,
                        "plan": plan or None,
                        "recorded_at": datetime.now(timezone.utc).isoformat(),
                    }
                    try:
                        write_treatment_observation(record)
                        read_table.clear()
                        st.session_state.obs_soap_adding = False
                        st.success(f"SOAP entry saved for {sel_player}.")
                        st.rerun()
                    except Exception as e:
                        st.error(
                            f"Save failed: {e}. If the table doesn't exist yet, run "
                            "schema_treatment_observations.sql."
                        )

            st.divider()
            st.markdown("**Previous entries**")
            try:
                treatment_df = read_table(TREATMENT_TABLE)
            except Exception:
                treatment_df = pd.DataFrame()

            if treatment_df.empty:
                st.caption("No SOAP entries logged yet.")
            else:
                player_soap = treatment_df[treatment_df["player_name"] == sel_player].copy()
                if player_soap.empty:
                    st.caption(f"No SOAP entries logged for {sel_player} yet.")
                else:
                    player_soap["_sort_date"] = pd.to_datetime(player_soap["date"], errors="coerce")
                    player_soap = player_soap.sort_values("_sort_date", ascending=False)
                    for _, entry in player_soap.iterrows():
                        with st.expander(_fmt_date(entry.get("date"))):
                            soap_fields = [
                                ("Subjective", entry.get("subjective")),
                                ("Objective", entry.get("objective")),
                                ("Assessment", entry.get("assessment")),
                                ("Plan", entry.get("plan")),
                            ]
                            soap_cols = st.columns(4)
                            for col, (label, value) in zip(soap_cols, soap_fields):
                                with col:
                                    with st.container(border=True):
                                        st.markdown(
                                            f"<div style='color:#888888; font-size:0.75rem; "
                                            f"text-transform:uppercase; letter-spacing:0.5px; "
                                            f"margin-bottom:4px;'>{label}</div>",
                                            unsafe_allow_html=True,
                                        )
                                        st.markdown(_fmt(value))

else:  # nav_section == "Medical" and nav_page == "Player Availability"
    # Tightens default Streamlit spacing so a full squad's cards fit
    # without scrolling. Targets stable data-testid hooks, but worth
    # re-checking if a future Streamlit version changes card padding.
    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"] { padding: 0.35rem 0.6rem !important; min-height: 330px; }
        div[data-testid="stVerticalBlock"] { gap: 0.25rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    try:
        players_df = read_table(PLAYERS_TABLE)
    except Exception as e:
        players_df = pd.DataFrame()
        st.info(
            f"Could not load the players table yet ({e}). Run "
            "schema_players.sql in Supabase and add your roster there."
        )
    roster_by_team = build_roster_dict(players_df)

    avail_team = st.selectbox("Team", TEAMS, key="avail_team")
    roster = roster_by_team.get(avail_team, {})
    if not roster:
        st.info(f"No players found for {avail_team} in the players table yet.")

    try:
        current_data = get_current_player_data(avail_team)
    except Exception as e:
        current_data = {}
        st.info(
            f"Could not load existing availability yet ({e}). "
            "Defaulting everyone to 'Available' — this is expected the "
            "first time the table is queried before it exists in Supabase."
        )

    # Flatten to one ordered list so cards form a continuous grid, grouped
    # by position but without a full-width header per group (saves rows).
    flat_players = [
        (position, player)
        for position in POSITION_ORDER
        for player in roster.get(position, [])
    ]

    # ---- Player filter ----
    # Players picked here are hidden from the cards below and excluded
    # from the Available/Modified/Unavailable counts, but they still
    # count toward the availability % on the top right (that figure is
    # computed from the full squad, further down). The widget itself is
    # rendered at the very bottom of the page so it doesn't take up space
    # above the cards; we read its persisted session_state value here,
    # before it's drawn, which is the standard Streamlit pattern for a
    # control that needs to affect content placed above it.
    avail_filter_key = f"avail_hidden_players_{avail_team}"
    if avail_filter_key not in st.session_state:
        st.session_state[avail_filter_key] = []
    avail_national_team_key = f"avail_filter_national_team_{avail_team}"
    if avail_national_team_key not in st.session_state:
        st.session_state[avail_national_team_key] = False

    hidden_players = set(st.session_state[avail_filter_key])
    if st.session_state[avail_national_team_key]:
        hidden_players |= set(NATIONAL_TEAM_PLAYERS)

    visible_players = [
        (position, player)
        for position, player in flat_players
        if player["name"] not in hidden_players
    ]

    # ---- Status summary, split Goalkeepers vs Outfielders ----
    # "Available - Recurring Medical Attention" is counted together with
    # "Available" here and shown under the single "Available" label — the
    # summary line only distinguishes Available / Modified / Unavailable.
    # Built from visible_players, so filtered-out players don't add to
    # these counts.
    SUMMARY_STATUS_ORDER = ["Available", "Available - Modified", "Unavailable"]

    gk_counts = {s: 0 for s in SUMMARY_STATUS_ORDER}
    outfield_counts = {s: 0 for s in SUMMARY_STATUS_ORDER}
    for position, player in visible_players:
        status = current_data.get(player["name"], {}).get("status", "Available")
        summary_status = "Available" if status == "Available - Recurring Medical Attention" else status
        bucket = gk_counts if position == "Goalkeepers" else outfield_counts
        bucket[summary_status] += 1

    def _stat_card(status, count):
        """One color-shaded mini stat card (count + label), reusing the
        same background/border tint as the player cards below for that
        status, so the summary visually matches the cards it's counting."""
        colors = STATUS_CARD_COLORS[status]
        label = STATUS_CARD_LABELS.get(status, status)
        return (
            f"<div style='flex:1; min-width:76px; background-color:{colors['bg']}; "
            f"border:1px solid {colors['border']}; border-radius:10px; "
            f"padding:8px 10px; text-align:center;'>"
            f"<div style='font-size:1.5rem; font-weight:700; color:{colors['border']}; "
            f"line-height:1.2;'>{count}</div>"
            f"<div style='font-size:0.7rem; font-weight:600; color:#555555; "
            f"line-height:1.2;'>{label}</div>"
            f"</div>"
        )

    def _stat_row(counts):
        return (
            "<div style='display:flex; gap:8px; margin-bottom:22px;'>"
            + "".join(_stat_card(status, counts[status]) for status in SUMMARY_STATUS_ORDER)
            + "</div>"
        )

    # ---- Overall availability % (Available [+ Recurring Medical Attention, already merged above] + Modified) ----
    # Computed over the FULL squad (flat_players), not visible_players —
    # players hidden by the filter still count toward this figure, only
    # the cards/counts above exclude them.
    total_players = len(flat_players)
    available_total = sum(
        1
        for _, player in flat_players
        if current_data.get(player["name"], {}).get("status", "Available")
        in ("Available", "Available - Recurring Medical Attention", "Available - Modified")
    )
    availability_pct = round(available_total / total_players * 100) if total_players else 0
    today_str = datetime.now().strftime("%d/%m/%y")

    def _pct_badge_color(pct):
        if pct >= 80:
            return STATUS_PILL_COLORS["Available"]
        if pct >= 50:
            return STATUS_PILL_COLORS["Available - Modified"]
        return STATUS_PILL_COLORS["Unavailable"]

    sum_col1, sum_col2, pct_col = st.columns([2, 2, 1], gap="large")
    with sum_col1:
        st.markdown(
            "<div style='font-size:1.05rem; font-weight:600; line-height:1.6; margin-bottom:14px;'>Goalkeepers</div>",
            unsafe_allow_html=True,
        )
        st.markdown(_stat_row(gk_counts), unsafe_allow_html=True)
    with sum_col2:
        st.markdown(
            "<div style='font-size:1.05rem; font-weight:600; line-height:1.6; margin-bottom:14px;'>Outfielders</div>",
            unsafe_allow_html=True,
        )
        st.markdown(_stat_row(outfield_counts), unsafe_allow_html=True)
    with pct_col:
        badge_color = _pct_badge_color(availability_pct)
        st.markdown(
            f"<div style='display:flex; justify-content:flex-end; align-items:center; padding-bottom:14px;'>"
            f"<div style='text-align:right; margin-right:10px; line-height:1.25;'>"
            f"<div style='font-size:1.05rem; color:#555555;'>{today_str}</div>"
            f"<div style='font-size:1.05rem; font-weight:600;'>Availability %</div>"
            f"</div>"
            f"<div style='width:56px; height:56px; border-radius:50%; "
            f"background-color:{badge_color}; color:#ffffff; display:flex; "
            f"align-items:center; justify-content:center; font-weight:700; "
            f"font-size:0.95rem;' title='Available (incl. Recurring Medical Attention) "
            f"+ Available - Modified, as % of all players shown'>{availability_pct}%</div></div>",
            unsafe_allow_html=True,
        )

    # ---- Per-card colour CSS, generated once up front and injected together ----
    card_css_rules = []
    for position, player in visible_players:
        name = player["name"]
        status = current_data.get(name, {}).get("status", "Available")
        colors = STATUS_CARD_COLORS[status]
        key_slug = slugify(f"card_{avail_team}_{name}")
        card_css_rules.append(
            f'.st-key-{key_slug} {{ '
            f'background-color: {colors["bg"]} !important; '
            f'border: 1px solid {colors["border"]} !important; '
            f'position: relative; '
            f'}}'
        )
    st.markdown(f"<style>{''.join(card_css_rules)}</style>", unsafe_allow_html=True)

    def _notes_block(label, text, margin_bottom=6):
        """Medical/modification notes line, CSS-clamped to exactly two
        lines (with an ellipsis if longer) so every card reserves the
        same amount of space here regardless of how much text is in it —
        short notes leave blank space instead of collapsing to one line,
        long notes get truncated at two lines instead of stretching the
        card taller than its neighbours. line-height is kept tight (the
        spacing wanted is *between* the two note blocks, via
        margin_bottom, not between the wrapped lines within one)."""
        shown = text if text else f"No {label.lower()} notes"
        escaped = html.escape(shown)
        return (
            f"<div style='font-size:0.85rem; color:#808495; line-height:1.1em; "
            f"min-height:2.2em; margin-bottom:{margin_bottom}px; display:-webkit-box; "
            f"-webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;'>"
            f"<b>{label}:</b> {escaped}</div>"
        )

    @st.fragment
    def _render_availability_card(slot, position, player):
        """One player's card, as its own fragment so opening/closing the
        edit form (or cancelling out of it) only reruns this single card
        instead of the whole page — the counts/percentage above and every
        other card stay untouched and don't get visibly redrawn.

        Rendered into an st.empty() slot (rather than writing straight
        into the outer column) because that slot is what Streamlit clears
        and replaces on each fragment rerun; a plain column/container
        created outside the fragment would otherwise accumulate elements
        instead of replacing them.

        Saving does trigger a normal full-page rerun (st.rerun() with its
        default scope="app"), since a save is the one case where the
        counts/percentage above genuinely need to reflect the change.
        """
        name = player["name"]
        age = player["age"]
        age_display = round(age) if isinstance(age, (int, float)) else age
        saved = current_data.get(name, {})
        saved_status = saved.get("status", "Available")
        saved_notes = saved.get("medical_notes", "")
        saved_mod_notes = saved.get("modification_notes", "")

        edit_key = f"editing_{avail_team}_{name}"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = False

        card_key = slugify(f"card_{avail_team}_{name}")

        with slot.container(border=True, key=card_key):
            st.markdown(render_avatar_html(player, POSITION_COLORS[position]), unsafe_allow_html=True)
            pos_color = POSITION_COLORS[position]
            st.markdown(
                f"<div style='padding-right:64px; margin-bottom:6px;'><b>{name}</b></div>",
                unsafe_allow_html=True,
            )
            st.caption(f"Age {age_display}")

            if not st.session_state[edit_key]:
                # ---- View-only mode ----
                pill_color = STATUS_PILL_COLORS[saved_status]
                pill_label = STATUS_CARD_LABELS.get(saved_status, saved_status)
                st.markdown(
                    f"<div style='display:flex; align-items:center; gap:6px; margin-bottom:22px;'>"
                    f"<div style='width:22px; height:22px; border-radius:50%; "
                    f"background-color:{pos_color}; color:#ffffff; display:flex; "
                    f"align-items:center; justify-content:center; font-size:0.65rem; "
                    f"font-weight:700; flex-shrink:0;'>{POSITION_ABBR[position]}</div>"
                    f"<span style='background-color:{pill_color}; color:#ffffff; "
                    f"padding:2px 10px; border-radius:10px; font-size:0.75rem; "
                    f"font-weight:600; display:inline-block;'>{pill_label}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(_notes_block("Medical", saved_notes, margin_bottom=14), unsafe_allow_html=True)
                st.markdown(_notes_block("Mods", saved_mod_notes, margin_bottom=18), unsafe_allow_html=True)
                modify_col, history_col = st.columns([2, 1])
                with modify_col:
                    if st.button("✎", key=f"modify_{avail_team}_{name}", use_container_width=True, help="Modify"):
                        st.session_state[edit_key] = True
                        st.rerun(scope="fragment")
                with history_col:
                    with st.popover("⏱", use_container_width=True, help="Recent session history"):
                        st.caption("Last 5 sessions")
                        history = get_recent_session_history(avail_team, name)
                        if isinstance(history, str):
                            st.caption(history)
                        else:
                            for line in history:
                                st.markdown(f"- {line}")
            else:
                # ---- Edit mode ----
                new_status = st.pills(
                    label=name,
                    options=STATUS_OPTIONS,
                    format_func=lambda s: STATUS_DISPLAY[s],
                    selection_mode="single",
                    default=saved_status,
                    key=f"pill_{avail_team}_{name}",
                    label_visibility="collapsed",
                )
                new_notes = st.text_area(
                    "Medical notes",
                    value=saved_notes,
                    key=f"notes_{avail_team}_{name}",
                    height=70,
                    label_visibility="collapsed",
                    placeholder="Medical notes...",
                )
                new_mod_notes = st.text_area(
                    "Modification notes",
                    value=saved_mod_notes,
                    key=f"mod_notes_{avail_team}_{name}",
                    height=70,
                    label_visibility="collapsed",
                    placeholder="Modification notes...",
                )
                save_col, cancel_col = st.columns(2)
                with save_col:
                    if st.button("Save", key=f"save_{avail_team}_{name}", type="primary", use_container_width=True):
                        record = {
                            "team": avail_team,
                            "player": name,
                            "position": position,
                            "status": new_status or saved_status,
                            "medical_notes": new_notes,
                            "modification_notes": new_mod_notes,
                            "recorded_at": datetime.now(timezone.utc).isoformat(),
                        }
                        try:
                            write_availability([record])
                            get_current_player_data.clear()
                            st.session_state[edit_key] = False
                            st.rerun()
                        except Exception as e:
                            st.error(
                                f"Save failed: {e}. If the table doesn't "
                                "exist yet, run schema_availability.sql "
                                "(and migrations/001_add_medical_notes.sql, "
                                "migrations/002_add_modification_notes.sql "
                                "if it was created before notes support)."
                            )
                with cancel_col:
                    if st.button("Cancel", key=f"cancel_{avail_team}_{name}", use_container_width=True):
                        st.session_state[edit_key] = False
                        st.rerun(scope="fragment")

    columns = st.columns(CARD_GRID_COLUMNS)

    for i, (position, player) in enumerate(visible_players):
        slot = columns[i % CARD_GRID_COLUMNS].empty()
        _render_availability_card(slot, position, player)

    # ---- Player filter control ----
    # Placed at the very bottom of the page, below every card, so it
    # doesn't push the roster down or block the view. Uses the same
    # avail_filter_key read further up, before this widget is drawn, to
    # hide the selected players from the cards and top counts (the
    # availability % is unaffected — see its calculation above).
    if flat_players:
        st.divider()
        st.multiselect(
            "Filter out players",
            options=[player["name"] for _, player in flat_players],
            key=avail_filter_key,
            help=(
                "Selected players are hidden from the cards and from the "
                "Available / Available - Modified / Unavailable counts "
                "above, but still count toward the availability % in the "
                "top right."
            ),
        )
        st.checkbox(
            "National Team",
            key=avail_national_team_key,
            help=(
                "Filters out a fixed group of players straightaway "
                "(edit the NATIONAL_TEAM_PLAYERS list in the source code "
                "to change who's included). Combines with the filter above."
            ),
        )