"""Research the post-guess park profiles with Exa and save them as drafts.

Usage (from the repo root):
    python pipeline/enrich_profiles.py --dry-run     # research + check; write a review file only
    python pipeline/enrich_profiles.py               # same, and save drafts to Supabase

Options:
    --parks romo bibe ...   which parks (default: every park that has a puzzle, i.e. the pilot)
    --sections fun_facts formation people_history   (default: all three)

How each section is made:
- fun_facts, formation: Exa search returns source pages with their text
  (exa_research.search_sources). Claude writes claims using only those pages,
  each with an exact supporting quote. Code drops any claim whose quote
  isn't on the page it cites (profile_checks.check_claims).
- people_history: Exa Deep Search returns structured fields with citations
  and a confidence level per field (exa_research.research_people). Code
  checks that cited pages load and that each nation's name appears on the
  pages cited for it (profile_checks.check_people).

Every row is saved with status 'draft' (never shown publicly) and
review_notes listing anything the checks flagged. A review file in drafts/
shows each section with its notes, for reading before you approve.

Key decisions:
- Claude writes only from pages Exa returned, and each claim must carry an
  exact quote. Code, not Claude, decides whether the quote is really there.
- History uses Deep Search's own structured output and citations rather
  than Claude rewriting it, so every sentence stays tied to a source.
- Nothing auto-publishes: profiles are drafts until approved in
  review_profiles.py.
- Raw Exa output is saved to drafts/ so a reviewer can see what came back.

Why it matters: this produces the "learn about the park" half of the game,
including the Indigenous history, which has the highest bar for accuracy.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import httpx
from pydantic import BaseModel

from db import get_client
from exa_research import PeopleResearch, fetch_page_texts, research_people, search_sources
from generate_puzzles import DEFAULT_MODEL, PRICES
from profile_checks import (
    INFO_FIELDS,
    LITTLE_INFO_NOTE,
    NATION_NOTE,
    PLAYER_NOTES,
    assess_nation,
    check_claims,
    check_framing,
    check_people,
    confidence_note,
    note,
    paragraphs,
    source_confidence,
    source_quality,
)

SECTIONS = ("fun_facts", "formation", "people_history")
WRITING_INSTRUCTIONS = (Path(__file__).parent / "prompts" / "profile_writing.md").read_text()
DRAFTS_DIR = Path(__file__).parent.parent / "drafts"


# --- Fun facts and formation ----------------------------------------------------

class Claim(BaseModel):
    text: str
    source_url: str
    quote: str


class SectionDraft(BaseModel):
    claims: list[Claim]


def write_claims(client, park_name: str, section: str, sources) -> tuple[list[dict], float]:
    """Claude writes claims from the source pages. Returns (claims, cost)."""
    pages = "\n\n".join(f"### Source: {s.title}\nURL: {s.url}\n\n{s.text}" for s in sources)
    with client.beta.messages.stream(
        model=DEFAULT_MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "high"},
        system=WRITING_INSTRUCTIONS,
        messages=[{"role": "user", "content":
                   f"Park: {park_name}\nSection: {section}\n\n## Source pages\n\n{pages}"}],
        output_format=SectionDraft,
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason != "end_turn":
        raise RuntimeError(f"Claude stopped early: stop_reason={message.stop_reason}")
    in_price, out_price = PRICES[DEFAULT_MODEL]
    cost = message.usage.input_tokens / 1e6 * in_price + message.usage.output_tokens / 1e6 * out_price
    return [c.model_dump() for c in message.parsed_output.claims], cost


def build_written_section(client, park: dict, section: str) -> dict:
    sources, exa_cost = search_sources(park["name"], section)
    claims, claude_cost = write_claims(client, park["name"], section, sources)
    if section == "fun_facts":
        # One sentence for players: the top-ranked candidate that checks out.
        kept, notes = check_claims(claims, {s.url: s.text for s in sources}, min_claims=1)
        kept = kept[:1]
        notes = [] if kept else notes  # failed runner-ups don't matter once one fact passed
        body = kept[0]["text"] if kept else ""
        min_high = 1
    else:
        kept, notes = check_claims(claims, {s.url: s.text for s in sources})
        body = paragraphs(" ".join(c["text"] for c in kept))
        min_high = 3

    titles = {s.url: s.title for s in sources}
    cited = list(dict.fromkeys(c["source_url"] for c in kept))  # unique, in order
    level, reason = source_confidence(cited, min_high=min_high)
    return {
        "body": with_player_note(body, level),
        "sources": source_list(cited, titles),
        "review_notes": confidence_note(level, reason) + notes,
        "confidence": (level, reason),
        "cost": exa_cost + claude_cost,
        "detail": (f"top verified fact of {len(claims)} candidates from {len(sources)} pages"
                   if section == "fun_facts" else
                   f"{len(kept)} of {len(claims)} claims kept from {len(sources)} pages"),
    }


def with_player_note(body: str, level: str) -> str:
    """Open a section with a plain note for players when sourcing isn't strong."""
    return f"{PLAYER_NOTES[level]}\n\n{body}" if level in PLAYER_NOTES else body


