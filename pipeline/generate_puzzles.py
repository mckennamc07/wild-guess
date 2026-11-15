"""The weekly batch: pick a week of parks, have Claude write the puzzles,
validate them, and save them.

Usage (from the repo root):
    python pipeline/generate_puzzles.py --show-input   # print Claude's input; free, writes nothing
    python pipeline/generate_puzzles.py --dry-run      # call Claude + validate; saves to drafts/, not Supabase
    python pipeline/generate_puzzles.py                # the real run: saves to Supabase

Options:
    --start YYYY-MM-DD   first day of the week (default: next Monday, Eastern time)
    --seed N             reuse a seed to get the same parks (e.g. for the model test)
    --model ID           which Claude model writes the puzzles

Steps:
1. Pick 7 parks with select_parks.select_week().
2. Gather each park's NPS fact sheet, banned words and past clues, plus the
   latest calibration notes.
3. One Claude call writes all 7 puzzles as structured output.
4. puzzle_checks.py validates them. On failure, Claude gets one retry with
   the list of problems; a second failure stops the run.
5. Save: the puzzles (status 'approved', so they auto-publish), each park's
   last_shown_date/times_shown, the calibration notes, and the run's cost.
"""

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic
from pydantic import BaseModel

from db import get_client
from nps import fetch_fact_sheet
from puzzle_checks import check_puzzle, check_week
from select_parks import PARK_COLUMNS, Pick, new_seed, next_monday, park_from_row, select_week

# Chosen 2026-11-15 after playtesting a Sonnet week. The full model test
# (spec section 6) was skipped for now; try others any time with --model.
DEFAULT_MODEL = "claude-sonnet-5-5"

# Dollars per million tokens (input, output). Check current pricing before
# relying on these; they feed the cost column in generation_runs.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}

REPO_ROOT = Path(__file__).parent.parent
INSTRUCTIONS = (Path(__file__).parent / "prompts" / "puzzle_instructions.md").read_text()
DRAFTS_DIR = REPO_ROOT / "drafts"
NOTES_FROM_LAST_RUNS = 2


# --- The shape Claude must reply in ----------------------------------------

class PuzzleDraft(BaseModel):
    nps_code: str
    clue_1: str
    clue_2: str
    clue_3: str
    wrong_answers: list[str]
    accepted_answers: list[str]
    reasoning: str
    calibration_note: str


class WeekDraft(BaseModel):
    puzzles: list[PuzzleDraft]


# --- Gathering the inputs ----------------------------------------------------

def load_inputs(db, start: date, seed: int, with_fact_sheets: bool = True) -> dict:
    rows = db.table("parks").select(f"{PARK_COLUMNS}, short_name, states, banned_words").execute().data
    picks = select_week([park_from_row(r) for r in rows], start, seed)
    by_id = {r["id"]: r for r in rows}

    week_ids = [p.park.id for p in picks]
    past = db.table("puzzles").select("park_id, puzzle_date, clue_1, clue_2, clue_3") \
        .in_("park_id", week_ids).order("puzzle_date").execute().data

    recent_runs = db.table("generation_runs").select("id").eq("status", "succeeded") \
        .order("id", desc=True).limit(NOTES_FROM_LAST_RUNS).execute().data
    notes = []
    if recent_runs:
        notes = [n["note"] for n in db.table("calibration_notes").select("note")
                 .in_("run_id", [r["id"] for r in recent_runs]).order("id").execute().data]

    return {
        "picks": picks,
        "parks": {p.park.nps_code: {**by_id[p.park.id], "answer_format": p.answer_format} for p in picks},
        "past": {p.park.nps_code: [x for x in past if x["park_id"] == p.park.id] for p in picks},
        "park_names": sorted(r["name"] for r in rows),
        "notes": notes,
        "fact_sheets": {p.park.nps_code: fetch_fact_sheet(p.park.nps_code) for p in picks}
                       if with_fact_sheets else {},
    }


