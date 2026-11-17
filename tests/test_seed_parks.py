"""Tests for seed_parks.py's NPS-to-row conversion (no network or database).

Covers picking the park photo: first image, alt text with a fallback to the
title, and no photo when NPS has none.

Why it matters: the photo shows on the reveal, and its alt text is what
screen-reader users get.
"""

from seed_parks import park_photo


def test_uses_first_image_with_alt_text_and_credit():
    nps = {"images": [
        {"url": "https://nps.gov/a.jpg", "title": "Electric Peak", "altText": "A snowy peak at sunset",
         "caption": "Sunset", "credit": "NPS / Jacob W. Frank"},
        {"url": "https://nps.gov/b.jpg", "title": "Second", "altText": "", "caption": "", "credit": ""},
    ]}
    assert park_photo(nps) == {
        "url": "https://nps.gov/a.jpg", "title": "Electric Peak", "alt": "A snowy peak at sunset",
        "caption": "Sunset", "credit": "NPS / Jacob W. Frank",
    }


def test_alt_text_falls_back_to_title():
    nps = {"images": [{"url": "https://nps.gov/a.jpg", "title": "Blooming Cenizo", "altText": ""}]}
    assert park_photo(nps)["alt"] == "Blooming Cenizo"


def test_no_images_means_no_photo():
    assert park_photo({"images": []}) is None
    assert park_photo({}) is None
