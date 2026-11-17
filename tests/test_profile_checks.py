"""Tests for profile_checks.py.

Covers quote matching (exact, tolerant of case and dashes, minimum length),
source quality and confidence levels, nation-name matching on cited pages,
"vanished people" framing, and paragraph splitting. Page texts are fake
strings, so no network calls are made.

Why it matters: these checks decide which history claims are dropped and
which nations are listed, so each rule is pinned down by a test.
"""

from profile_checks import (
    check_claims,
    check_framing,
    check_people,
    confidence_note,
    source_confidence,
    name_on_page,
    name_variants,
    quote_in_source,
    source_quality,
)

PAGE = ("The Chisos Mountains are the remains of volcanic activity that began about 46 million "
        "years ago. Erosion by the Rio Grande has since carved canyons up to 1,500 feet deep.")
URL = "https://www.nps.gov/bibe/learn/nature/geology.htm"


def claim(quote, url=URL):
    return {"text": "A fact.", "source_url": url, "quote": quote}


# --- Quotes ---------------------------------------------------------------------

def test_exact_quote_found():
    assert quote_in_source("remains of volcanic activity that began about 46 million years ago", PAGE)


def test_quote_tolerates_case_whitespace_and_dashes():
    page = "Canyons  up\nto 1,500 feet—deep."
    assert quote_in_source("canyons up to 1,500 feet - deep", page)


def test_altered_quote_not_found():
    assert not quote_in_source("remains of volcanic activity that began about 50 million years ago", PAGE)


def test_too_short_quote_rejected():
    assert not quote_in_source("Chisos Mountains", PAGE)


# --- Claims -------------------------------------------------------------------------

def test_good_claims_kept():
    claims = [claim("remains of volcanic activity that began about 46 million"),
              claim("Erosion by the Rio Grande has since carved canyons"),
              claim("carved canyons up to 1,500 feet deep")]
    kept, notes = check_claims(claims, {URL: PAGE})
    assert len(kept) == 3 and notes == []


def test_unverifiable_claims_dropped_and_noted():
    claims = [claim("remains of volcanic activity that began about 46 million"),
              claim("the park was formed entirely by ancient glaciers long ago"),
              claim("carved canyons up to 1,500 feet deep", url="https://example.com/other")]
    kept, notes = check_claims(claims, {URL: PAGE})
    assert len(kept) == 1
    checks = [n["check"] for n in notes]
    assert "quote_not_found" in checks
    assert "unknown_source" in checks
    assert "too_few_claims" in checks


# --- Source quality -----------------------------------------------------------------

def test_source_quality():
    assert source_quality("https://www.nps.gov/bibe/") == "high"
    assert source_quality("https://texashistory.unt.edu/x.pdf") == "high"
    assert source_quality("https://www.navajo-nsn.gov/") == "high"
    assert source_quality("https://en.wikipedia.org/wiki/X") == "low"
    assert source_quality("https://www.thestoryoftexas.com/x") == "medium"
    assert source_quality("https://gateway.ipfs.example/ipfs/Qm123/wiki/Jumano.html") == "low"


# --- Nation names ---------------------------------------------------------------------

def test_name_variants_drop_generic_words():
    assert name_variants("Mescalero Apache Tribe") == [{"mescalero", "apache"}]
    assert name_variants("Jumano Nation (Jumano)") == [{"jumano"}, {"jumano"}]
    # Descriptions after a dash or semicolon aren't part of the name.
    assert name_variants("Lipan Apache (Lipan Nde) — today the Lipan Apache Tribe of Texas") == \
        [{"lipan", "apache"}, {"lipan", "nde"}]


def test_name_on_page():
    page = "The Mescalero Apaches entered the region... later the Comanche passed through."
    assert name_on_page("Comanche Nation", page)
    assert name_on_page("Mescalero Apache Tribe", page)  # 'Apaches' counts as 'Apache'
    assert not name_on_page("Lipan Apache Tribe", page)   # but every identifying word must be there
    assert name_on_page("Jumano Nation (Jumano)", "Jumano traders guided expeditions.")
    assert not name_on_page("Jumano Nation", "Nothing relevant here.")


# --- People sections -------------------------------------------------------------

PEOPLE = {"nations": [{"name": "Comanche Nation", "connection": "Traveled the trail.", "present_day": "Lives on."}],
          "displacement": "", "documentation_note": ""}
NPS = "https://www.nps.gov/bibe/comanche.htm"
WIKI = "https://en.wikipedia.org/wiki/Comanche"


def grounding(confidence="high", urls=(NPS,)):
    return [{"field": f"nations[0].{k}", "citations": [{"url": u, "title": "t"} for u in urls],
             "confidence": confidence} for k in ("name", "connection", "present_day")]


def test_clean_people_section_has_no_notes():
    notes = check_people(PEOPLE, grounding(), {NPS: "The Comanche passed through."}, {NPS: True})
    assert notes == []


def test_people_flags():
    texts = {NPS: "No names here.", WIKI: "Nothing either."}
    notes = check_people(PEOPLE, grounding("low", (NPS, WIKI)), texts, {NPS: True, WIKI: False})
    checks = {n["check"] for n in notes}
    assert {"low_confidence", "link_broken", "low_quality_source", "name_not_found"} <= checks


def test_missing_citations_and_no_nations():
    notes = check_people(PEOPLE, [], {}, {})
    assert any(n["check"] == "uncited" for n in notes)
    assert any(n["check"] == "no_nations" for n in check_people({"nations": []}, [], {}, {}))


