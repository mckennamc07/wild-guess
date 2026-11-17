-- profile_sections: the post-guess content. One row per park, per section,
-- per version. New content (e.g. from Exa) is a new row beside the old one;
-- the site shows the newest approved row for each section.
--
-- Why it matters: keeping every version (instead of overwriting) means
-- research can be redone and compared, and nothing is shown until approved.

create table profile_sections (
  id            integer generated always as identity primary key,
  park_id       integer not null references parks (id),
  section       profile_section not null,
  body          text not null,                   -- markdown

  -- jsonb = JSON stored in a binary form Postgres can search.
  -- Expected shape: [{"title": "...", "url": "..."}, ...]
  sources       jsonb not null default '[]'
                check (jsonb_typeof(sources) = 'array'),

  provider      content_provider not null,
  status        section_status not null default 'draft',
  generated_at  timestamptz not null default now(),
  reviewed_at   timestamptz
);

-- Matches the site's lookup: for a park and section, newest first.
create index profile_sections_lookup_idx
  on profile_sections (park_id, section, generated_at desc);
