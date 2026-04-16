"""
backfill_provinces.py
---------------------
One-time script. Run once after deploying the scraper fixes to repair
existing tenders in the DB that have province = NULL or wrong province.

Strategy:
  1. For tenders whose source_site matches a known portal domain, we assign
     the province from that portal's known province.
  2. For the rest, we re-run detect_province() against title + description.

Run:
    python backfill_provinces.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
import models
from scraper.utils import detect_province, detect_municipality, detect_town

# Map source_site domain → province (ground truth from portal config)
DOMAIN_PROVINCE_MAP = {
    # Gauteng
    "joburg.org.za":          "Gauteng",
    "tshwane.gov.za":         "Gauteng",
    "ekurhuleni.gov.za":      "Gauteng",
    # Western Cape
    "capetown.gov.za":        "Western Cape",
    # KwaZulu-Natal
    "durban.gov.za":          "KwaZulu-Natal",
    # Eastern Cape
    "buffalocity.gov.za":     "Eastern Cape",
    "nelsonmandelabay.gov.za":"Eastern Cape",
    # Free State
    "mangaung.co.za":         "Free State",
    # Northern Cape
    "ncgov.co.za":            "Northern Cape",
    "northern-cape.gov.za":   "Northern Cape",
    "solplaatje.org.za":      "Northern Cape",
    "dikgatlong.gov.za":      "Northern Cape",
    "magareng.gov.za":        "Northern Cape",
    "phokwane.gov.za":        "Northern Cape",
    "francesbaarddc.gov.za":  "Northern Cape",
    "dawidkruiper.gov.za":    "Northern Cape",
    "kaigariblm.gov.za":      "Northern Cape",
    "kharahais.gov.za":       "Northern Cape",
    "kheis.gov.za":           "Northern Cape",
    "tsantsabane.gov.za":     "Northern Cape",
    "zfmgcawudc.gov.za":      "Northern Cape",
    "richtersveld.gov.za":    "Northern Cape",
    "namakhoi.gov.za":        "Northern Cape",
    "kamiesberg.gov.za":      "Northern Cape",
    "hantam.gov.za":          "Northern Cape",
    "karoohoogland.gov.za":   "Northern Cape",
    "khai-ma.gov.za":         "Northern Cape",
    "namakwadc.gov.za":       "Northern Cape",
    "siyathemba.gov.za":      "Northern Cape",
    "ubuntu.gov.za":          "Northern Cape",
    "umsobomvu.gov.za":       "Northern Cape",
    "emthanjeni.gov.za":      "Northern Cape",
    "kareeberg.gov.za":       "Northern Cape",
    "renosterberg.gov.za":    "Northern Cape",
    "thembelihle.gov.za":     "Northern Cape",
    "siyancuma.gov.za":       "Northern Cape",
    "pixleydc.gov.za":        "Northern Cape",
    "joemorolog.gov.za":      "Northern Cape",
    "gamagara.gov.za":        "Northern Cape",
    "gasegonyana.gov.za":     "Northern Cape",
    "johntaologaetsewedc.gov.za": "Northern Cape",
}


def backfill():
    db = SessionLocal()
    tenders = db.query(models.Tender).all()
    updated = 0

    for t in tenders:
        new_province = None

        # 1. Try domain lookup (most reliable)
        if t.source_site:
            site = t.source_site.lower().replace("www.", "")
            for domain, prov in DOMAIN_PROVINCE_MAP.items():
                if site.endswith(domain):
                    new_province = prov
                    break

        # 2. Fall back to text detection
        if not new_province:
            text = f"{t.title or ''} {t.description or ''} {t.issuing_body or ''}"
            new_province = detect_province(text)

        if new_province and new_province != t.province:
            t.province = new_province
            # Also repair municipality/town within the correct province
            text = f"{t.title or ''} {t.description or ''} {t.issuing_body or ''}"
            t.municipality = detect_municipality(text, new_province)
            if not t.town:
                t.town = detect_town(text, new_province)
            updated += 1

    db.commit()
    db.close()
    print(f"Backfill complete — {updated} tenders updated out of {len(tenders)} total")


if __name__ == "__main__":
    backfill()