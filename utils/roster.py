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
            {"name": "Victor Aznar", "age": 23, "photo_path":"VICTOR AZNAR.png"}
        ],
        "Defenders": [
            {"name": "Bailey Wright", "age": 33, "photo_path":"BAILEY WRIGHT.jpg"},
            {"name": "Hugo Gomes", "age": 32, "photo_path":"HUGO GOMES.jpg"},
            {"name": "Toni Datkovic", "age": 31, r"photo_path":"TONI DATKOVIC.jpg"},
            {"name": "Lionel Tan", "age": 26, "photo_path":"LIONEL TAN.jpg"},
            {"name": "Hariss Harun", "age": 26, "photo_path":"HARISS HARUN.jpg"},
            {"name": "Diogo Costa", "age": 26, "photo_path":"DIOGO COSTA.jpg"},
            {"name": "Nur Adam", "age": 26, "photo_path":"NUR ADAM ABDULLAH.jpg"},
            {"name": "Jorge Karseladze", "age": 26, "photo_path":"JORGE KARSELADZE.jpg"},
            {"name": "Ryhan Stewart", "age": 26, "photo_path":"RYHAN STEWART.jpg"},
        ],
        "Midfielders": [
            {"name": "Hami Syahin", "age": 25, "photo_path":"HAMI SYAHIN.jpg"},
            {"name": "Kyoga Nakamura", "age": 28, "photo_path":"KYOGA NAKAMURA.jpg"},
            {"name": "Tsiy Ndenge", "age": 22, "photo_path":"TSIY NDENGE.jpg"},
            {"name": "Song Ui-young", "age": 30, "photo_path":"SONG UIYOUNG.jpg"},
            {"name": "Giovanni Haag", "age": 26, "photo_path":"GIOVANNI HAAG.jpg"},
            {"name": "Asis Ijilrali", "age": 26, "photo_path":"ASIS IJILRALI.jpg"},
            {"name": "Bart Ramselaar", "age": 26, "photo_path":"BART RAMSELAAR.jpg"},
            {"name": "Glenn Kweh", "age": 26, "photo_path":"GLENN KWEH.jpg"},
            {"name": "Bobby Adekanye", "age": 26, "photo_path":"BOBBY ADEKANYE.jpg"},
            {"name": "Farhan Zulkifli", "age": 26, "photo_path":"FARHAN ZULKIFLI.jpg"},
        ],
        "Forwards": [
            {"name": "Lennart Thy", "age": 24, "photo_path":"LENNART THY.jpg"},
            {"name": "Shawal Anuar", "age": 27, "photo_path":"SHAWAL ANUAR.jpg"},
            {"name": "Antonio Mance", "age": 21, "photo_path":"ANTONIO MANCE.jpg"},
            {"name": "Abdul Rasaq", "age": 26, "photo_path":"ABDUL RASAQ.jpg"},
            {"name": "Ilhan Fandi", "age": 26, "photo_path":"ILHAN FANDI.jpg"},
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
