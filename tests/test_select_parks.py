"""Tests for select_parks.py. Run from the repo root with: pytest

None of these touch Supabase: they build fake parks in memory.
Randomness is handled with seeds; a property that must hold "always" is
checked across many seeds.

Covers reproducibility, the 2-2-2-1 difficulty mix, no predictable
4-3-2-1 runs, the soft 14-day rule and its exact boundary, fallbacks to the
nearest level, and weighting toward parks shown less often.

Why it matters: these are the rules that keep the daily game varied and
unpredictable, and they're easy to break without noticing.
"""

from collections import Counter
from datetime import date, timedelta

import pytest

from select_parks import (
    Park,
    difficulty_slots,
    has_predictable_run,
    is_rested,
    levels_by_distance,
    next_monday,
    select_week,
)

import random

MONDAY = date(2026, 11, 23)
SEEDS = range(300)


def make_parks(per_level: int = 5, **overrides) -> list[Park]:
    """per_level fresh parks at each fame level, ids 1..4*per_level."""
    parks, next_id = [], 1
    for level in (4, 3, 2, 1):
        for _ in range(per_level):
            parks.append(Park(next_id, f"p{next_id}", f"Park {next_id}", level, None, 0))
            next_id += 1
    return parks


def shown(park: Park, days_before: int, start: date = MONDAY, times: int = 1) -> Park:
    """A copy of park, last shown `days_before` days before start."""
    return Park(park.id, park.nps_code, park.name, park.fame_score,
                start - timedelta(days=days_before), times)


# --- Reproducibility ----------------------------------------------------------

def test_same_seed_gives_same_week():
    parks = make_parks()
    assert select_week(parks, MONDAY, seed=42) == select_week(parks, MONDAY, seed=42)


def test_input_order_does_not_matter():
    parks = make_parks()
    assert select_week(parks, MONDAY, 42) == select_week(list(reversed(parks)), MONDAY, 42)


def test_different_seeds_give_different_weeks():
    parks = make_parks()
    weeks = {tuple(p.park.id for p in select_week(parks, MONDAY, s)) for s in range(20)}
    assert len(weeks) > 1


# --- Shape of the week -----------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS)
def test_week_is_seven_consecutive_days_with_no_repeats(seed):
    picks = select_week(make_parks(), MONDAY, seed)
    assert [p.puzzle_date for p in picks] == [MONDAY + timedelta(days=i) for i in range(7)]
    assert len({p.park.id for p in picks}) == 7


@pytest.mark.parametrize("seed", SEEDS)
def test_difficulty_is_balanced_2_2_2_1(seed):
    counts = Counter(p.difficulty for p in select_week(make_parks(), MONDAY, seed))
    assert sorted(counts.values()) == [1, 2, 2, 2]


@pytest.mark.parametrize("seed", SEEDS)
def test_difficulty_order_is_never_a_predictable_run(seed):
    slots = difficulty_slots(random.Random(seed), 7)
    assert not has_predictable_run(slots)


def test_predictable_run_detection():
    assert has_predictable_run([2, 4, 3, 2, 1, 3, 4])
    assert has_predictable_run([1, 2, 3, 4, 4, 2, 3])
    assert not has_predictable_run([4, 3, 2, 2, 1, 4, 3])  # 4-3-2 then 2: no run of 4


def test_answer_format_follows_fame():
    for pick in select_week(make_parks(), MONDAY, 7):
        assert pick.answer_format == {4: "type_in", 3: "first_letter_count",
                                      2: "choice_confusable", 1: "choice_easy"}[pick.difficulty]


# --- The 14-day rule ----------------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS)
def test_recent_park_skipped_when_alternatives_exist(seed):
    parks = make_parks()
    parks[0] = shown(parks[0], days_before=3)  # a fame-4 park
    assert parks[0].id not in {p.park.id for p in select_week(parks, MONDAY, seed)}


def test_rest_boundary_is_exactly_14_days():
    park = make_parks(per_level=1)[0]
    assert is_rested(shown(park, days_before=14), MONDAY)
    assert not is_rested(shown(park, days_before=13), MONDAY)
    assert not is_rested(shown(park, days_before=-3), MONDAY)  # already scheduled later
    assert is_rested(park, MONDAY)                              # never shown


def test_soft_rule_repeats_least_recent_park_at_same_level():
    parks = make_parks(per_level=2)
    # Both fame-1 parks stay recent all week (5 + 6 days < 14);
    # park 7 was shown longer ago.
    parks[6] = shown(parks[6], days_before=5)
    parks[7] = shown(parks[7], days_before=2)
    for seed in SEEDS:
        # The first fame-1 slot has both parks to choose from. (A second
        # fame-1 slot, if any, can only take the one that's left.)
        first = next(p for p in select_week(parks, MONDAY, seed) if p.slot_level == 1)
        assert first.difficulty == 1          # kept the difficulty...
        assert first.park.id == parks[6].id   # ...and used the least recent park
        assert "14 days" in first.rule_note


def test_empty_level_falls_back_to_nearest_level():
    parks = [p for p in make_parks() if p.fame_score != 3]
    for seed in SEEDS:
        for pick in select_week(parks, MONDAY, seed):
            if pick.slot_level == 3:
                assert pick.difficulty == 2  # tie between 2 and 4 goes to the easier level
                assert "level 3" in pick.rule_note


def test_levels_by_distance():
    assert levels_by_distance(3) == [3, 2, 4, 1]
    assert levels_by_distance(1) == [1, 2, 3, 4]


# --- Weighting and edge cases -----------------------------------------------

def test_parks_shown_less_often_are_picked_more():
    parks = make_parks(per_level=2)
    # Two fame-4 parks: one never shown, one shown 9 times (both long ago).
    parks[1] = shown(parks[1], days_before=200, times=9)
    # Count only each week's first fame-4 pick: with two fame-4 slots and two
    # fame-4 parks, the second slot has no choice to make.
    picks = Counter(
        next(p for p in select_week(parks, MONDAY, s) if p.slot_level == 4).park.id
        for s in range(2000)
    )
    assert picks[parks[0].id] > 5 * picks[parks[1].id]  # expected ratio is 10:1


def test_unscored_parks_are_never_picked():
    parks = make_parks()
    parks.append(Park(999, "new", "Unscored Park", None, None, 0))
    for seed in range(50):
        assert 999 not in {p.park.id for p in select_week(parks, MONDAY, seed)}


def test_too_few_parks_is_an_error():
    with pytest.raises(RuntimeError, match="ran out of parks"):
        select_week(make_parks(per_level=1), MONDAY, 1)  # 4 parks, 7 days


def test_next_monday():
    assert next_monday(date(2026, 11, 19)) == date(2026, 11, 23)  # Thursday
    assert next_monday(date(2026, 11, 23)) == date(2026, 11, 30)  # Monday -> following Monday
    assert next_monday(date(2026, 11, 22)) == date(2026, 11, 23)  # Sunday
