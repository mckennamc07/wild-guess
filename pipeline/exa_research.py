"""Exa calls for park profiles.

Two kinds of research, matching how much each section needs checking:
- search_sources(): a standard Exa search that returns pages *with their
  text*. Used for fun facts and formation: Claude writes only from these
  pages, and code checks each claim's quote against the page text.
- research_people(): an Exa Deep Search that returns structured fields
  (nations, displacement...) with citations and a confidence level per
  field. Used for "who lived here first".
fetch_page_texts() downloads cited pages so code can check names against them.

Key decisions:
- Standard searches are limited to .gov, .edu and the Smithsonian, and AI
  encyclopedias are excluded: citing them would be citing a model's memory.
- Deep Search gets an output schema (PEOPLE_SCHEMA), so results come back as
  fields the checks and the frontend can use, not free text.
- The people instructions ask for nations' own names, present-day framing,
  and empty fields over guesses.

Why it matters: the project rule is "never write history from model
memory". This module is where every source for the park profiles comes from.
"""

from dataclasses import dataclass

from dotenv import load_dotenv
from exa_py import Exa

load_dotenv()

# AI-generated encyclopedias: citing them for history would be citing a
# model's memory with extra steps.
EXCLUDE_DOMAINS = ["grokipedia.com"]

# Where standard searches look. *.gov covers NPS and USGS; *.edu covers
# universities; si.edu is the Smithsonian.
SOURCE_DOMAINS = ["nps.gov", "*.gov", "*.edu", "si.edu"]

SEARCH_QUERIES = {
    "fun_facts": "surprising, little-known and delightful facts about {name}",
    "formation": "how the landscape of {name} formed: geology, rocks, and the forces and timescales that shaped it",
}

PEOPLE_INSTRUCTIONS = (
    "Research the Indigenous nations who lived on, used, and shaped the land of this national park, and "
    "anyone, Indigenous or not, who was displaced when the park was created. Use the names nations use for "
    "themselves. Describe them as living, present-day nations, never as vanished peoples. Prefer tribal "
    "nation, NPS ethnographic, academic, and museum sources. List every nation a reliable source connects "
    "to this land, even when little else is documented about them; leave a field empty rather than guess. "
    "Never fill gaps: if little is documented or sources disagree, say so plainly."
)

PEOPLE_SCHEMA = {
    "type": "object",
    "properties": {
        "nations": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string",
                     "description": "only the nation's name for itself, optionally with the common English "
                                    "name in brackets, e.g. 'Ndé (Mescalero Apache Tribe)'; no other text"},
            "connection": {"type": "string",
                           "description": "one or two sentences on how they lived on, used, or shaped this "
                                          "land; if it runs longer, start a new paragraph (blank line) where "
                                          "the time period or topic changes"},
            "present_day": {"type": "string",
                            "description": "one or two sentences on the nation today and its continuing ties "
                                           "to this land, or that little is documented"},
        }}},
        "displacement": {"type": "string",
                         "description": "people (Indigenous or not) removed or displaced when the park was "
                                        "created, in short paragraphs; empty if none is documented"},
        "documentation_note": {"type": "string",
                               "description": "say if little is documented or sources disagree; empty otherwise"},
    },
}


@dataclass(frozen=True)
class Source:
    title: str
    url: str
    text: str


@dataclass(frozen=True)
class PeopleResearch:
    content: dict           # matches PEOPLE_SCHEMA
    grounding: list[dict]   # [{"field": "nations[0].name", "citations": [{"url", "title"}], "confidence"}]
    cost: float


def search_sources(park_name: str, section: str, num_results: int = 6) -> tuple[list[Source], float]:
    """Pages about one park and section, with their text. Returns (sources, cost)."""
    r = Exa().search(
        SEARCH_QUERIES[section].format(name=park_name),
        type="auto",
        num_results=num_results,
        include_domains=SOURCE_DOMAINS,
        contents={"text": {"max_characters": 8000}},
    )
    sources = [Source(x.title or x.url, x.url, x.text or "") for x in r.results if x.text]
    return sources, r.cost_dollars.total


def research_people(park_name: str, states: list[str]) -> PeopleResearch:
    r = Exa().search(
        f"Indigenous nations and displaced communities of {park_name}, {', '.join(states)}",
        type="deep",
        system_prompt=PEOPLE_INSTRUCTIONS,
        output_schema=PEOPLE_SCHEMA,
        exclude_domains=EXCLUDE_DOMAINS,
        contents={"highlights": True},
    )
    # Exa returns objects; turn them into plain dicts we can test and save.
    grounding = [{
        "field": g.field,
        "citations": [{"url": c.url, "title": c.title} for c in g.citations],
        "confidence": g.confidence,
    } for g in (r.output.grounding or [])]
    return PeopleResearch(r.output.content or {}, grounding, r.cost_dollars.total)


def fetch_page_texts(urls: list[str]) -> dict[str, str]:
    """Text of each page (HTML or PDF) via Exa Contents, for checking names."""
    if not urls:
        return {}
    r = Exa().get_contents(urls, text={"max_characters": 50000})
    texts = {}
    for x in r.results:
        # Exa may return a normalized URL; `id` is the one we asked for.
        texts[x.url] = texts[x.id] = x.text or ""
    return texts
