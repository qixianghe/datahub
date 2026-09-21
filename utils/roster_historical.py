"""
Static player roster for development/demo purposes.

Team assignments, positions, and ages here are placeholders (none of this
was in the source name list, so it was filled in for a realistic demo).
Replace this with a real `players` table in Supabase once actual roster
data is available, and load it with a query instead of importing this
dict — the Availability tab in app.py only relies on the shape of
ROSTER (dict of dicts of {"name", "age"} entries), not on where it
comes from.
"""

ROSTER = {
    "First Team": {
        "Goalkeepers": [
            {"name": "Ivan Susak", "age": 27, "photo_path":"IVAN SUSAK.jpg"},
            {"name": "Adib Azahari", "age": 28, "photo_path":"ADIB AZAHARI.jpg"},
            {"name": "Victor Aznar", "age": 23, "photo_path":"VICTOR AZNAR.jpg"}
        ],
        "Defenders": [
            {"name": "Bailey Wright", "age": 33},
            {"name": "Hugo Gomes", "age": 32, "photo_path":"HUGO GOMES.jpg"},
            {"name": "Toni Datkovic", "age": 31},
            {"name": "Lionel Tan", "age": 26, "photo_url":"https://www.lioncitysailorsfc.sg/wp-content/uploads/2021/02/mainpic_lionel-1.png"},
            {"name": "Diogo Costa", "age": 26},
            {"name": "Nur Adam", "age": 26},
            {"name": "Jorge Karseladze", "age": 26, "photo_url":"https://cdn-img.staticzz.com/img/planteis/new/43/39/8724339_jorge_karseladze_20240521194408.jpg"},
            {"name": "Ryhan Stewart", "age": 26},
        ],
        "Midfielders": [
            {"name": "Hami Syahin", "age": 25},
            {"name": "Kyoga Nakamura", "age": 28},
            {"name": "Tsiy Ndenge", "age": 22},
            {"name": "Song Ui-young", "age": 30},
            {"name": "Giovanni Haag", "age": 26},
            {"name": "Asis Ijilrali", "age": 26},
            {"name": "Bart Ramselaar", "age": 26},
        ],
        "Forwards": [
            {"name": "Lennart Thy", "age": 24},
            {"name": "Shawal Anuar", "age": 27},
            {"name": "Antonio Mance", "age": 21},
            {"name": "Abdul Rasaq", "age": 26},
        ],
    },
    "SPL2": {
        "Goalkeepers": [
            {"name": "Noah Bennett", "age": 20},
        ],
        "Defenders": [
            {"name": "Samuel Turner", "age": 19},
            {"name": "Alexander Reed", "age": 21},
        ],
        "Midfielders": [
            {"name": "Jacob Murphy", "age": 20},
        ],
        "Forwards": [
            {"name": "Andrew Clarke", "age": 22},
        ],
    },
    "U19": {
        "Goalkeepers": [],
        "Defenders": [],
        "Midfielders": [
            {"name": "Adam Richardson", "age": 18},
            {"name": "Thomas Ward", "age": 17},
        ],
        "Forwards": [
            {"name": "Christopher Evans", "age": 18},
        ],
    },
}

# Fixed display order for grouping cards without dedicated section headers.
POSITION_ORDER = ["Goalkeepers", "Defenders", "Midfielders", "Forwards"]
