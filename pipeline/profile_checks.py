"""Automated checks for park profile sections.

Nothing here decides what gets published: every section is saved as a
draft for human review. These checks write review notes that point the
reviewer at what needs a closer look, and drop claims that can't be backed
by their source.

A review note is a dict: {"check": "<short id>", "detail": "<plain English>"}.
"""

import re
from urllib.parse import urlparse

from puzzle_checks import normalize

MIN_QUOTE_WORDS = 6
MIN_CLAIMS = 3

# Generic words in nation names that don't identify a nation on their own.
GENERIC_NAME_WORDS = {
    "nation", "nations", "tribe", "tribes", "tribal", "people", "peoples", "band", "bands",
    "of", "the", "and", "indian", "indians", "community", "communities", "confederated",
    "council", "reservation", "pueblo", "native", "village",
}

LOW_QUALITY_DOMAINS = {"wikipedia.org", "encyclopedia.com", "native-americans.com", "grokipedia.com"}


def note(check: str, detail: str) -> dict:
    return {"check": check, "detail": detail}


def flatten(text: str) -> str:
    """normalize() plus: straight quotes, dashes and whitespace made uniform,
    so a quote copied from a page still matches the page text."""
    text = normalize(text)
    text = re.sub(r"[“”\"]", "", text)
    text = re.sub(r"[‐-‒–—-]", " ", text)
    text = re.sub(r"[^a-z0-9.,;:%$ ]", " ", text)
    return " ".join(text.split())


def quote_in_source(quote: str, source_text: str) -> bool:
    return len(quote.split()) >= MIN_QUOTE_WORDS and flatten(quote) in flatten(source_text)


def domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def source_quality(url: str) -> str:
    """'high' (government, university, tribal, Smithsonian), 'low', or 'medium'."""
    d = domain(url)
    if d.endswith((".gov", ".edu", ".nsn.us")) or d == "si.edu" or d.endswith(".si.edu"):
        return "high"
    if any(d == low or d.endswith("." + low) for low in LOW_QUALITY_DOMAINS):
        return "low"
    if "/ipfs/" in url:  # mirrored copies of other sites (often Wikipedia)
        return "low"
    return "medium"


# --- Source confidence ----------------------------------------------------------

STRONG_MIN_HIGH_SOURCES = 3

# Shown to players at the top of a section whose sourcing isn't strong.
PLAYER_NOTES = {
    "limited": "*Only a few reliable sources were found online for this section.*",
    "thin": "*Little reliable information was found online for this section, so it may be incomplete.*",
}
NATION_NOTE = "*Based on limited sources.*"


def source_confidence(urls: list[str], confidences: list[str | None] = (),
                      min_high: int = STRONG_MIN_HIGH_SOURCES) -> tuple[str, str]:
    """How well-sourced something is: ('strong' | 'limited' | 'thin', reason).

    urls: the pages it cites
    confidences: Exa's per-field confidence, if any ('high', 'medium', 'low', None)
    min_high: high-quality sources needed for 'strong' (1 for a one-sentence fun fact)
    """
    high = len({u for u in urls if source_quality(u) == "high"})
    unsure = sum(1 for c in confidences if c in (None, "low"))
    if high == 0:
        return "thin", "no government, university, tribal or museum sources were found"
    reasons = []
    if high < min_high:
        reasons.append(f"only {high} high-quality source{'s' if high > 1 else ''}")
    if unsure:
        reasons.append(f"{unsure} field{'s' if unsure > 1 else ''} with low or unknown Exa confidence")
    if reasons:
        return "limited", "; ".join(reasons)
    return "strong", f"{high} high-quality sources"


def confidence_note(level: str, reason: str) -> list[dict]:
    """A review note for anything less than strong."""
    return [] if level == "strong" else [note("source_confidence", f"{level.upper()}: {reason}")]


# Wording that frames nations as gone, which the research rules forbid.
VANISHING_WORDS = re.compile(
    r"\b(ceased to exist|no longer exist\w*|extinct|vanished|disappeared|died out|wiped out|lost tribe)\b",
    re.IGNORECASE,
)


