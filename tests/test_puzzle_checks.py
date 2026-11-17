"""Tests for puzzle_checks.py: each rule should catch a bad draft and pass a good one.

Pattern: start from one known-good puzzle (good_puzzle), break one thing,
and check that the matching problem is reported. pytest.mark.parametrize
runs one test over several bad inputs.

Why it matters: puzzles auto-publish, so these tests protect the clue rules
(no park or state names, banned words, fresh clues, valid wrong answers).
"""

import pytest

from puzzle_checks import check_puzzle, check_week, contains_phrase, normalize, overlap

PARK_NAMES = {
    "Zion National Park", "Bryce Canyon National Park", "Arches National Park",
    "Capitol Reef National Park", "Haleakalā National Park", "Everglades National Park",
}

ZION = {
    "name": "Zion National Park",
    "short_name": "Zion",
    "states": ["Utah"],
    "banned_words": ["Angels Landing", "The Narrows"],
    "answer_format": "choice_confusable",
}


def good_puzzle(**changes) -> dict:
    puzzle = {
        "nps_code": "zion",
        "clue_1": "Cream, pink, and red stone walls rise so high you tilt your head back to see the sky.",
        "clue_2": "A shuttle carries visitors along a scenic drive through the main canyon.",
        "clue_3": "Hikers climb chains up Angels Landing.",  # banned words allowed in clue 3
        "wrong_answers": ["Bryce Canyon National Park", "Arches National Park", "Capitol Reef National Park"],
        "accepted_answers": ["zion national park", "zion"],
        "reasoning": "...",
        "calibration_note": "",
    }
    return {**puzzle, **changes}


def problems(puzzle=None, park=ZION, past=()):
    return check_puzzle(puzzle or good_puzzle(), park, PARK_NAMES, list(past))


def test_good_puzzle_passes():
    assert problems() == []


# --- Text helpers --------------------------------------------------------------

def test_normalize_strips_accents_and_okina():
    assert normalize("Hawaiʻi Volcanoes") == "hawaii volcanoes"
    assert normalize("Haleakalā") == "haleakala"


def test_contains_phrase_is_whole_word():
    assert contains_phrase("Welcome to Zion's canyon", "Zion")
    assert not contains_phrase("Archers once hunted here", "Arches")
    assert contains_phrase("the summit of HALEAKALA", "Haleakalā")


def test_overlap():
    assert overlap("red cliffs above a river", "red cliffs above a river") == 1.0
    assert overlap("red cliffs", "blue lake") == 0.0


# --- Clue rules ------------------------------------------------------------------

@pytest.mark.parametrize("clue", [
    "Few places compare to Zion in spring.",
    "One of the best-known parks in Utah.",
    "Welcome to zion national park.",
])
def test_clue_naming_park_or_state_fails(clue):
    assert any("names the park" in p for p in problems(good_puzzle(clue_3=clue)))


def test_banned_word_fails_in_clue_1_and_2():
    assert any("banned word" in p for p in problems(good_puzzle(clue_2="Hike up Angels Landing.")))
    assert any("banned word" in p for p in problems(good_puzzle(clue_1="Wade through the narrows.")))


def test_banned_word_allowed_in_clue_3():
    assert problems(good_puzzle(clue_3="Wade upstream through The Narrows.")) == []


def test_clue_over_25_words_fails():
    long_clue = " ".join(["word"] * 26)
    assert any("26 words" in p for p in problems(good_puzzle(clue_1=long_clue)))


def test_empty_clue_fails():
    assert any("empty" in p for p in problems(good_puzzle(clue_2="  ")))


def test_repeating_a_past_clue_fails():
    past = ["A shuttle carries visitors along a scenic drive through the main canyon."]
    assert any("past clue" in p for p in problems(past=past))


def test_fresh_clue_passes_despite_past_clues():
    past = ["Snowmelt rushes past hanging gardens of ferns clinging to wet rock."]
    assert problems(past=past) == []


# --- Wrong answers -----------------------------------------------------------------

def test_choice_needs_exactly_three_wrong_answers():
    two = ["Bryce Canyon National Park", "Arches National Park"]
    assert any("exactly 3" in p for p in problems(good_puzzle(wrong_answers=two)))


def test_typed_format_takes_no_wrong_answers():
    park = {**ZION, "answer_format": "type_in"}
    assert any("no wrong answers" in p for p in problems(park=park))
    assert problems(good_puzzle(wrong_answers=[]), park=park) == []


def test_wrong_answer_must_be_a_listed_park():
    wrong = ["Bryce Canyon", "Arches National Park", "Capitol Reef National Park"]  # short name, not exact
    assert any("isn't an exact national park name" in p for p in problems(good_puzzle(wrong_answers=wrong)))


def test_answer_cannot_be_a_wrong_answer():
    wrong = ["Zion National Park", "Arches National Park", "Capitol Reef National Park"]
    park_names = PARK_NAMES | {"Zion National Park"}
    result = check_puzzle(good_puzzle(wrong_answers=wrong), ZION, park_names, [])
    assert any("correct answer is listed" in p for p in result)


def test_duplicate_wrong_answers_fail():
    wrong = ["Arches National Park", "Arches National Park", "Capitol Reef National Park"]
    assert any("duplicate" in p for p in problems(good_puzzle(wrong_answers=wrong)))


# --- Accepted answers ------------------------------------------------------------

def test_accepted_answers_must_be_lowercase():
    assert any("lowercase" in p for p in problems(good_puzzle(accepted_answers=["Zion", "zion"])))


def test_accepted_answers_must_include_short_name():
    assert any("short name" in p for p in problems(good_puzzle(accepted_answers=["zion national park"])))


# --- Week rules ------------------------------------------------------------------

def test_week_needs_each_park_exactly_once():
    week = [good_puzzle(nps_code="zion"), good_puzzle(nps_code="zion")]
    assert check_week(week, ["zion", "arch"])


def test_wrong_answer_repeated_across_the_week_fails():
    week = [
        good_puzzle(nps_code="zion", wrong_answers=["Arches National Park"]),
        good_puzzle(nps_code="brca", wrong_answers=["Arches National Park"]),
    ]
    assert any("more than one puzzle" in p for p in check_week(week, ["zion", "brca"]))


def test_good_week_passes():
    week = [
        good_puzzle(nps_code="zion", wrong_answers=["Arches National Park"]),
        good_puzzle(nps_code="brca", wrong_answers=["Everglades National Park"]),
    ]
    assert check_week(week, ["zion", "brca"]) == []
