-- details: a structured version of a profile section, for the frontend.
-- Used by people_history so the site can list each nation as something to
-- tap and expand:
--   {"nations": [{"name", "connection", "present_day", "confidence", "sources"}],
--    "displacement": "...", "documentation_note": "..."}
-- Null for sections that are plain text (fun_facts, formation). `body` stays
-- the readable version of the same content.
--
-- Why it matters: it lets PeopleHistory.tsx show each nation, its sources
-- and its confidence separately, instead of one block of text.

alter table profile_sections
  add column details jsonb
  check (details is null or jsonb_typeof(details) = 'object');

-- Players need this, so the public key may read it (added to the column
-- grant from the review_notes migration; review_notes stays hidden).
grant select (details) on profile_sections to anon, authenticated;