def check_framing(text: str) -> list[dict]:
    hits = sorted({m.group(0).lower() for m in VANISHING_WORDS.finditer(text)})
    if not hits:
        return []
    return [note("vanishing_framing",
                 f"uses wording that frames a people as gone ({', '.join(hits)}); "
                 "the rules call for describing nations as living and present-day")]


# --- Fun facts and formation: Claude-written claims --------------------------

def check_claims(claims: list[dict], page_texts: dict[str, str],
                 min_claims: int = MIN_CLAIMS) -> tuple[list[dict], list[dict]]:
    """Keep only claims whose quote really appears on the page they cite.

    claims: [{"text", "source_url", "quote"}]
    page_texts: {url: text} for the pages Claude was given
    min_claims: fewer surviving claims than this gets a review note
    Returns (kept_claims, review_notes).
    """
    kept, notes = [], []
    for i, claim in enumerate(claims, 1):
        url = claim["source_url"]
        if url not in page_texts:
            notes.append(note("unknown_source", f"claim {i} dropped: cites a page it wasn't given ({url})"))
        elif not quote_in_source(claim["quote"], page_texts[url]):
            notes.append(note("quote_not_found", f"claim {i} dropped: its supporting quote isn't on {url}"))
        else:
            kept.append(claim)
            if source_quality(url) == "low":
                notes.append(note("low_quality_source", f"claim {i} relies on a lower-quality source: {url}"))
    if len(kept) < min_claims:
        notes.append(note("too_few_claims", f"only {len(kept)} claims survived the checks"))
    return kept, notes


# --- Paragraphs -------------------------------------------------------------------

# Abbreviations whose period doesn't end a sentence.
ABBREVIATIONS = r"(?<!\bSt\.)(?<!\bMt\.)(?<!\bFt\.)(?<!\bDr\.)(?<!\bU\.S\.)(?<!\bca\.)(?<!\bc\.)(?<!\bvs\.)(?<!\bNo\.)"
SENTENCE_END = re.compile(ABBREVIATIONS + r"(?<=[.!?])\s+(?=[A-Z\"“(])")


def paragraphs(text: str, max_sentences: int = 3) -> str:
    """Keep the writer's own paragraph breaks; split any paragraph longer than
    max_sentences into chunks of about two sentences, so nothing reads as a
    wall of text."""
    out = []
    for para in re.split(r"\n\s*\n", text.strip()):
        sentences = SENTENCE_END.split(para.strip())
        if len(sentences) <= max_sentences:
            out.append(para.strip())
        else:
            out += [" ".join(sentences[i:i + 2]) for i in range(0, len(sentences), 2)]
    return "\n\n".join(p for p in out if p)


# --- Who lived here first: Exa Deep Search fields ----------------------------

def name_variants(name: str) -> list[set[str]]:
    """'Jumano Nation (Jumano)' -> [{'jumano'}, {'jumano'}]: the identifying
    words of the name and of any name in brackets. Anything after a dash,
    semicolon or comma is description, not name, and is ignored."""
    name = re.split(r"\s[—–-]\s|;|,", name)[0]
    parts = [re.sub(r"\(.*?\)", "", name)] + re.findall(r"\((.*?)\)", name)
    variants = []
    for part in parts:
        words = {w for w in flatten(part).split() if w not in GENERIC_NAME_WORDS and len(w) > 2}
        if words:
            variants.append(words)
    return variants


def name_on_page(name: str, page_text: str) -> bool:
    """True if every identifying word of the name (or of a bracketed
    alternative) appears on the page. Simple plurals count: a page saying
    'Apaches' mentions 'Apache'."""
    page_words = set(flatten(page_text).split())
    page_words |= {w[:-1] for w in page_words if w.endswith("s")}
    return any(variant <= page_words for variant in name_variants(name))


INFO_FIELDS = ("connection", "present_day")
INFO_MIN_HIGH = 2  # high-quality sources for a piece of information to count as strong
LITTLE_INFO_NOTE = "*Little information was found about this nation's ties to the park.*"


