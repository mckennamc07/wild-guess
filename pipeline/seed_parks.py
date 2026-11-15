"""One-time setup: load the national parks from the NPS API into `parks`.

Usage (from the repo root):
    python pipeline/seed_parks.py --dry-run   # print rows, write nothing
    python pipeline/seed_parks.py             # upsert into Supabase

Safe to run more than once: it upserts on nps_code, so a second run updates
the same 63 rows instead of adding duplicates. It only sends name,
short_name, nps_code and states, so it never overwrites fame scores or
banned words added later.
"""

import argparse

from db import get_client
from nps import fetch_all_parks

# The NPS codes for every national park, one per NPS record.
# Written out by hand because the API can't be filtered reliably:
# American Samoa has a blank designation, and non-parks like Wolf Trap
# National Park for the Performing Arts would match a text search.
# Sequoia & Kings Canyon is one NPS record (seki), so it's one park here.
PARK_CODES = [
    "acad", "arch", "badl", "bibe", "bisc", "blca", "brca", "cany", "care",
    "cave", "chis", "chir", "cong", "crla", "cuva", "deva", "dena", "drto",
    "ever", "gaar", "jeff", "glba", "glac", "grca", "grte", "grba", "grsa",
    "grsm", "gumo", "hale", "havo", "hosp", "indu", "isro", "jotr", "katm",
    "kefj", "kova", "lacl", "lavo", "maca", "meve", "mora", "neri", "noca",
    "npsa", "olym", "pefo", "pinn", "redw", "romo", "sagu", "seki", "shen",
    "thro", "viis", "voya", "whsa", "wica", "wrst", "yell", "yose", "zion",
]

# NPS gives states as postal codes ("CA,NV"). Clues would leak the full
# name ("California"), so that's what the validator needs to check against.
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    "AS": "American Samoa", "GU": "Guam", "MP": "Northern Mariana Islands",
    "PR": "Puerto Rico", "VI": "U.S. Virgin Islands",
}


def build_rows(nps_parks: list[dict]) -> list[dict]:
    """Turn NPS API records into rows for the parks table."""
    by_code = {p["parkCode"]: p for p in nps_parks}

    # Fail loudly rather than quietly seeding 62 parks.
    missing = [code for code in PARK_CODES if code not in by_code]
    if missing:
        raise RuntimeError(f"NPS API returned no record for: {missing}")

    rows = []
    for code in PARK_CODES:
        park = by_code[code]
        rows.append({
            "nps_code": code,
            "name": park["fullName"],    # "Acadia National Park"
            "short_name": park["name"],  # "Acadia"
            # "ID,MT,WY" -> ["Idaho", "Montana", "Wyoming"]
            # A KeyError here means NPS used a code missing from STATE_NAMES.
            "states": [STATE_NAMES[s.strip()] for s in park["states"].split(",")],
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print rows without writing to Supabase")
    args = parser.parse_args()

    rows = build_rows(fetch_all_parks())

    if args.dry_run:
        for row in rows:
            print(f"{row['nps_code']:5} {row['short_name']:32} {', '.join(row['states'])}")
        print(f"\n{len(rows)} parks (dry run, nothing written)")
        return

    # on_conflict="nps_code": if a park with this code exists, update it.
    get_client().table("parks").upsert(rows, on_conflict="nps_code").execute()
    print(f"Upserted {len(rows)} parks")


if __name__ == "__main__":
    main()
