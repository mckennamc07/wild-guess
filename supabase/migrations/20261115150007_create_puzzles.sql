-- puzzles: one row per day. Clues and answers only; the post-guess
-- content lives in profile_sections.

create table puzzles (
  id                integer generated always as identity primary key,
  puzzle_date       date not null unique,          -- one puzzle per day

  -- Foreign keys: the database refuses a puzzle for a park or run that
  -- doesn't exist, and refuses to delete a park that has puzzles.
  park_id           integer not null references parks (id),
  run_id            integer not null references generation_runs (id),

  -- Copied from the park at generation time, so re-scoring a park later
  -- doesn't rewrite the history of past puzzles.
  difficulty        integer not null check (difficulty between 1 and 4),
  answer_format     answer_format not null,

  clue_1            text not null,
  clue_2            text not null,
  clue_3            text not null,

  wrong_answers     text[] not null default '{}',
  -- Lowercase forms of the right answer: full name, short name, real
  -- nicknames ("smokies"). No misspelling lists: the frontend normalizes the
  -- guess (lowercase, trim, strip "national park"/"np") and fuzzy-matches it
  -- by edit distance, accepting only if it's closer to this park than any other.
  accepted_answers  text[] not null,
  reasoning         text,                          -- Claude's note on its choices

  status            puzzle_status not null default 'approved',
  created_at        timestamptz not null default now(),

  -- Choice formats need exactly 3 wrong answers; typed formats need none.
  -- cardinality() = number of items in an array.
  constraint wrong_answers_match_format check (
    (answer_format in ('type_in', 'first_letter_count') and cardinality(wrong_answers) = 0)
    or
    (answer_format in ('choice_confusable', 'choice_easy') and cardinality(wrong_answers) = 3)
  ),

  constraint has_accepted_answers check (cardinality(accepted_answers) > 0),

  -- Accepted answers must be lowercase: the whole array, as text, must be
  -- unchanged by lower().
  constraint accepted_answers_lowercase check (
    accepted_answers::text = lower(accepted_answers::text)
  )
);

-- Postgres indexes primary keys and unique columns automatically, but NOT
-- foreign keys. This one speeds up "give me this park's past clues".
create index puzzles_park_id_idx on puzzles (park_id);