def assess_nation(i: int, nation: dict, grounding: list[dict]) -> dict:
    """Decide what to show for one nation.

    Two separate questions:
    - Is the nation really connected to this land? Judged from the sources
      for its *name*. It's listed if at least one high-quality source names
      it, or Exa is highly confident.
    - What do we know? Each information field is shown only if it has text
      AND citations, with its own sources and confidence. A listed nation
      with no cited information is still shown, marked "little information".
    """
    grounded = {g["field"]: g for g in grounding}

    name_g = grounded.get(f"nations[{i}].name") or {"citations": [], "confidence": None}
    name_urls = list(dict.fromkeys(c["url"] for c in name_g["citations"]))
    name_level, name_reason = source_confidence(name_urls, [name_g["confidence"]], min_high=1)

    info = {}
    for key in INFO_FIELDS:
        text = (nation.get(key) or "").strip()
        g = grounded.get(f"nations[{i}].{key}")
        if not text or not g or not g["citations"]:
            continue  # nothing cited: don't show it
        urls = list(dict.fromkeys(c["url"] for c in g["citations"]))
        level, _ = source_confidence(urls, [g["confidence"]], min_high=INFO_MIN_HIGH)
        info[key] = {"text": paragraphs(text), "urls": urls, "confidence": level}

    return {
        "name": nation.get("name", "").strip(),
        "listed": name_level == "strong" or name_g["confidence"] == "high",
        "name_urls": name_urls,
        "name_reason": name_reason,
        "info": info,
        "little_information": not info,
        "limited": any(f["confidence"] != "strong" for f in info.values()),
    }


def check_people(content: dict, grounding: list[dict], page_texts: dict[str, str],
                 loads: dict[str, bool]) -> list[dict]:
    """Review notes for a Deep Search result.

    grounding: [{"field", "citations": [{"url", "title"}], "confidence"}]
    page_texts: {url: text} for cited pages (for the name check)
    loads: {url: True/False}, whether each cited page loaded
    """
    notes = []
    grounded = {g["field"]: g for g in grounding}
    low_by_group: dict[str, set[str]] = {}

    if not content.get("nations"):
        notes.append(note("no_nations", "no nations were identified; check whether that's accurate"))

    for i, nation in enumerate(content.get("nations") or []):
        for key in ("name", "connection", "present_day"):
            if (nation.get(key) or "").strip() and f"nations[{i}].{key}" not in grounded:
                notes.append(note("uncited", f"nations[{i}].{key} has no citations"))

    for field, g in grounded.items():
        if g["confidence"] in (None, "low"):
            notes.append(note("low_confidence", f"{field}: Exa confidence is {g['confidence'] or 'unknown'}"))

        urls = [c["url"] for c in g["citations"]]
        if not urls:
            notes.append(note("uncited", f"{field} has no citations"))
        broken = [u for u in urls if not loads.get(u, False)]
        if urls and len(broken) == len(urls):
            notes.append(note("links_broken", f"{field}: none of its cited pages loaded"))
        elif broken:
            notes.append(note("link_broken", f"{field}: cited page didn't load: {', '.join(broken)}"))
        group = re.match(r"nations\[\d+\]|[a-z_]+", field).group(0)  # 'nations[2]' or 'displacement'
        low_by_group.setdefault(group, set()).update(u for u in urls if source_quality(u) == "low")

        m = re.fullmatch(r"nations\[(\d+)\]\.name", field)
        if m:
            name = content["nations"][int(m.group(1))]["name"]
            if not any(name_on_page(name, page_texts.get(u, "")) for u in urls):
                notes.append(note("name_not_found", f"'{name}' doesn't appear on any page cited for it"))

    # One note per nation (or top-level field) rather than one per field.
    for group, low in low_by_group.items():
        if low:
            notes.append(note("low_quality_source", f"{group} relies partly on: {', '.join(sorted(low))}"))

    return notes
