"""Client for the National Park Service API (developer.nps.gov)."""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://developer.nps.gov/api/v1"


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
