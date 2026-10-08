"""
Shared variable schema for the Movement Screening Dashboard.

Both utils/screening_dashboard.py (the Performance > Medical Screening page
of app.py) and parse_pdfs.py (the PDF -> CSV parser) import from this module, so the list of known variables, their
scales/ranges, and column-naming rules only ever live in one place.
"""

# ----------------------------------------------------------------------
# ANSWER SCALES
# ----------------------------------------------------------------------
# Answer scales used by single-choice variables. Order matters -- it is
# the order pills are drawn in. Colors are deliberately NOT a simple
# green-to-red ramp for the mobility scale, since "Hypermobile" is a
# different kind of abnormal to "Stiff", not merely a milder version.
SCALES = {
    "mobility5": {
        "options": ["Hypermobile", "Mobile", "Ok", "Stiff", "Highly Restricted"],
        "colors": {
            "Hypermobile": "#3B82F6",       # blue -- excess mobility, different axis
            "Mobile": "#34D399",            # light green
            "Ok": "#22C55E",                # green
            "Stiff": "#F59E0B",             # amber
            "Highly Restricted": "#EF4444", # red
        },
        "flagged": {"Stiff", "Highly Restricted"},
    },
    "goodbad4": {
        "options": ["=- (Good)", "+ (Sub-optimal)", "++ (Bad)", "+++ (Very Bad)"],
        "colors": {
            "=- (Good)": "#22C55E",
            "+ (Sub-optimal)": "#EAB308",
            "++ (Bad)": "#F97316",
            "+++ (Very Bad)": "#EF4444",
        },
        "flagged": {"++ (Bad)", "+++ (Very Bad)"},
    },
    "hernia2": {
        "options": ["Yes (Negative)", "No Indication (Positive)"],
        "colors": {
            "Yes (Negative)": "#22C55E",
            "No Indication (Positive)": "#EF4444",
        },
        "flagged": {"No Indication (Positive)"},
    },
}

SCALES["gameload6"] = {
    "options": [
        ">80% of GL of previous team",
        "70-80% of GL of previous team",
        "60-70% of GL of previous team",
        "50-60% of GL of previous team",
        "40-50% of GL of previous team",
        "<40% of GL of previous team",
    ],
    "colors": {
        ">80% of GL of previous team": "#22C55E",
        "70-80% of GL of previous team": "#84CC16",
        "60-70% of GL of previous team": "#EAB308",
        "50-60% of GL of previous team": "#F59E0B",
        "40-50% of GL of previous team": "#F97316",
        "<40% of GL of previous team": "#EF4444",
    },
    "flagged": {"50-60% of GL of previous team", "40-50% of GL of previous team", "<40% of GL of previous team"},
}

SCALES["recentinjury6"] = {
    "options": [
        "No injury reported (neither time-loss/medical attention)",
        "Medical attention only - without missing games",
        "Mild time-loss injuries - less than 15 days per season",
        "Moderate time-loss injuries - 15 to 28 days per season",
        "Severe time-loss (28-90 days)",
        "Re-injury or long-term injuries (ACL, fractures, surgical cases etc.)",
    ],
    "colors": {
        "No injury reported (neither time-loss/medical attention)": "#22C55E",
        "Medical attention only - without missing games": "#84CC16",
        "Mild time-loss injuries - less than 15 days per season": "#EAB308",
        "Moderate time-loss injuries - 15 to 28 days per season": "#F59E0B",
        "Severe time-loss (28-90 days)": "#F97316",
        "Re-injury or long-term injuries (ACL, fractures, surgical cases etc.)": "#EF4444",
    },
    "flagged": {
        "Moderate time-loss injuries - 15 to 28 days per season",
        "Severe time-loss (28-90 days)",
        "Re-injury or long-term injuries (ACL, fractures, surgical cases etc.)",
    },
}

SCALES["pastinjury6"] = {
    "options": [
        "No significant injury history",
        "Single injury history in different tissues",
        "Recurrent injury (same tissue) different seasons <3x in career",
        "Multiple injuries per season (>3), different tissues",
        ">3 same-tissue injuries OR previous major injury (>6 months)",
        "Chronic/recurring injury throughout athlete's career",
    ],
    "colors": {
        "No significant injury history": "#22C55E",
        "Single injury history in different tissues": "#84CC16",
        "Recurrent injury (same tissue) different seasons <3x in career": "#EAB308",
        "Multiple injuries per season (>3), different tissues": "#F59E0B",
        ">3 same-tissue injuries OR previous major injury (>6 months)": "#F97316",
        "Chronic/recurring injury throughout athlete's career": "#EF4444",
    },
    "flagged": {
        "Multiple injuries per season (>3), different tissues",
        ">3 same-tissue injuries OR previous major injury (>6 months)",
        "Chronic/recurring injury throughout athlete's career",
    },
}