def build_prompt(inputs: dict) -> str:
    out = ["## Calibration notes from recent runs"]
    out += [f"- {n}" for n in inputs["notes"]] or ["(none yet)"]

    out += ["", "## All national park names (copy wrong answers exactly from here)"]
    out += [f"- {name}" for name in inputs["park_names"]]

    out += ["", "## This week's parks"]
    for pick in inputs["picks"]:
        code = pick.park.nps_code
        park = inputs["parks"][code]
        out += [
            "",
            f"### {pick.puzzle_date:%A %B %d}: {park['name']} (nps_code: {code})",
            f"Short name: {park['short_name']}",
            f"States: {', '.join(park['states'])}",
            f"Fame score: {pick.difficulty}",
            f"Answer format: {pick.answer_format}",
            f"Banned words (clues 1 and 2): {', '.join(park['banned_words']) or '(none)'}",
            "Past clues:",
        ]
        past = inputs["past"][code]
        out += [f"- {p['puzzle_date']}: 1) {p['clue_1']} 2) {p['clue_2']} 3) {p['clue_3']}" for p in past] or ["(none: first appearance)"]
        out += ["NPS data:", inputs["fact_sheets"][code]]

    out += ["", "Write one puzzle for each park above, using its nps_code."]
    return "\n".join(out)


# --- Calling Claude and validating ------------------------------------------

def ask_claude(client, model: str, prompt: str):
    kwargs = dict(
        model=model,
        max_tokens=64000,
        output_config={"effort": "high"},  # explicit: defaults differ by model
        system=INSTRUCTIONS,
        messages=[{"role": "user", "content": prompt}],
        output_format=WeekDraft,
    )
    # Server-side fallbacks: if the model declines on safety grounds, the API
    # retries on another model. Not available for Haiku.
    if not model.startswith("claude-haiku"):
        kwargs.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")

    # Streaming avoids HTTP timeouts on long responses. Reading the events as
    # they arrive also lets us print a heartbeat, so a slow call is visibly
    # alive and a stalled one is obvious.
    started = last_beat = time.monotonic()
    events = 0
    with client.beta.messages.stream(**kwargs) as stream:
        for _ in stream:
            events += 1
            if time.monotonic() - last_beat >= 30:
                last_beat = time.monotonic()
                print(f"  ...still writing ({last_beat - started:.0f}s, {events} stream events)")
        message = stream.get_final_message()
    print(f"  Claude finished in {time.monotonic() - started:.0f}s: "
          f"{message.usage.input_tokens} tokens in, {message.usage.output_tokens} out")
    if message.stop_reason != "end_turn":
        raise RuntimeError(f"Claude stopped early: stop_reason={message.stop_reason}")
    return message


def validate(drafts: list[dict], inputs: dict) -> list[str]:
    codes = [p.park.nps_code for p in inputs["picks"]]
    problems = check_week(drafts, codes)
    names = set(inputs["park_names"])
    for d in drafts:
        if d["nps_code"] not in inputs["parks"]:
            continue  # already reported by check_week
        past = [c for p in inputs["past"][d["nps_code"]] for c in (p["clue_1"], p["clue_2"])]
        problems += check_puzzle(d, inputs["parks"][d["nps_code"]], names, past)
    return problems


def write_week(client, model: str, inputs: dict) -> tuple[list[dict], dict]:
    """Ask Claude for the week, with one retry. Returns (drafts, usage totals)."""
    prompt = build_prompt(inputs)
    usage = {"input_tokens": 0, "output_tokens": 0}

    for attempt in (1, 2):
        print(f"Asking {model} to write the week (attempt {attempt} of 2)...")
        message = ask_claude(client, model, prompt)
        usage["input_tokens"] += message.usage.input_tokens
        usage["output_tokens"] += message.usage.output_tokens

        drafts = [p.model_dump() for p in message.parsed_output.puzzles]
        problems = validate(drafts, inputs)
        if not problems:
            return drafts, usage

        print(f"Attempt {attempt} failed validation:")
        for p in problems:
            print(f"  - {p}")
        # The retry gets the original input plus the failed draft and its
        # problems, and must return the whole week again.
        prompt = (
            build_prompt(inputs)
            + "\n\n## Your previous draft failed these checks\n"
            + "\n".join(f"- {p}" for p in problems)
            + "\n\nPrevious draft:\n" + json.dumps(drafts, indent=2, ensure_ascii=False)
            + "\n\nReturn the full week again with every problem fixed."
        )

    raise RuntimeError(f"puzzles still failed validation after a retry: {problems}")


