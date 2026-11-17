-- Enums: columns that may only hold one of a fixed list of values.
-- Postgres rejects anything else, so a typo like 'aproved' can never be saved.
-- They're created first because the tables below use them as column types.
--
-- Why it matters: statuses decide what's public (approved vs draft), and the
-- answer formats tie fame score to how a puzzle is played. Enums make the
-- database enforce both.

-- The four answer formats, one per fame level (4 = best known = hardest).
create type answer_format as enum (
  'type_in',             -- fame 4: type the park name
  'first_letter_count',  -- fame 3: first letter + one blank per letter
  'choice_confusable',   -- fame 2: multiple choice, similar wrong answers
  'choice_easy'          -- fame 1: multiple choice, clearly different wrong answers
);

-- Puzzles auto-publish, so they start as 'approved'; you set 'rejected' to pull one.
create type puzzle_status as enum ('approved', 'rejected');

-- The three post-guess sections.
create type profile_section as enum ('fun_facts', 'formation', 'people_history');

-- Where a profile section's content came from.
create type content_provider as enum ('nps', 'claude', 'exa');

-- Profile sections wait for your review before the site shows them.
create type section_status as enum ('draft', 'approved');

-- Lifecycle of one weekly batch job.
create type run_status as enum ('running', 'succeeded', 'failed');