# ----------------------------------------------------------------------
# REGIONS
# ----------------------------------------------------------------------
# Region accent colors -- used as a left-border on cards in the dashboard
# so each body region is visually recognizable at a glance.
REGION_COLORS = {
    "Athlete Profile": "#DB2777",  # rose -- context/load data, distinct from body regions
    "Ankle/Foot": "#06B6D4",   # cyan
    "Knee": "#6366F1",         # indigo
    "Hip/Groin": "#8B5CF6",    # violet
    "Mobility": "#D97706",     # amber
    "Goalkeeper Specific": "#059669",  # emerald -- position-specific, distinct from body regions
    "Skinfold Analysis": "#64748B",    # slate -- supplementary body-comp data, often blank
    "Gym Performance Testing": "#2563EB",  # blue -- strength/force testing, distinct from body regions
}

# Single-choice tests, grouped by region: (test name, scale key, sided).
# "sided" = True means the test has separate Left/Right columns;
# False means it's a single, whole-athlete value.
SINGLE_CHOICE_TESTS = {
    "Athlete Profile": [
        ("Game Load Previous Season", "gameload6", False),
        ("Recent Injury History", "recentinjury6", False),
        ("Past Injury History", "pastinjury6", False),
    ],
    "Ankle/Foot": [
        ("General Impression", "mobility5", True),
        ("Anterior Drawer Test", "goodbad4", True),
        ("Inversion Stress Test", "goodbad4", True),
        ("Achilles Palpation", "goodbad4", True),
        ("First Toe Extension", "goodbad4", True),
    ],
    "Knee": [
        ("Anterior Drawer Test", "goodbad4", True),
        ("Posterior Drawer Test", "goodbad4", True),
        ("Valgus Stress", "goodbad4", True),
        ("Varus Stress", "goodbad4", True),
        ("McMurray Test", "goodbad4", True),
    ],
    "Hip/Groin": [
        ("Impingement Test FADIR", "goodbad4", True),
        ("Adductor Insertion Palpation", "goodbad4", True),
        ("Pubic Palpation", "goodbad4", True),
        ("Inguinal Ring Palpation", "goodbad4", True),
        ("Inguinal Hernia Testing", "hernia2", True),
    ],
    "Goalkeeper Specific": [
        # Blank for outfield players -- only goalkeepers get this tested.
        ("Shoulder Apprehension Test", "goodbad4", False),
    ],
}

# Number tests: (test name, min, max, unit, sided).
# NOTE: ranges are reasonable estimates for a movement/athlete screen,
# not diagnostic thresholds. Adjust to your protocol's norms if you have
# them -- edit the tuple values below.
NUMBER_TESTS = {
    "Athlete Profile": [
        # Height/Weight/Bodyfat are handled separately below as plain
        # text (ANTHRO_FIELDS) rather than as gauge cards.
    ],
    "Mobility": [
        ("Hip - IR", 0, 50, "\u00b0", True),
        ("Hip - ER", 0, 60, "\u00b0", True),
        ("Hip - TROM", 0, 100, "\u00b0", True),
        ("Hip - BKFO", 0, 40, "cm", True),
        ("Anterior Chain - Falcon Test", 0, 90, "\u00b0", True),
        ("Hamstring - Jurdan Test", 0, 100, "\u00b0", True),
        ("Ankle - Knee to Wall", 0, 20, "cm", True),
        # Goalkeeper-specific shoulder ROM -- blank for outfield players.
        ("Shoulder - Flexion", 0, 180, "\u00b0", False),
        ("Shoulder - Extension", 0, 60, "\u00b0", False),
        ("Shoulder - Abduction", 0, 180, "\u00b0", False),
        ("Shoulder - Internal", 0, 90, "\u00b0", False),
        ("Shoulder - External", 0, 90, "\u00b0", False),
    ],
    "Gym Performance Testing": [
        # Force values in Newtons. Ranges are best-estimate ceilings for
        # elite-level output, not diagnostic thresholds -- adjust if your
        # testing protocol/population has established norms.
        ("Nordic ISO30 Peak Force", 0, 700, "N", True),
        ("Knee Extension Standing Peak Force", 0, 900, "N", True),
        ("Hip Abduction 60", 0, 300, "N", True),
        ("Hip Adduction 60", 0, 300, "N", True),
        ("Ankle Plantar Flexion Seated", 0, 700, "N", True),
        ("IMTP", 0, 4500, "N", False),
    ],
}

