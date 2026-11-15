"""Tests for the terminal playtest tool's helpers."""

import pytest

from play_drafts import canonical, is_correct, letter_hint, show_remaining_clues

PUZZLE = {
    "clue_1": "First clue.",
    "clue_2": "Second clue.",
    "clue_3": "Third clue.",
}


# --- Answer checking -----------------------------------------------------------

def test_canonical_drops_case_punctuation_and_filler():
    assert canonical("Rocky Mountain National Park!") == "rocky mountain"
    assert canonical("Hawaiʻi Volcanoes NP") == "hawaii volcanoes"
    assert canonical("National Park of American Samoa") == "american samoa"


@pytest.mark.parametrize("guess", [
    "yellowstone", "YELLOWSTONE", "Yellowstone National Park", "yelowstone", "yellowstone np",
])
def test_accepts_reasonable_guesses(guess):
    assert is_correct(guess, ["yellowstone national park", "yellowstone"])


@pytest.mark.parametrize("guess", ["", "   ", "national park", "glacier"])
def test_rejects_empty_filler_and_wrong_park(guess):
    assert not is_correct(guess, ["glacier bay national park", "glacier bay"])


# --- First-letter hint ---------------------------------------------------------

def test_letter_hint_shows_only_first_letter():
    assert letter_hint("Big Bend") == "B _ _   _ _ _ _  National Park"


def test_letter_hint_keeps_okina_and_punctuation():
    assert letter_hint("Hawaiʻi Volcanoes") == "H _ _ _ _ ʻ _   _ _ _ _ _ _ _ _ _  National Park"
    assert letter_hint("Wrangell - St Elias") == "W _ _ _ _ _ _ _   -   _ _   _ _ _ _ _  National Park"


# --- Showing the clues you didn't need ----------------------------------------

def test_solving_on_clue_1_shows_clues_2_and_3(capsys):
    show_remaining_clues(PUZZLE, solved_on=1)
    out = capsys.readouterr().out
    assert "Clue 2: Second clue." in out
    assert "Clue 3: Third clue." in out
    assert "Clue 1" not in out


def test_solving_on_clue_2_shows_only_clue_3(capsys):
    show_remaining_clues(PUZZLE, solved_on=2)
    out = capsys.readouterr().out
    assert "Clue 3: Third clue." in out
    assert "Clue 2" not in out


def test_solving_on_clue_3_shows_nothing(capsys):
    show_remaining_clues(PUZZLE, solved_on=3)
    assert capsys.readouterr().out == ""
