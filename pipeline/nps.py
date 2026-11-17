"""Client for the National Park Service API (developer.nps.gov).

What: two calls. fetch_all_parks() returns every NPS unit for seeding the
parks table; fetch_fact_sheet() turns one park's description, activities,
things to do and places into a plain-text sheet for the puzzle writer.

Key decisions:
- The API key goes in a header, not the URL, so it can't leak into an error
  message that prints the URL.
- Fact sheets are capped (MAX_THINGS_TO_DO, MAX_PLACES) and skip empty
  places, so a huge park like Yellowstone stays a few thousand tokens.
- Filtering is done in Python because the API's parkCode filter breaks on
  URL-encoded commas.

Why it matters: the puzzle instructions say clues may only use facts from
this sheet, so it's the factual ground truth for every clue Claude writes.
"""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://developer.nps.gov/api/v1"


def _get(endpoint: str, **params) -> dict:
    key = os.environ.get("NPS_API_KEY")
    if not key:
        raise RuntimeError("NPS_API_KEY must be set (see .env.example)")
    response = httpx.get(f"{BASE_URL}/{endpoint}", params=params,
                         headers={"X-Api-Key": key}, timeout=90)
    response.raise_for_status()
    return response.json()


# Caps keep each park's fact sheet to a few thousand tokens. Yellowstone alone
# has 500+ places; the puzzle writer needs material, not everything.
MAX_THINGS_TO_DO = 30
MAX_PLACES = 40


def fetch_fact_sheet(park_code: str) -> str:
    """Everything the puzzle writer may use about one park, as plain text.

    The puzzle instructions say clues may only use facts from this sheet.
    """
    park = _get("parks", parkCode=park_code)["data"][0]
    things = _get("thingstodo", parkCode=park_code, limit=MAX_THINGS_TO_DO)["data"]
    places = _get("places", parkCode=park_code, limit=500)["data"]
    # Many places are bare entries (a picnic area, a parking lot) with no
    # description; skip those and keep the ones that say something.
    places = [p for p in places if p.get("listingDescription", "").strip()][:MAX_PLACES]

    lines = [
        f"Description: {park['description'] or '(none provided)'}",
        f"Weather: {park['weatherInfo']}",
        f"Activities: {', '.join(a['name'] for a in park['activities'])}",
        f"Topics: {', '.join(t['name'] for t in park['topics'])}",
        "Things to do:",
        *(f"- {t['title']}: {t['shortDescription']}" for t in things),
        "Places:",
        *(f"- {p['title']}: {p['listingDescription']}" for p in places),
    ]
    return "\n".join(lines)


def fetch_all_parks() -> list[dict]:
    """Return every NPS unit (~475: parks, monuments, historic sites...).

    We fetch everything in one request and filter in Python. The API's
    parkCode filter breaks when the commas between codes get URL-encoded.
    """
    key = os.environ.get("NPS_API_KEY")
    if not key:
        raise RuntimeError("NPS_API_KEY must be set (see .env.example)")

    response = httpx.get(
        f"{BASE_URL}/parks",
        params={"limit": 1000},
        # Sent as a header rather than in the URL, so the key never shows up
        # in error messages that print the URL.
        headers={"X-Api-Key": key},
        timeout=90,
    )
    response.raise_for_status()  # turns a 403/500 into a Python error
    return response.json()["data"]
