-- Row Level Security (RLS)
--
-- The website uses Supabase's public key, which anyone can copy out of the
-- browser. So the database itself decides what that key may see.
--   anon          = visitors using the public key
--   authenticated = signed-in users (Phase 3)
--   service_role  = the pipeline's secret key; it bypasses RLS entirely
--
-- Once RLS is on, a table with no policies is invisible to anon. Policies
-- only ever ADD access. The website only reads, so there are no
-- insert/update/delete policies: the public key can't write anything.

alter table parks              enable row level security;
alter table puzzles            enable row level security;
alter table profile_sections   enable row level security;
alter table generation_runs    enable row level security;  -- private: no policies
alter table calibration_notes  enable row level security;  -- private: no policies


-- parks ---------------------------------------------------------------------
-- Every row is fine to show, but NOT every column. The pipeline sets
-- last_shown_date when it schedules a puzzle, so reading that column would
-- reveal this week's upcoming parks. Column privileges hide it.
-- (Supabase grants full table access by default, so revoke that first, then
-- grant back only the safe columns.)

revoke select on parks from anon, authenticated;
grant select (id, name, short_name, nps_code, states, region)
  on parks to anon, authenticated;

create policy "Anyone can read parks"
  on parks for select
  to anon, authenticated
  using (true);


-- puzzles -------------------------------------------------------------------
-- Approved puzzles dated today or earlier. Never future ones.
-- "Today" means Eastern time. Supabase's clock runs on UTC, so plain
-- current_date would roll over at 7-8 pm Eastern (v1's bug, in a new place).

create policy "Anyone can read published puzzles"
  on puzzles for select
  to anon, authenticated
  using (
    status = 'approved'
    and puzzle_date <= (now() at time zone 'America/New_York')::date
  );


-- profile_sections ----------------------------------------------------------
-- Only content you (or the pipeline, for NPS sections) have approved.

create policy "Anyone can read approved profile sections"
  on profile_sections for select
  to anon, authenticated
  using (status = 'approved');