def cost_of(model: str, usage: dict) -> float:
    in_price, out_price = PRICES[model]
    return usage["input_tokens"] / 1e6 * in_price + usage["output_tokens"] / 1e6 * out_price


# --- Saving ------------------------------------------------------------------

def save_week(db, run_id: int, drafts: list[dict], inputs: dict) -> None:
    by_code = {d["nps_code"]: d for d in drafts}
    picks: list[Pick] = inputs["picks"]

    # One insert for all seven rows: either all are saved or none are.
    db.table("puzzles").insert([{
        "puzzle_date": pick.puzzle_date.isoformat(),
        "park_id": pick.park.id,
        "run_id": run_id,
        "difficulty": pick.difficulty,
        "answer_format": pick.answer_format,
        "clue_1": by_code[pick.park.nps_code]["clue_1"],
        "clue_2": by_code[pick.park.nps_code]["clue_2"],
        "clue_3": by_code[pick.park.nps_code]["clue_3"],
        "wrong_answers": by_code[pick.park.nps_code]["wrong_answers"],
        "accepted_answers": by_code[pick.park.nps_code]["accepted_answers"],
        "reasoning": by_code[pick.park.nps_code]["reasoning"],
    } for pick in picks]).execute()

    for pick in picks:
        db.table("parks").update({
            "last_shown_date": pick.puzzle_date.isoformat(),
            "times_shown": pick.park.times_shown + 1,
        }).eq("id", pick.park.id).execute()

    notes = [{"run_id": run_id, "note": d["calibration_note"]} for d in drafts if d["calibration_note"].strip()]
    if notes:
        db.table("calibration_notes").insert(notes).execute()


def draft_file(drafts: list[dict], inputs: dict, start: date, seed: int, model: str,
               usage: dict) -> dict:
    """A dry run's output: everything play_drafts.py needs to play the week,
    plus the usage, so --from-draft can record the real cost."""
    by_code = {d["nps_code"]: d for d in drafts}
    return {
        "start": start.isoformat(),
        "seed": seed,
        "model": model,
        "usage": usage,
        "puzzles": [{
            "puzzle_date": pick.puzzle_date.isoformat(),
            "name": pick.park.name,
            "short_name": inputs["parks"][pick.park.nps_code]["short_name"],
            "difficulty": pick.difficulty,
            "answer_format": pick.answer_format,
            **by_code[pick.park.nps_code],
        } for pick in inputs["picks"]],
    }


def print_week(drafts: list[dict], inputs: dict) -> None:
    by_code = {d["nps_code"]: d for d in drafts}
    for pick in inputs["picks"]:
        d = by_code[pick.park.nps_code]
        print(f"\n{pick.puzzle_date:%a %b %d}  fame {pick.difficulty}  {pick.answer_format}  {pick.park.name}")
        for n in (1, 2, 3):
            print(f"  {n}. {d[f'clue_{n}']}")
        if d["wrong_answers"]:
            print(f"  wrong: {', '.join(d['wrong_answers'])}")