def source_list(urls: list[str], titles: dict[str, str]) -> list[dict]:
    """[{title, url, quality}] with tidy titles (some pages have stray whitespace)."""
    return [{"title": " ".join((titles.get(u) or u).split()), "url": u, "quality": source_quality(u)}
            for u in urls]


# --- Who lived here first ---------------------------------------------------------

def check_links(urls: list[str]) -> dict[str, bool]:
    """Whether each page loads (any status below 400, after redirects)."""
    loads = {}
    headers = {"User-Agent": "Mozilla/5.0 (compatible; wild-guess-source-checker)"}
    with httpx.Client(follow_redirects=True, timeout=20, headers=headers) as http:
        for url in urls:
            try:
                loads[url] = http.get(url).status_code < 400
            except httpx.HTTPError:
                loads[url] = False
    return loads


def people_body(nations: list[dict], content: dict) -> str:
    """Readable Markdown of the listed nations (the frontend uses `details`)."""
    labels = {"connection": "", "present_day": "*Today:* "}
    parts = []
    for n in nations:
        lines = [f"**{n['name']}**"]
        if n["little_information"]:
            lines.append(LITTLE_INFO_NOTE)
        for key, field in n["info"].items():
            lines.append(labels[key] + field["text"])
        if n["limited"]:
            lines.append(NATION_NOTE)
        parts.append("\n\n".join(lines))
    if (content.get("displacement") or "").strip():
        parts.append(f"**Displacement when the park was created**\n\n{paragraphs(content['displacement'])}")
    if (content.get("documentation_note") or "").strip():
        parts.append(f"*{content['documentation_note']}*")
    return "\n\n".join(parts) or "*Little is documented in the sources found.*"


def people_details(nations: list[dict], content: dict, titles: dict[str, str], level: str) -> dict:
    """The structured version saved in profile_sections.details: every listed
    nation, each piece of information with its own sources, for the
    frontend's list of nations to tap and expand."""
    return {
        "confidence": level,
        "player_note": PLAYER_NOTES.get(level),
        "nations": [{
            "name": n["name"],
            "named_by": source_list(n["name_urls"], titles),
            "little_information": n["little_information"],
            **{key: ({"text": f["text"], "confidence": f["confidence"], "sources": source_list(f["urls"], titles)}
                     if (f := n["info"].get(key)) else None)
               for key in INFO_FIELDS},
        } for n in nations],
        "displacement": paragraphs(content.get("displacement") or ""),
        "documentation_note": content.get("documentation_note") or "",
    }


def build_people_section(park: dict, research: PeopleResearch | None = None) -> dict:
    """research: pass earlier Exa output (e.g. from a profiles_raw_*.json file)
    to re-check and save it without searching again."""
    research = research or research_people(park["name"], park["states"])
    content, grounding = research.content, research.grounding
    urls = list(dict.fromkeys(c["url"] for g in grounding for c in g["citations"]))
    loads = check_links(urls)
    page_texts = fetch_page_texts([u for u in urls if loads[u]])
    notes = check_people(content, grounding, page_texts, loads)

    assessed = [assess_nation(i, n, grounding) for i, n in enumerate(content.get("nations") or [])]
    listed = [n for n in assessed if n["listed"]]
    for n in assessed:
        if not n["listed"]:
            notes.append(note("not_listed", f"'{n['name']}' isn't shown to players: {n['name_reason']} "
                                            f"names it ({', '.join(n['name_urls']) or 'no citations'})"))
        elif n["little_information"]:
            notes.append(note("little_information", f"'{n['name']}' is listed with little information"))

    body = people_body(listed, content)
    notes += check_framing(body)

    # Section level: from the cited information of the listed nations. A
    # nation shown as "little information" is already labeled honestly, so
    # it doesn't drag the level down; no listed nations at all means thin.
    info_urls = [u for n in listed for f in n["info"].values() for u in f["urls"]]
    confidences = [g["confidence"] for g in grounding
                   if any(g["field"].startswith(f"nations[{i}].") for i, n in enumerate(assessed) if n["listed"])]
    level, reason = source_confidence(info_urls, confidences)
    if not listed:
        level, reason = "thin", "no nation is named by a high-quality source"

    titles = {c["url"]: c["title"] for g in grounding for c in g["citations"]}
    return {
        "body": with_player_note(body, level),
        "details": people_details(listed, content, titles, level),
        "sources": source_list(urls, titles),
        "review_notes": confidence_note(level, reason) + notes,
        "confidence": (level, reason),
        "cost": research.cost + 0.001 * len(page_texts),
        "detail": (f"{len(listed)} of {len(assessed)} nations listed "
                   f"({sum(n['little_information'] for n in listed)} with little information), "
                   f"{len(urls)} cited pages"),
        "raw": {"content": content, "grounding": grounding},
    }


