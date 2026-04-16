"""
scripts/backfill_provinces.py
------------------------------
One-time script — run once after deploying scraper fixes to repair
existing tenders that have province = NULL or incorrect province.

Strategy:
  1. For tenders whose source_site matches a known domain, assign province
     from that domain's ground-truth mapping.
  2. For the rest, re-run detect_province() against title + description.

Run from project root:
    python scripts/backfill_provinces.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
import models
from scraper.utils import detect_province, detect_municipality, detect_town

# Ground-truth domain → province mapping (matches CITY_PORTALS + CRAWL_TARGETS)
DOMAIN_PROVINCE_MAP = {
    # Gauteng
    "joburg.org.za":               "Gauteng",
    "tshwane.gov.za":              "Gauteng",
    "ekurhuleni.gov.za":           "Gauteng",
    # Western Cape
    "capetown.gov.za":             "Western Cape",
    # KwaZulu-Natal
    "durban.gov.za":               "KwaZulu-Natal",
    # Eastern Cape
    "buffalocity.gov.za":          "Eastern Cape",
    "nelsonmandelabay.gov.za":     "Eastern Cape",
    # Free State
    "mangaung.co.za":              "Free State",
    # Northern Cape — provincial
    "ncgov.co.za":                 "Northern Cape",
    "northern-cape.gov.za":        "Northern Cape",
    # Northern Cape — Frances Baard
    "solplaatje.org.za":           "Northern Cape",
    "dikgatlong.gov.za":           "Northern Cape",
    "magareng.gov.za":             "Northern Cape",
    "phokwane.gov.za":             "Northern Cape",
    "francesbaarddc.gov.za":       "Northern Cape",
    # Northern Cape — ZF Mgcawu
    "dawidkruiper.gov.za":         "Northern Cape",
    "kaigarib.gov.za":             "Northern Cape",
    "kharahais.gov.za":            "Northern Cape",
    "kheis.gov.za":                "Northern Cape",
    "tsantsabane.gov.za":          "Northern Cape",
    "zfmgcawudc.gov.za":           "Northern Cape",
    # Northern Cape — Namakwa
    "richtersveld.gov.za":         "Northern Cape",
    "namakhoi.gov.za":             "Northern Cape",
    "kamiesberg.gov.za":           "Northern Cape",
    "hantam.gov.za":               "Northern Cape",
    "karoohoogland.gov.za":        "Northern Cape",
    "khai-ma.gov.za":              "Northern Cape",
    "namakwadc.gov.za":            "Northern Cape",
    # Northern Cape — Pixley ka Seme
    "siyathemba.gov.za":           "Northern Cape",
    "ubuntu.gov.za":               "Northern Cape",
    "umsobomvu.gov.za":            "Northern Cape",
    "emthanjeni.gov.za":           "Northern Cape",
    "kareeberg.gov.za":            "Northern Cape",
    "renosterberg.gov.za":         "Northern Cape",
    "thembelihle.gov.za":          "Northern Cape",
    "siyancuma.gov.za":            "Northern Cape",
    "pixleydc.gov.za":             "Northern Cape",
    # Northern Cape — John Taolo Gaetsewe
    "joemorolog.gov.za":           "Northern Cape",
    "gamagara.gov.za":             "Northern Cape",
    "ga-segonyana.gov.za":         "Northern Cape",
    "johntaologaetsewedc.gov.za":  "Northern Cape",
}


def backfill():
    db = SessionLocal()
    tenders = db.query(models.Tender).all()
    updated = 0

    for t in tenders:
        new_province = None

        # 1. Domain lookup — most reliable
        if t.source_site:
            site = t.source_site.lower().replace("www.", "")
            for domain, prov in DOMAIN_PROVINCE_MAP.items():
                if site == domain or site.endswith("." + domain):
                    new_province = prov
                    break

        # 2. Text detection fallback
        if not new_province:
            text = f"{t.title or ''} {t.description or ''} {t.issuing_body or ''}"
            new_province = detect_province(text)

        if new_province and new_province != t.province:
            text = f"{t.title or ''} {t.description or ''} {t.issuing_body or ''}"
            t.province = new_province
            t.municipality = detect_municipality(text, new_province)
            if not t.town:
                t.town = detect_town(text, new_province)
            updated += 1

    db.commit()
    db.close()
    print(f"Backfill complete — {updated} tenders updated out of {len(tenders)} total")


if __name__ == "__main__":
    backfill()