# --- Source confidence ------------------------------------------------------------

GOV = ["https://www.nps.gov/a", "https://www.usgs.gov/b", "https://history.utexas.edu/c"]


def test_three_high_quality_sources_is_strong():
    assert source_confidence(GOV)[0] == "strong"


def test_same_page_twice_counts_once():
    level, reason = source_confidence([GOV[0], GOV[0], GOV[1]])
    assert level == "limited" and "only 2 high-quality sources" in reason


def test_no_high_quality_sources_is_thin():
    level, reason = source_confidence(["https://en.wikipedia.org/wiki/X", "https://someblog.com/y"])
    assert level == "thin" and "no government" in reason
    assert source_confidence([])[0] == "thin"


def test_low_exa_confidence_makes_it_limited():
    level, reason = source_confidence(GOV, ["high", "low", None])
    assert level == "limited" and "2 fields with low or unknown" in reason


def test_confidence_note_only_when_not_strong():
    assert confidence_note("strong", "fine") == []
    assert confidence_note("thin", "nothing found")[0]["detail"] == "THIN: nothing found"


# --- Framing ------------------------------------------------------------------------

def test_vanishing_framing_flagged():
    notes = check_framing("The Jumano ceased to exist as a distinct people and later vanished.")
    assert notes and "ceased to exist" in notes[0]["detail"] and "vanished" in notes[0]["detail"]


def test_living_framing_passes():
    assert check_framing("The Comanche Nation today is headquartered in Lawton, Oklahoma.") == []


def test_low_quality_notes_grouped_per_nation():
    notes = check_people(PEOPLE, grounding("high", (NPS, WIKI)), {NPS: "Comanche"}, {NPS: True, WIKI: True})
    low = [n for n in notes if n["check"] == "low_quality_source"]
    assert len(low) == 1 and low[0]["detail"].startswith("nations[0] relies partly on")


# --- Paragraphs ---------------------------------------------------------------

from profile_checks import paragraphs  # noqa: E402


def test_short_text_stays_one_paragraph():
    assert paragraphs("One sentence. Two sentences.") == "One sentence. Two sentences."


def test_long_text_splits_into_two_sentence_paragraphs():
    text = "First. Second. Third. Fourth. Fifth."
    assert paragraphs(text) == "First. Second.\n\nThird. Fourth.\n\nFifth."


def test_writer_paragraph_breaks_are_kept():
    assert paragraphs("A one.\n\nB one. B two.") == "A one.\n\nB one. B two."


def test_abbreviations_dont_end_sentences():
    text = "Mt. Elias rises high. The U.S. Army came ca. 1880. People stayed. Some left. Others returned."
    paras = paragraphs(text).split("\n\n")
    assert paras[0] == "Mt. Elias rises high. The U.S. Army came ca. 1880."


def test_one_high_quality_source_is_strong_for_a_single_fact():
    assert source_confidence(["https://www.nps.gov/a"], min_high=1)[0] == "strong"
    assert source_confidence(["https://www.nps.gov/a"])[0] == "limited"


# --- Which nations are listed, and what's shown ------------------------------

from profile_checks import assess_nation  # noqa: E402

NPS2 = "https://www.nps.gov/bibe/history.htm"
EDU = "https://texashistory.unt.edu/doc.pdf"


def g(field, urls, confidence="high"):
    return {"field": field, "citations": [{"url": u, "title": "t"} for u in urls], "confidence": confidence}


def test_well_sourced_nation_with_info_is_listed_and_shown():
    nation = {"name": "Comanche Nation", "connection": "Traveled the trail.", "present_day": "Lawton, Oklahoma."}
    grounding = [g("nations[0].name", [NPS]), g("nations[0].connection", [NPS, EDU]),
                 g("nations[0].present_day", [NPS, EDU])]
    a = assess_nation(0, nation, grounding)
    assert a["listed"] and not a["little_information"] and not a["limited"]
    assert set(a["info"]) == {"connection", "present_day"}


def test_named_by_good_source_but_no_info_is_still_listed():
    nation = {"name": "Chisos", "connection": "", "present_day": ""}
    a = assess_nation(0, nation, [g("nations[0].name", [NPS], "medium")])
    assert a["listed"] and a["little_information"] and a["info"] == {}


def test_uncited_information_is_not_shown():
    nation = {"name": "Chisos", "connection": "They farmed here.", "present_day": ""}
    a = assess_nation(0, nation, [g("nations[0].name", [NPS])])  # no grounding for connection
    assert a["little_information"] and "connection" not in a["info"]


def test_nation_named_only_by_weak_sources_is_not_listed():
    nation = {"name": "Tonkawa", "connection": "Ranged here.", "present_day": ""}
    a = assess_nation(0, nation, [g("nations[0].name", [WIKI], "medium"),
                                  g("nations[0].connection", [WIKI], "medium")])
    assert not a["listed"]
    assert "no government" in a["name_reason"]


def test_high_exa_confidence_lists_even_without_high_quality_source():
    nation = {"name": "Kickapoo", "connection": "", "present_day": ""}
    assert assess_nation(0, nation, [g("nations[0].name", [WIKI], "high")])["listed"]


def test_information_from_one_good_source_is_marked_limited():
    nation = {"name": "Jumano", "connection": "Traded at La Junta.", "present_day": ""}
    a = assess_nation(0, nation, [g("nations[0].name", [NPS]), g("nations[0].connection", [NPS])])
    assert a["listed"] and a["limited"] and a["info"]["connection"]["confidence"] == "limited"