# --- Main --------------------------------------------------------------------------

def review_markdown(results: list[dict]) -> str:
    out = ["# Park profile review", ""]
    for r in results:
        level, reason = r["confidence"]
        out += [f"## {r['park']} — {r['section']}", "",
                f"**Source confidence: {level.upper()}** ({reason})", "",
                f"_{r['detail']}; ~${r['cost']:.3f}_", ""]
        if r["review_notes"]:
            out += ["**Review notes:**"] + [f"- `{n['check']}` {n['detail']}" for n in r["review_notes"]] + [""]
        else:
            out += ["**Review notes:** none, every automated check passed.", ""]
        out += [r["body"], "", "**Sources:**"] + \
            [f"- [{s['title']}]({s['url']}) ({s['quality']})" for s in r["sources"]] + [""]
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Research park profiles with Exa")
    parser.add_argument("--parks", nargs="+", metavar="NPS_CODE")
    parser.add_argument("--sections", nargs="+", choices=SECTIONS, default=list(SECTIONS))
    parser.add_argument("--dry-run", action="store_true", help="write the review file only, not Supabase")
    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    db = get_client()
    parks = db.table("parks").select("id, nps_code, name, states").order("name").execute().data
    if args.parks:
        parks = [p for p in parks if p["nps_code"] in args.parks]
    else:  # the pilot: parks that already have a puzzle
        with_puzzles = {r["park_id"] for r in db.table("puzzles").select("park_id").execute().data}
        parks = [p for p in parks if p["id"] in with_puzzles]

    client = anthropic.Anthropic(timeout=anthropic.Timeout(600, read=180, connect=15))
    results = []
    for park in parks:
        for section in args.sections:
            print(f"{park['name']}: {section}...")
            if section == "people_history":
                r = build_people_section(park)
            else:
                r = build_written_section(client, park, section)
            r |= {"park": park["name"], "park_id": park["id"], "section": section}
            results.append(r)
            print(f"  source confidence {r['confidence'][0].upper()}: {r['detail']}, "
                  f"{len(r['review_notes'])} review notes, ~${r['cost']:.3f}")

            if not args.dry_run:
                db.table("profile_sections").insert({
                    "park_id": park["id"],
                    "section": section,
                    "body": r["body"],
                    "sources": r["sources"],
                    "provider": "exa",
                    "status": "draft",
                    "review_notes": r["review_notes"],
                    "details": r.get("details"),  # history only; None for plain-text sections
                }).execute()

    DRAFTS_DIR.mkdir(exist_ok=True)
    stamp = f"{datetime.now():%Y-%m-%d_%H%M}"
    review = DRAFTS_DIR / f"profiles_review_{stamp}.md"
    review.write_text(review_markdown(results))
    # Raw Exa output for history, so a reviewer can see exactly what came back.
    raw = [{"park": r["park"], **r["raw"]} for r in results if "raw" in r]
    if raw:
        (DRAFTS_DIR / f"profiles_raw_{stamp}.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False))

    total = sum(r["cost"] for r in results)
    where = "review file only (dry run)" if args.dry_run else "drafts saved to Supabase"
    print(f"\n{len(results)} sections, ~${total:.2f}. {where}. Review: {review}")


if __name__ == "__main__":
    main()
