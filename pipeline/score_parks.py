"""One-time setup: draft a fame score and banned-words list for every park.

Usage (from the repo root):
    python pipeline/score_parks.py            # ask Claude, write the draft file
    python pipeline/score_parks.py --apply    # after your review: save to Supabase

Step 1 writes pipeline/data/fame_scores.json. Nothing reaches the database
until you've reviewed (and edited) that file and run --apply. It refuses to
overwrite an existing draft, so a stray re-run can't wipe your edits.

Key decisions:
- Opus scores all parks in one call, so scores are judged relative to each
  other instead of one park at a time.
- Structured output with fame_score as Literal[1, 2, 3, 4]: the API can't
  return a score outside the range.
- A two-step draft-then-apply flow, so the scores are reviewed (and edited)
  by a human before they change how the game plays.

Why it matters: fame score is the only thing that sets difficulty and
answer format, and banned words feed the clue validator. Both come from here.
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Literal

import anthropic
from pydantic import BaseModel

from db import get_client
from nps import fetch_all_parks

MODEL = "claude-opus-5-5"
DRAFT_PATH = Path(__file__).parent / "data" / "fame_scores.json"

# Opus 5.5 list prices, dollars per million tokens. Only used to print an
# estimate; check current pricing before relying on it.
INPUT_PRICE, OUTPUT_PRICE = 4.00, 20.00


# --- The shape Claude must reply in ----------------------------------------
# Pydantic models double as the JSON schema sent to the API (structured
# output), and the SDK turns the reply back into these objects for us.

class ParkScore(BaseModel):
    nps_code: str
    # Literal = only these values are allowed; becomes an enum in the schema.
    fame_score: Literal[1, 2, 3, 4]
    fame_reasoning: str
    banned_words: list[str]


class ScoringResult(BaseModel):
    parks: list[ParkScore]


SYSTEM_PROMPT = """\
You are helping build Wild Guess, a daily U.S. national park guessing game.
Players get three clues and guess the park. You are scoring every park once,
at setup.

## Fame score (1-4): how recognizable the park is to a typical American adult
who is not a park enthusiast. It sets the puzzle format:
- 4 = well known: most people could name it unprompted (they type the answer).
- 3 = medium: familiar once you hear it (shown the first letter and length).
- 2 = lesser known: people have heard of it but couldn't place it (multiple
  choice with similar wrong answers).
- 1 = least known: most people have never heard of it (easy multiple choice).

Scores are relative across the whole list, so compare parks to each other.
Score honestly rather than forcing an even split, but the game needs parks at
every level, so don't crowd nearly everything into one or two levels.

fame_reasoning: one plain sentence explaining the score.

## Banned words: the famous landmark and feature names that would give the
park away if they appeared in an early clue (e.g. for Yellowstone: "Old
Faithful", "Grand Prismatic Spring"). Proper nouns only, 3-10 per park, most
recognizable first. Don't include the park's own name or its state; those are
already blocked separately. Use only landmarks you are confident are real and
inside or defining that park; the provided NPS description is your reference.

Return exactly one entry per park, using the nps_code given."""


def build_prompt(parks: list[dict], descriptions: dict[str, str]) -> str:
    lines = ["Score these parks:\n"]
    for p in parks:
        lines.append(
            f"- nps_code: {p['nps_code']}\n"
            f"  name: {p['name']}\n"
            f"  states: {', '.join(p['states'])}\n"
            f"  NPS description: {descriptions.get(p['nps_code'], '')}\n"
        )
    return "\n".join(lines)


def check_result(scores: list[dict], expected_codes: set[str]) -> None:
    """Don't trust the model's bookkeeping: every park exactly once."""
    codes = [s["nps_code"] for s in scores]
    duplicates = {c for c in codes if codes.count(c) > 1}
    missing = expected_codes - set(codes)
    unknown = set(codes) - expected_codes
    if duplicates or missing or unknown:
        raise RuntimeError(f"duplicates={duplicates} missing={missing} unknown={unknown}")


def print_distribution(scores: list[dict]) -> None:
    counts = Counter(s["fame_score"] for s in scores)
    for level in (4, 3, 2, 1):
        print(f"  fame {level}: {counts[level]:2} parks")


def draft() -> None:
    if DRAFT_PATH.exists():
        raise SystemExit(f"{DRAFT_PATH} already exists. Review it and run --apply, "
                         "or delete it to draft again.")

    parks = get_client().table("parks").select("nps_code, name, states").order("nps_code").execute().data
    descriptions = {p["parkCode"]: p["description"] for p in fetch_all_parks()}

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    print(f"Asking {MODEL} to score {len(parks)} parks (takes a minute or two)...")

    # Streaming keeps a long response from hitting HTTP timeouts.
    # The beta client is needed only for `fallbacks`: if the model declines a
    # request on safety grounds, the API retries it on a fallback model.
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=64000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "high"},  # Opus 5.5 defaults to medium
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_prompt(parks, descriptions)}],
        output_format=ScoringResult,
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason != "end_turn":
        raise RuntimeError(f"Claude stopped early: stop_reason={message.stop_reason}")

    scores = [s.model_dump() for s in message.parsed_output.parks]
    check_result(scores, {p["nps_code"] for p in parks})

    # Add the park name so the file is readable during review.
    names = {p["nps_code"]: p["name"] for p in parks}
    scores = [{"name": names[s["nps_code"]], **s} for s in sorted(scores, key=lambda s: s["nps_code"])]

    DRAFT_PATH.parent.mkdir(exist_ok=True)
    DRAFT_PATH.write_text(json.dumps(scores, indent=2, ensure_ascii=False) + "\n")

    usage = message.usage
    cost = usage.input_tokens / 1e6 * INPUT_PRICE + usage.output_tokens / 1e6 * OUTPUT_PRICE
    print(f"Wrote {DRAFT_PATH}")
    print_distribution(scores)
    print(f"Tokens: {usage.input_tokens} in, {usage.output_tokens} out (~${cost:.2f})")
    print("Next: review the file, edit anything you disagree with, then run --apply.")


def apply() -> None:
    scores = json.loads(DRAFT_PATH.read_text())
    db = get_client()
    check_result(scores, {p["nps_code"] for p in db.table("parks").select("nps_code").execute().data})

    for s in scores:
        if s["fame_score"] not in (1, 2, 3, 4):
            raise RuntimeError(f"{s['nps_code']}: fame_score must be 1-4")

    # update (not upsert): the parks already exist, we're filling in columns.
    for s in scores:
        db.table("parks").update({
            "fame_score": s["fame_score"],
            "fame_reasoning": s["fame_reasoning"],
            "banned_words": s["banned_words"],
        }).eq("nps_code", s["nps_code"]).execute()

    print(f"Saved scores for {len(scores)} parks")
    print_distribution(scores)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="save the reviewed draft to Supabase")
    args = parser.parse_args()
    apply() if args.apply else draft()


if __name__ == "__main__":
    main()