# Flag thresholds for the Mobility tab's number tests. These are
# best-estimate cutoffs drawn from commonly-cited ranges in general
# sports-science/physio literature for restricted mobility -- NOT
# validated diagnostic thresholds for any specific population, sport,
# or protocol, and several of these are team-specific test names
# (Falcon Test, Jurdan Test, BKFO) with no single published norm to
# point to. Treat these as a reasonable starting point and replace with
# your own normative data if/when you have it.
# Each entry: {"direction": "below"/"above", "value": cutoff, "note": display text}
MOBILITY_THRESHOLDS = {
    "Hip - IR": {
        "direction": "below", "value": 20,
        "note": "Flag if < 20\u00b0 (restricted internal rotation)",
    },
    "Hip - ER": {
        "direction": "below", "value": 30,
        "note": "Flag if < 30\u00b0 (restricted external rotation)",
    },
    "Hip - TROM": {
        "direction": "below", "value": 35,
        "note": "Flag if < 35\u00b0 (low total hip rotation is linked to higher hip/groin injury risk in some studies)",
    },
    "Hip - BKFO": {
        "direction": "below", "value": 15,
        "note": "Flag if < 15cm (restricted)",
    },
    "Anterior Chain - Falcon Test": {
        "direction": "below", "value": 20,
        "note": "Flag if < 20\u00b0 (restricted hip flexor/quad length)",
    },
    "Hamstring - Jurdan Test": {
        "direction": "below", "value": 20,
        "note": "Flag if < 20\u00b0 (restricted hamstring length)",
    },
    "Ankle - Knee to Wall": {
        "direction": "below", "value": 9,
        "note": "Flag if < 9cm (a commonly-cited cutoff for reduced ankle dorsiflexion ROM)",
    },
    "Shoulder - Flexion": {
        "direction": "below", "value": 150,
        "note": "Flag if < 150\u00b0 (restricted)",
    },
    "Shoulder - Extension": {
        "direction": "below", "value": 40,
        "note": "Flag if < 40\u00b0 (restricted)",
    },
    "Shoulder - Abduction": {
        "direction": "below", "value": 150,
        "note": "Flag if < 150\u00b0 (restricted)",
    },
    "Shoulder - Internal": {
        "direction": "below", "value": 50,
        "note": "Flag if < 50\u00b0 (restricted; also check for GIRD vs. the other shoulder)",
    },
    "Shoulder - External": {
        "direction": "below", "value": 70,
        "note": "Flag if < 70\u00b0 (restricted)",
    },
}

# Simple text-only fields, shown together in one row (no gauge/scale).
# Each entry: (region, field name, unit, decimal places).
ANTHRO_FIELDS = [
    ("Athlete Profile", "Height (cm)", "cm", 0),
    ("Athlete Profile", "Weight (kg)", "kg", 1),
    ("Athlete Profile", "Bodyfat Percentage (%)", "%", 1),
]

# Skinfold measurements -- also plain text (no inherent "good/bad"
# direction without an established per-athlete baseline), shown together
# in their own row. Each entry: (region, field name, unit, decimal places).
SKINFOLD_FIELDS = [
    ("Skinfold Analysis", "Triceps Skinfold", "mm", 1),
    ("Skinfold Analysis", "Biceps Skinfold", "mm", 1),
    ("Skinfold Analysis", "Subscapular Skinfold", "mm", 1),
    ("Skinfold Analysis", "Iliac Crest", "mm", 1),
    ("Skinfold Analysis", "Supraspinale Skinfold", "mm", 1),
    ("Skinfold Analysis", "Abdominal Skinfold", "mm", 1),
    ("Skinfold Analysis", "Thigh Skinfold", "mm", 1),
    ("Skinfold Analysis", "Calf Skinfold", "mm", 1),
]

REGIONS = [
    "Athlete Profile",
    "Ankle/Foot",
    "Knee",
    "Hip/Groin",
    "Mobility",
    "Goalkeeper Specific",
    "Skinfold Analysis",
    "Gym Performance Testing",
]


# Regions whose CSV columns are NOT prefixed with "Region - " -- e.g.
# because they're entered manually using their own plain names, like
# "Nordic ISO30 Peak Force (Left)" rather than
# "Gym Performance Testing - Nordic ISO30 Peak Force (Left)".
UNPREFIXED_REGIONS = {"Gym Performance Testing"}


def col_name(region: str, test: str, side: str = None) -> str:
    prefix = "" if region in UNPREFIXED_REGIONS else f"{region} - "
    if side is None:
        return f"{prefix}{test}"
    return f"{prefix}{test} ({side})"


def all_expected_columns():
    cols = ["Name", "Date"]
    for region, tests in SINGLE_CHOICE_TESTS.items():
        for test, _scale, sided in tests:
            if sided:
                cols.append(col_name(region, test, "Left"))
                cols.append(col_name(region, test, "Right"))
            else:
                cols.append(col_name(region, test))
    for region, tests in NUMBER_TESTS.items():
        for test, _mn, _mx, _unit, sided in tests:
            if sided:
                cols.append(col_name(region, test, "Left"))
                cols.append(col_name(region, test, "Right"))
            else:
                cols.append(col_name(region, test))
    for region, test, _unit, _dp in ANTHRO_FIELDS:
        cols.append(col_name(region, test))
    for region, test, _unit, _dp in SKINFOLD_FIELDS:
        cols.append(col_name(region, test))
    return cols


def count_single_choice_fields() -> int:
    total = 0
    for tests in SINGLE_CHOICE_TESTS.values():
        for _test, _scale, sided in tests:
            total += 2 if sided else 1
    return total
