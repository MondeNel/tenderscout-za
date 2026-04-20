"""
scripts/geocode_tenders.py
---------------------------
One-time script — backfills lat/lng on existing Tender rows using the
town data from saLocations.js (mirrored as a Python dict here).

Run:
    python scripts/geocode_tenders.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
import models

# Mirror of SA_LOCATIONS from saLocations.js — town name → (lat, lng)
TOWN_COORDS = {
    # Gauteng
    "Johannesburg": (-26.2041, 28.0473), "Pretoria": (-25.7479, 28.2293),
    "Centurion": (-25.8600, 28.1889), "Midrand": (-25.9978, 28.1284),
    "Sandton": (-26.1074, 28.0572), "Soweto": (-26.2677, 27.8585),
    "Ekurhuleni": (-26.3592, 28.1519), "Germiston": (-26.2164, 28.1669),
    "Benoni": (-26.1855, 28.3201), "Boksburg": (-26.2143, 28.2617),
    "Vereeniging": (-26.6734, 27.9258), "Vanderbijlpark": (-26.7019, 27.8359),
    # Western Cape
    "Cape Town": (-33.9249, 18.4241), "Stellenbosch": (-33.9321, 18.8602),
    "Paarl": (-33.7302, 18.9629), "Worcester": (-33.6457, 19.4479),
    "George": (-33.9631, 22.4617), "Knysna": (-34.0363, 23.0473),
    "Mossel Bay": (-34.1831, 22.1438), "Swellendam": (-34.0218, 20.4421),
    # KwaZulu-Natal
    "Durban": (-29.8587, 31.0218), "Pietermaritzburg": (-29.6006, 30.3794),
    "Richards Bay": (-28.7832, 32.0516), "Newcastle": (-27.7595, 29.9318),
    "Ladysmith": (-28.5588, 29.7814), "Ulundi": (-28.3256, 31.4157),
    # Eastern Cape
    "Gqeberha": (-33.9608, 25.6022), "East London": (-33.0153, 27.9116),
    "Mthatha": (-31.5885, 28.7844), "Queenstown": (-31.8972, 26.8748),
    "Graaff-Reinet": (-32.2527, 24.5392), "Aliwal North": (-30.6919, 26.7098),
    # Free State
    "Bloemfontein": (-29.1210, 26.2140), "Welkom": (-27.9777, 26.7363),
    "Kroonstad": (-27.6514, 27.2302), "Sasolburg": (-26.8098, 27.8283),
    # Limpopo
    "Polokwane": (-23.9045, 29.4689), "Tzaneen": (-23.8330, 30.1621),
    "Lephalale": (-23.6762, 27.7011), "Modimolle": (-24.6974, 28.4061),
    "Thohoyandou": (-22.9564, 30.4797),
    # Mpumalanga
    "Nelspruit": (-25.4753, 30.9694), "Witbank": (-25.8747, 29.2306),
    "Middelburg": (-25.7748, 29.4626), "Secunda": (-26.5180, 29.1738),
    "Ermelo": (-26.5238, 29.9864),
    # North West
    "Mahikeng": (-25.8565, 25.6442), "Rustenburg": (-25.6671, 27.2424),
    "Klerksdorp": (-26.8679, 26.6662), "Potchefstroom": (-26.7145, 27.1032),
    "Brits": (-25.6333, 27.7833),
    # Northern Cape
    "Kimberley": (-28.7323, 24.7620), "Barkly West": (-28.5378, 24.5166),
    "Warrenton": (-28.1081, 24.8505), "Hartswater": (-27.7486, 24.8196),
    "Upington": (-28.4478, 21.2561), "Kakamas": (-28.7753, 20.6164),
    "Groblershoop": (-28.8842, 21.9738), "Postmasburg": (-28.3542, 23.0756),
    "Springbok": (-29.6641, 17.8865), "Port Nolloth": (-29.2501, 16.8652),
    "Garies": (-30.5667, 17.9833), "Calvinia": (-31.4745, 19.7762),
    "Sutherland": (-32.3967, 20.6627), "Pofadder": (-29.1310, 19.3954),
    "De Aar": (-30.6494, 24.0112), "Colesberg": (-30.7196, 25.0953),
    "Victoria West": (-31.4136, 23.1295), "Carnarvon": (-30.9652, 22.1308),
    "Petrusville": (-30.0901, 24.6617), "Hopetown": (-29.6231, 24.0726),
    "Prieska": (-29.6667, 22.7500), "Douglas": (-29.0582, 23.7676),
    "Kuruman": (-27.4562, 23.4322), "Kathu": (-27.6942, 23.0455),
    "Hotazel": (-27.2317, 22.9605),
}


def geocode():
    db = SessionLocal()
    tenders = db.query(models.Tender).filter(
        models.Tender.lat == None,
        models.Tender.town != None,
    ).all()

    updated = 0
    for t in tenders:
        coords = TOWN_COORDS.get(t.town)
        if coords:
            t.lat, t.lng = coords
            updated += 1

    db.commit()
    db.close()
    print(f"Geocoded {updated} tenders out of {len(tenders)} without coordinates.")


if __name__ == "__main__":
    geocode()