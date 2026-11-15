"""Play draft puzzle weeks in the terminal. A playtest tool, not the real game.

Usage (from the repo root):
    python pipeline/play_drafts.py drafts/2026-11-16_claude-sonnet-5-5_seed2026.json

    # Blind model test: give several drafts of the same week. They're shuffled
    # and labeled Set A, B, C; which model wrote which is revealed at the end.
    python pipeline/play_drafts.py drafts/2026-11-16_*_seed2026.json

Each puzzle shows clue 1; a wrong guess (or just Enter) reveals the next
clue. Solving on clue 1 scores 3, clue 2 scores 2, clue 3 scores 1. After
each puzzle you can rate it 1-5 and leave a note. Ratings are saved to
drafts/playtest_<time>.json for the model-test write-up.

Typed answers use a simple stand-in for the real game's checker: it ignores
case, accents, punctuation and "national park", and allows small typos.
"""

import argparse
import json
import random
import re
import string
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from puzzle_checks import normalize

FILLER_WORDS = {"national", "park", "parks", "np", "nat", "preserve", "and", "the", "of"}
TYPO_TOLERANCE = 0.85  # how similar (0-1) a guess must be to count


def canonical(text: str) -> str:
    """'Rocky Mountain National Park!' -> 'rocky mountain'."""
    words = re.sub(r"[^a-z0-9]+", " ", normalize(text)).split()
    return " ".join(w for w in words if w not in FILLER_WORDS)


def is_correct(guess: str, accepted: list[str]) -> bool:
    g = canonical(guess)
    if not g:
        return False
    return any(SequenceMatcher(None, g, canonical(a)).ratio() >= TYPO_TOLERANCE for a in accepted)


def letter_hint(short_name: str) -> str:
    """'Big Bend' -> 'B _ _   _ _ _ _  National Park'."""
    words = []
    for i, word in enumerate(short_name.split()):
        # The ʻokina counts as a letter to Python, but players shouldn't type it.
        chars = [c if (not c.isalpha() or c == "ʻ" or (i == 0 and j == 0)) else "_"
                 for j, c in enumerate(word)]
        words.append(" ".join(chars))
    return "   ".join(words) + "  National Park"


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def show_remaining_clues(p: dict, solved_on: int) -> None:
    """After an early solve, show the clues the player didn't need,
    so every clue still gets judged."""
    remaining = range(solved_on + 1, 4)
    if remaining:
        print("The clues you didn't need:")
        for n in remaining:
            print(f"  Clue {n}: {p[f'clue_{n}']}")


def play_puzzle(p: dict) -> int:
    """Play one puzzle; return points scored (3, 2, 1 or 0)."""
    fmt = p["answer_format"]
    print(f"\n{'=' * 60}\n{p['puzzle_date']}  ({fmt.replace('_', ' ')})")

    options = None
    if fmt.startswith("choice"):
        options = p["wrong_answers"] + [p["name"]]
        random.shuffle(options)
    elif fmt == "first_letter_count":
        print(f"Hint: {letter_hint(p['short_name'])}")

    for n in (1, 2, 3):
        print(f"\nClue {n}: {p[f'clue_{n}']}")
        if options:
            for i, opt in enumerate(options, 1):
                print(f"  {i}) {opt}")
            choice = ask("Your pick (1-4, Enter for next clue): ")
            correct = choice.isdigit() and 1 <= int(choice) <= 4 and options[int(choice) - 1] == p["name"]
        else:
            guess = ask("Your guess (Enter for next clue): ")
            correct = is_correct(guess, p["accepted_answers"])

        if correct:
            points = 4 - n
            print(f"Correct! {p['name']}  (+{points})")
            show_remaining_clues(p, solved_on=n)
            return points
        print("Not it." if n < 3 else f"Out of clues. It was {p['name']}.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Play draft puzzle weeks in the terminal")
    parser.add_argument("drafts", nargs="+", type=Path, help="one or more draft files")
    args = parser.parse_args()

    weeks = [json.loads(path.read_text()) for path in args.drafts]
    blind = len(weeks) > 1
    if blind:
        random.shuffle(weeks)
        print(f"Blind test: {len(weeks)} sets of the same week, shuffled. "
              "Models are revealed at the end.\nFrom the second set on you'll know the answers, "
              "so judge those on quality and rate them.")

    results = []
    for label, week in zip(string.ascii_uppercase, weeks):
        name = f"Set {label}" if blind else week["model"]
        print(f"\n\n######## {name}: week of {week['start']} ########")
        for p in week["puzzles"]:
            points = play_puzzle(p)
            rating = ask("Rate this puzzle 1-5 (Enter to skip): ")
            note = ask("Note (Enter to skip): ")
            results.append({
                "set": label, "model": week["model"], "park": p["name"],
                "fame": p["difficulty"], "points": points,
                "rating": int(rating) if rating in {"1", "2", "3", "4", "5"} else None,
                "note": note,
            })

    print(f"\n\n{'=' * 60}\nResults")
    for label, week in zip(string.ascii_uppercase, weeks):
        rows = [r for r in results if r["set"] == label]
        ratings = [r["rating"] for r in rows if r["rating"]]
        avg = f"{sum(ratings) / len(ratings):.1f}" if ratings else "-"
        who = f"Set {label} = {week['model']}" if blind else week["model"]
        print(f"  {who}: {sum(r['points'] for r in rows)} points, average rating {avg}")

    out = args.drafts[0].parent / f"playtest_{datetime.now():%Y-%m-%d_%H%M}.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print(f"\nSaved your ratings to {out}")


if __name__ == "__main__":
    main()