# --- Main ---------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a week of puzzles")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--show-input", action="store_true", help="print Claude's input and stop")
    mode.add_argument("--dry-run", action="store_true", help="call Claude but save to drafts/, not Supabase")
    mode.add_argument("--from-draft", type=Path, metavar="FILE",
                      help="save a reviewed dry-run draft to Supabase instead of calling Claude "
                           "(uses the draft's own start date, seed and model)")
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=sorted(PRICES))
    args = parser.parse_args()

    # Print each line as it happens, even when output goes to a file or a
    # GitHub Actions log (Python otherwise holds it until the end).
    sys.stdout.reconfigure(line_buffering=True)

    if args.from_draft:
        week = json.loads(args.from_draft.read_text())
        start, seed, model = date.fromisoformat(week["start"]), week["seed"], week["model"]
    else:
        start = args.start or next_monday(datetime.now(ZoneInfo("America/New_York")).date())
        seed = args.seed if args.seed is not None else new_seed()
        model = args.model
    print(f"Week of {start}, seed {seed}, model {model}")
    print("Loading parks and past clues...")
    db = get_client()
    # A saved draft already has its clues, so it doesn't need NPS fact sheets.
    inputs = load_inputs(db, start, seed, with_fact_sheets=not args.from_draft)

    if args.show_input:
        print(f"\n===== SYSTEM ({len(INSTRUCTIONS.split())} words) =====\n{INSTRUCTIONS}")
        print(f"===== USER =====\n{build_prompt(inputs)}")
        return

    if args.from_draft:
        # Keep only Claude's fields; the draft file also has date/name/format for the playtest tool.
        drafts = [{k: p[k] for k in PuzzleDraft.model_fields} for p in week["puzzles"]]
        picked = sorted(p.park.nps_code for p in inputs["picks"])
        if picked != sorted(d["nps_code"] for d in drafts):
            raise SystemExit("This draft's seed no longer picks the same parks (park history has "
                             "changed since it was written). Generate a fresh week instead.")
        problems = validate(drafts, inputs)
        if problems:
            raise SystemExit("Draft fails validation:\n" + "\n".join(f"  - {x}" for x in problems))

        def get_week():
            return drafts, week.get("usage")
    else:
        # read=180: give up if no data at all arrives for 3 minutes. The API
        # sends periodic pings while the model thinks, so silence that long
        # means the connection has stalled. (The SDK then retries, up to 2 times.)
        client = anthropic.Anthropic(timeout=anthropic.Timeout(1800, read=180, connect=15))

        if args.dry_run:
            drafts, usage = write_week(client, model, inputs)
            DRAFTS_DIR.mkdir(exist_ok=True)
            path = DRAFTS_DIR / f"{start}_{model}_seed{seed}.json"
            out = draft_file(drafts, inputs, start, seed, model, usage)
            path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
            print_week(drafts, inputs)
            print(f"\nSaved to {path} (not Supabase). "
                  f"Tokens: {usage['input_tokens']} in, {usage['output_tokens']} out (~${cost_of(model, usage):.2f})")
            return

        def get_week():
            return write_week(client, model, inputs)

    # Real run. Refuse to start if any of these dates already has a puzzle,
    # before spending anything on Claude.
    dates = [p.puzzle_date.isoformat() for p in inputs["picks"]]
    taken = db.table("puzzles").select("puzzle_date").in_("puzzle_date", dates).execute().data
    if taken:
        raise SystemExit(f"Puzzles already exist for {sorted(t['puzzle_date'] for t in taken)}; nothing done.")

    run_id = db.table("generation_runs").insert({"seed": seed, "model": model}).execute().data[0]["id"]
    try:
        drafts, usage = get_week()
        save_week(db, run_id, drafts, inputs)
    except Exception as e:
        # Record the failure so it's visible in the database, then re-raise.
        db.table("generation_runs").update({
            "status": "failed",
            "error_message": str(e)[:2000],
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()
        raise

    finished = {"status": "succeeded", "finished_at": datetime.now(timezone.utc).isoformat()}
    if usage:  # unknown for drafts written before usage was recorded
        finished |= {
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "cost_usd": round(cost_of(model, usage), 4),
        }
    db.table("generation_runs").update(finished).eq("id", run_id).execute()

    print_week(drafts, inputs)
    cost = f", cost ~${cost_of(model, usage):.2f}" if usage else ""
    print(f"\nSaved run {run_id}: {len(drafts)} puzzles for {dates[0]} to {dates[-1]}{cost}")


if __name__ == "__main__":
    main()
