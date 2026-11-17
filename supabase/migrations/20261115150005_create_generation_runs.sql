-- generation_runs: one row per weekly batch job.
-- Your real cost record, and where failures become visible.
--
-- Why it matters: the weekly job runs unattended in GitHub Actions, so this
-- table is how you know it ran, what it cost, and why it failed.

create table generation_runs (
  id             integer generated always as identity primary key,
  started_at     timestamptz not null default now(),
  finished_at    timestamptz,                    -- null while the run is still going
  status         run_status not null default 'running',
  error_message  text,

  -- The random seed used by select_parks.py, so any week can be reproduced
  -- exactly. (Mentioned in spec section 6, missing from the section 5 table.)
  seed           bigint not null,

  model          text,                           -- e.g. 'claude-sonnet-5-5'
  input_tokens   integer check (input_tokens >= 0),
  output_tokens  integer check (output_tokens >= 0),
  -- numeric, not float: floats can't store 0.1 exactly, which is bad for money.
  cost_usd       numeric(10, 4) check (cost_usd >= 0)
);
