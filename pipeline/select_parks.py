"""Pick the parks for a week of puzzles. Plain code, no AI.

Usage (from the repo root), preview only, writes nothing:
    python pipeline/select_parks.py                      # next Monday, new seed
    python pipeline/select_parks.py --seed 1234          # reproduce a week
    python pipeline/select_parks.py --start 2026-11-23

generate_puzzles.py calls select_week() and does the saving.

The rules:
1. Difficulty: 7 days get a 2-2-2-1 split across the four fame levels (which
   level gets 1 is random), in shuffled order. The order is reshuffled if it
   contains a run like 4-3-2-1 or 1-2-3-4, so difficulty can't be predicted
   by weekday.
2. Each day's park is drawn at random from parks at that day's level, with
   parks shown less often weighted higher: weight = 1 / (1 + times_shown).
3. A park shown in the last 14 days is skipped while there are alternatives.
   The rule is soft: if every park at a level is recent, the one shown
   longest ago is used. Only an empty level falls back to the nearest level.
4. A park is never used twice in the same week.

Everything random comes from one seeded generator, so the same parks, start
date and seed always give the same week.
"""

import argparse
import random
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

LEVELS = (4, 3, 2, 1)
REST_DAYS = 14

ANSWER_FORMATS = {
    4: "type_in",
    3: "first_letter_count",
    2: "choice_confusable",
    1: "choice_easy",
}


@dataclass(frozen=True)
class Park:
    id: int
    nps_code: str
    name: str
    fame_score: int | None
    last_shown_date: date | None
    times_shown: int


@dataclass(frozen=True)
class Pick:
    puzzle_date: date
    park: Park
    slot_level: int   # the difficulty the shuffle asked for
    rule_note: str    # "" normally; explains any fallback

    @property
    def difficulty(self) -> int:
        # Difficulty always follows the park's own fame score.
        return self.park.fame_score

    @property
    def answer_format(self) -> str:
        return ANSWER_FORMATS[self.difficulty]


# --- Difficulty slots --------------------------------------------------------

def has_predictable_run(slots: list[int]) -> bool:
    """True if any 4 days in a row go 4-3-2-1 or 1-2-3-4."""
    for i in range(len(slots) - 3):
        window = slots[i:i + 4]
        steps = {b - a for a, b in zip(window, window[1:])}
        if steps == {1} or steps == {-1}:
            return True
    return False


def difficulty_slots(rng: random.Random, days: int) -> list[int]:
    # Every level once per 4 days, plus the remainder spread over random levels.
    slots = list(LEVELS) * (days // 4) + rng.sample(LEVELS, days % 4)
    for _ in range(1000):
        rng.shuffle(slots)
        if not has_predictable_run(slots):
            return slots
    raise RuntimeError("couldn't find a non-predictable difficulty order")


# --- Picking parks -----------------------------------------------------------

def is_rested(park: Park, day: date) -> bool:
    """Not shown in the REST_DAYS days before `day`.

    A last_shown_date after `day` (already scheduled later) counts as recent.
    """
    if park.last_shown_date is None:
        return True
    return (day - park.last_shown_date).days >= REST_DAYS


def levels_by_distance(level: int) -> list[int]:
    """[level, then nearest levels]. Ties go to the lower (easier) level."""
    return sorted(LEVELS, key=lambda lvl: (abs(lvl - level), lvl))


def pick_park(rng: random.Random, parks: list[Park], level: int, day: date,
              used: set[int]) -> tuple[Park, str]:
    for lvl in levels_by_distance(level):
        pool = [p for p in parks if p.fame_score == lvl and p.id not in used]
        if not pool:
            continue  # level empty (or used up): try the nearest level

        note = "" if lvl == level else f"no parks left at level {level}; used level {lvl}"

        rested = [p for p in pool if is_rested(p, day)]
        if rested:
            weights = [1 / (1 + p.times_shown) for p in rested]
            return rng.choices(rested, weights=weights, k=1)[0], note

        # Soft 14-day rule: every park here is recent, so take the one
        # shown longest ago (ties broken by id, so it stays reproducible).
        park = min(pool, key=lambda p: (p.last_shown_date, p.id))
        recent = f"all level-{lvl} parks shown within {REST_DAYS} days; repeated the least recent"
        return park, f"{note}; {recent}" if note else recent

    raise RuntimeError("ran out of parks: fewer scored parks than days")


def select_week(parks: list[Park], start: date, seed: int, days: int = 7) -> list[Pick]:
    rng = random.Random(seed)
    # Sort so the result depends only on the data, not on the order it arrived in.
    scored = sorted((p for p in parks if p.fame_score is not None), key=lambda p: p.id)

    picks, used = [], set()
    for offset, level in enumerate(difficulty_slots(rng, days)):
        day = start + timedelta(days=offset)
        park, note = pick_park(rng, scored, level, day, used)
        used.add(park.id)
        picks.append(Pick(day, park, level, note))
    return picks


# --- Loading and the preview command ----------------------------------------

PARK_COLUMNS = "id, nps_code, name, fame_score, last_shown_date, times_shown"


def park_from_row(r: dict) -> Park:
    """A Supabase parks row (which may have extra columns) -> Park."""
    return Park(
        id=r["id"],
        nps_code=r["nps_code"],
        name=r["name"],
        fame_score=r["fame_score"],
        last_shown_date=date.fromisoformat(r["last_shown_date"]) if r["last_shown_date"] else None,
        times_shown=r["times_shown"],
    )


def load_parks() -> list[Park]:
    from db import get_client  # imported here so tests don't need Supabase

    rows = get_client().table("parks").select(PARK_COLUMNS).execute().data
    return [park_from_row(r) for r in rows]


def next_monday(today: date) -> date:
    """The Monday after `today` (a week ahead if today is Monday)."""
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def new_seed() -> int:
    # 62 random bits: fits in the generation_runs.seed column (a signed bigint).
    return secrets.randbits(62)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview a week of park picks (writes nothing)")
    parser.add_argument("--start", type=date.fromisoformat, help="first day, YYYY-MM-DD (default: next Monday)")
    parser.add_argument("--seed", type=int, help="reuse a seed to reproduce a week")
    args = parser.parse_args()

    today = datetime.now(ZoneInfo("America/New_York")).date()
    start = args.start or next_monday(today)
    seed = args.seed if args.seed is not None else new_seed()

    print(f"Week of {start}  (seed {seed})\n")
    for pick in select_week(load_parks(), start, seed):
        line = f"{pick.puzzle_date:%a %b %d}  fame {pick.difficulty}  {pick.answer_format:18}  {pick.park.name}"
        print(line + (f"\n    note: {pick.rule_note}" if pick.rule_note else ""))


if __name__ == "__main__":
    main()
