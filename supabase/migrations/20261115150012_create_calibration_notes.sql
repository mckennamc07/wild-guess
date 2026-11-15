-- calibration_notes: v1's memory, but actually read back. Each run writes
-- notes; the next run gets the most recent ones in its prompt.

create table calibration_notes (
  id          integer generated always as identity primary key,
  run_id      integer not null references generation_runs (id),
  note        text not null,
  created_at  timestamptz not null default now()
);
