-- calibration_notes: v1's memory, but actually read back. Each run writes
-- notes; the next run gets the most recent ones in its prompt.
--
-- Why it matters: it lets the puzzle writer learn from its own recent weeks
-- without any model training: just notes fed back into the prompt.

create table calibration_notes (
  id          integer generated always as identity primary key,
  run_id      integer not null references generation_runs (id),
  note        text not null,
  created_at  timestamptz not null default now()
);
