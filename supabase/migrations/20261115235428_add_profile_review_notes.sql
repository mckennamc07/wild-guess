-- review_notes: why a profile section needs a human look, written by the
-- enrichment pipeline's checks. e.g.
--   [{"check": "quote_not_found", "detail": "claim 3: quote missing from cited page"},
--    {"check": "low_confidence", "detail": "field nations: Exa confidence low"}]
-- An empty list means every automated check passed. Every row still starts
-- as 'draft' and needs your approval; the notes tell you where to look.

alter table profile_sections
  add column review_notes jsonb not null default '[]'
  check (jsonb_typeof(review_notes) = 'array');

-- Keep review notes internal: the public key may read every column the
-- website needs, but not this one. (Same pattern as parks.last_shown_date.)
-- Supabase grants whole-table access by default, so revoke it and grant
-- back the public columns. A future public column must be added here too.
revoke select on profile_sections from anon, authenticated;
grant select (id, park_id, section, body, sources, provider, status, generated_at, reviewed_at)
  on profile_sections to anon, authenticated;
