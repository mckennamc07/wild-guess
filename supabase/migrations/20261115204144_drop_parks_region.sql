-- Drop parks.region: all park data now comes from the NPS API, and NPS has
-- no region field. (A weekly variety rule, if needed, can use states.)
--
-- Postgres also removes the public key's column privilege on region
-- (granted in the row_level_security migration) along with the column.
--
-- Why it matters: a later migration instead of editing the original, so
-- the history matches what was actually applied to the database.

alter table parks drop column region;
