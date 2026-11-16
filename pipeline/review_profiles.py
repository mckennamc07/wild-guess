"""Review and approve park profile sections from the terminal.

Usage (from the repo root):
    python pipeline/review_profiles.py                  # list drafts waiting for review
    python pipeline/review_profiles.py --show 29        # read one: body, review notes, sources
    python pipeline/review_profiles.py --approve 22 29  # publish these (status -> approved)
    python pipeline/review_profiles.py --unapprove 22   # take one back to draft

Approving sets status to 'approved' and stamps reviewed_at. The website
shows the newest approved row for each park and section, so approving a
new version replaces the old one on the site; older rows stay in the
table for comparison.
"""

import argparse
from datetime import datetime, timezone

from db import get_client

COLUMNS = "id, park_id, section, status, body, sources, review_notes, generated_at, reviewed_at"


def confidence_of(row: dict) -> str:
    """The section's source confidence, from its review notes."""
    for n in row["review_notes"]:
        if n["check"] == "source_confidence" and n["detail"].split(":")[0] in ("LIMITED", "THIN"):
            return n["detail"].split(":")[0].lower()
    return "strong"


def list_drafts(db, parks: dict[int, str]) -> None:
    rows = db.table("profile_sections").select(COLUMNS).eq("status", "draft").order("park_id").execute().data
    if not rows:
        print("No drafts waiting for review.")
        return
    print(f"{'id':>4}  {'park':32} {'section':15} {'confidence':10} notes")
    for r in sorted(rows, key=lambda r: (parks[r["park_id"]], r["section"])):
        print(f"{r['id']:>4}  {parks[r['park_id']][:32]:32} {r['section']:15} "
              f"{confidence_of(r):10} {len(r['review_notes'])}")
    print("\nRead one with --show ID; publish with --approve ID [ID ...].")


def show(db, parks: dict[int, str], row_id: int) -> None:
    rows = db.table("profile_sections").select(COLUMNS).eq("id", row_id).execute().data
    if not rows:
        raise SystemExit(f"No profile section with id {row_id}.")
    r = rows[0]
    print(f"#{r['id']}  {parks[r['park_id']]} — {r['section']}  [{r['status']}]\n")
    if r["review_notes"]:
        print("Review notes:")
        for n in r["review_notes"]:
            print(f"  - {n['check']}: {n['detail']}")
    else:
        print("Review notes: none, every automated check passed.")
    print(f"\n{r['body']}\n\nSources:")
    for s in r["sources"]:
        print(f"  - {s['title']} ({s.get('quality', '?')})\n    {s['url']}")


def set_status(db, ids: list[int], status: str) -> None:
    reviewed_at = datetime.now(timezone.utc).isoformat() if status == "approved" else None
    updated = db.table("profile_sections").update({"status": status, "reviewed_at": reviewed_at}) \
        .in_("id", ids).execute().data
    found = sorted(r["id"] for r in updated)
    print(f"Set {len(found)} section(s) to {status}: {found}")
    missing = sorted(set(ids) - set(found))
    if missing:
        print(f"Not found: {missing}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Review park profile sections")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--show", type=int, metavar="ID")
    action.add_argument("--approve", type=int, nargs="+", metavar="ID")
    action.add_argument("--unapprove", type=int, nargs="+", metavar="ID")
    args = parser.parse_args()

    db = get_client()
    parks = {p["id"]: p["name"] for p in db.table("parks").select("id, name").execute().data}

    if args.show is not None:
        show(db, parks, args.show)
    elif args.approve:
        set_status(db, args.approve, "approved")
    elif args.unapprove:
        set_status(db, args.unapprove, "draft")
    else:
        list_drafts(db, parks)


if __name__ == "__main__":
    main()
