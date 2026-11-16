"""Export local demo data for the website's dev-only demo mode.

Usage (from the repo root):
    python pipeline/export_demo_fixtures.py

Writes web/src/demo/fixtures.json with: every park's public columns, the
draft puzzle week from drafts/, and the current *draft* profile sections.
The file is git-ignored: draft history hasn't been reviewed, and the repo
is public. It's only loaded by `npm run dev` with ?demo=YYYY-MM-DD, never
by the production build.
"""

import json
from pathlib import Path

from db import get_client

ROOT = Path(__file__).parent.parent
WEEK = ROOT / "drafts" / "2026-11-16_claude-sonnet-5-5_seed2026.json"
OUT = ROOT / "web" / "src" / "demo" / "fixtures.json"


def main() -> None:
    db = get_client()
    parks = db.table("parks").select("id, name, short_name, nps_code, states, photo").order("name").execute().data
    by_name = {p["name"]: p for p in parks}

    week = json.loads(WEEK.read_text())
    puzzles = [{
        "id": i + 1,
        "puzzle_date": p["puzzle_date"],
        "park_id": by_name[p["name"]]["id"],
        "difficulty": p["difficulty"],
        "answer_format": p["answer_format"],
        "clue_1": p["clue_1"], "clue_2": p["clue_2"], "clue_3": p["clue_3"],
        "wrong_answers": p["wrong_answers"],
        "accepted_answers": p["accepted_answers"],
    } for i, p in enumerate(week["puzzles"])]

    profiles = db.table("profile_sections") \
        .select("id, park_id, section, body, sources, details, generated_at") \
        .order("generated_at", desc=True).execute().data

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"parks": parks, "puzzles": puzzles, "profiles": profiles},
                              indent=1, ensure_ascii=False))
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(parks)} parks, {len(puzzles)} puzzles, {len(profiles)} profile sections")


if __name__ == "__main__":
    main()
