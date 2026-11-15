-- parks: one row per national park (63). Rarely changes after setup.

create table parks (
  -- "generated always as identity" = Postgres hands out 1, 2, 3... automatically.
  id               integer generated always as identity primary key,
  name             text not null unique,          -- "Acadia National Park"
  short_name       text not null,                 -- "Acadia"
  nps_code         text not null unique,          -- "acad", for the NPS API
  -- An array because a park can span several states (Yellowstone: WY, MT, ID).
  -- Store full names ("Wyoming"), since that's what a clue would leak.
  states           text[] not null,
  region           text not null,                 -- lets code avoid 3 Southwest parks in a week

  -- Nullable on purpose: seed_parks.py loads the parks first, and the
  -- one-time fame scoring fills these in afterwards.
  fame_score       integer check (fame_score between 1 and 4),
  fame_reasoning   text,

  last_shown_date  date,                          -- drives the 14-day no-repeat rule
  times_shown      integer not null default 0 check (times_shown >= 0),
  banned_words     text[] not null default '{}',  -- landmark names clues 1-2 must avoid

  created_at       timestamptz not null default now()
);
