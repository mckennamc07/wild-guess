# Wild Guess

A daily U.S. national park guessing game. Each day players get three clues
about one of the 63 national parks, guess it, then learn about the park:
fun facts, how it formed, and the Indigenous nations and other communities
who lived there before it became a park.

This is a portfolio and learning project. The repo is public.

## How I want to work (important)

I'm learning as I build. By default:
1. Explain what we're about to build, why, and the concept behind it.
2. If I ask to let me write the code myself first.  Review what I wrote: point out bugs, explain better patterns, answer questions.
3. If I ask you to do it, complete it with an explanation of why you did what you did and allow me to ask questions.

Use plan mode for anything bigger than one file. Explain every new library,
command, and error message instead of just fixing it.

## How the system works

- **Weekly batch (GitHub Actions, Thursdays):** code picks the next 7 parks
  (14-day no-repeat rule, balanced difficulty mix, weighted random draw),
  then one Claude call writes all 7 puzzles as structured JSON. Code
  validates them and saves them to Supabase. Puzzles auto-publish unless rejected.
- **Park profiles:** fun facts and geology from the NPS API; Indigenous and
  displacement history researched with Exa, always reviewed by me before
  publishing. Never write history from model memory.
- **Website:** React + Vite on Vercel. Reads approved rows from Supabase. Never calls an AI.

## Where things live

- `pipeline/`: Python scripts (park selection, puzzle generation, NPS, Exa, database helpers)
- `web/`: the React + Vite frontend
- `supabase/migrations/`: SQL for every table, in order
- `.github/workflows/`: the weekly schedule
- The full plan: "Wild Guess v2 — Plan & Technical Spec" (Claude Doc)

## Key decisions

- Difficulty comes only from fame score (1–4): well known = type the answer,
  medium = first letter + letter count, lesser known = confusable multiple
  choice, least known = easy multiple choice.
- Clues: clue 1 atmospheric but plain (not poetic), clue 2 a specific
  feature, clue 3 always easy. Never name the park, state, or a banned word.
  Returning parks always get fresh clues.
- Writing model: Sonnet (to be confirmed by a model test).

## Rules

- Never commit `.env` or print, log, or paste any key.
- The Supabase secret key is for the pipeline only, never the website.
- Keep commits small, with clear messages.
- Ask before deleting files or changing the database structure.