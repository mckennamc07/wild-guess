-- photo: the park's featured photo from the NPS API, shown on the reveal.
--   {"url", "title", "alt", "caption", "credit"}
-- Stored here (filled by pipeline/seed_parks.py) so the website never needs
-- the NPS API key, which must stay out of the browser.
--
-- Why it matters: the reveal shows the park, not just its name, and the
-- photo's alt text keeps it accessible.

alter table parks
  add column photo jsonb
  check (photo is null or jsonb_typeof(photo) = 'object');

-- Public: players see it. Added to the column grant from the
-- row_level_security migration; last_shown_date etc. stay hidden.
grant select (photo) on parks to anon, authenticated;
