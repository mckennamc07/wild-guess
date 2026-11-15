"""Validation rules for Claude's puzzle drafts.

Claude is asked to follow these rules and to check its own work, but code
checks again before anything is saved. Each function returns a list of
problems in plain English (empty = passed), which can be sent back to
Claude on the retry.
"""

import re
import unicodedata

MAX_CLUE_WORDS = 25
TYPED_FORMATS = {"type_in", "first_letter_count"}
CHOICE_FORMATS = {"choice_confusable", "choice_easy"}

# Words too common to count as overlap between new and past clues.
STOPWORDS = set("""
a an and are as at be by for from has have in into is it its of on or that
the their this to was where which while with you your
""".split())


def normalize(text: str) -> str:
    """Lowercase and strip accents: 'Hawaiʻi' -> 'hawaii', "Zion's" -> 'zion s'.

    The ʻokina is part of a Hawaiian word, so it's removed; an apostrophe
    becomes a space so "Zion's" still contains the whole word "zion".
    """
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("ʻ", "")
    text = re.sub(r"['’‘`]", " ", text)
    return text.lower()


def contains_phrase(text: str, phrase: str) -> bool:
    """Whole-word, case- and accent-insensitive: 'Zion' matches 'zion's' but
    'Arches' doesn't match 'Archers'."""
    pattern = r"\b" + re.escape(normalize(phrase)) + r"\b"
    return re.search(pattern, normalize(text)) is not None


def content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", normalize(text)) if w not in STOPWORDS}


def overlap(a: str, b: str) -> float:
    """Share of distinct content words the two texts have in common (0-1)."""
    wa, wb = content_words(a), content_words(b)
    return len(wa & wb) / len(wa | wb) if wa | wb else 0.0


def check_puzzle(puzzle: dict, park: dict, park_names: set[str],
                 past_clues: list[str], max_overlap: float = 0.5) -> list[str]:
    """Problems with one puzzle.

    puzzle: the draft (clue_1..3, wrong_answers, accepted_answers)
    park: name, short_name, states, banned_words, answer_format
    park_names: every national park's full name
    past_clues: this park's clue 1s and 2s from earlier puzzles
    """
    problems = []
    who = park["short_name"]
    clues = {n: puzzle[f"clue_{n}"] for n in (1, 2, 3)}

    for n, clue in clues.items():
        if not clue.strip():
            problems.append(f"{who}: clue {n} is empty")
        words = len(clue.split())
        if words > MAX_CLUE_WORDS:
            problems.append(f"{who}: clue {n} is {words} words (max {MAX_CLUE_WORDS})")
        for giveaway in (park["name"], park["short_name"], *park["states"]):
            if contains_phrase(clue, giveaway):
                problems.append(f"{who}: clue {n} names the park or its state ('{giveaway}')")

    for n in (1, 2):
        for word in park["banned_words"]:
            if contains_phrase(clues[n], word):
                problems.append(f"{who}: clue {n} uses banned word '{word}'")
        for past in past_clues:
            if overlap(clues[n], past) > max_overlap:
                problems.append(f"{who}: clue {n} repeats a past clue too closely: '{past}'")

    wrong = puzzle["wrong_answers"]
    fmt = park["answer_format"]
    if fmt in TYPED_FORMATS and wrong:
        problems.append(f"{who}: {fmt} puzzles take no wrong answers, got {len(wrong)}")
    if fmt in CHOICE_FORMATS:
        if len(wrong) != 3:
            problems.append(f"{who}: needs exactly 3 wrong answers, got {len(wrong)}")
        if len(set(wrong)) != len(wrong):
            problems.append(f"{who}: wrong answers contain a duplicate")
        for w in wrong:
            if w == park["name"]:
                problems.append(f"{who}: the correct answer is listed as a wrong answer")
            elif w not in park_names:
                problems.append(f"{who}: wrong answer '{w}' isn't an exact national park name from the list")

    accepted = puzzle["accepted_answers"]
    if not accepted:
        problems.append(f"{who}: no accepted answers")
    if any(a != a.lower() for a in accepted):
        problems.append(f"{who}: accepted answers must be lowercase")
    if park["short_name"].lower() not in accepted:
        problems.append(f"{who}: accepted answers must include the short name '{park['short_name'].lower()}'")

    return problems


def check_week(puzzles: list[dict], expected_codes: list[str]) -> list[str]:
    """Problems across the whole week."""
    problems = []
    codes = [p["nps_code"] for p in puzzles]
    if sorted(codes) != sorted(expected_codes):
        problems.append(f"expected one puzzle for each of {sorted(expected_codes)}, got {sorted(codes)}")

    seen: dict[str, str] = {}
    for p in puzzles:
        for w in p["wrong_answers"]:
            if w in seen and seen[w] != p["nps_code"]:
                problems.append(f"'{w}' is a wrong answer in more than one puzzle this week")
            seen[w] = p["nps_code"]
    return problems
