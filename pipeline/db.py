"""Supabase connection for the pipeline.

Uses the service role key, which bypasses Row Level Security. It must only
ever run locally or in GitHub Actions, never in the website.

Key decisions:
- One shared get_client() so every script connects the same way and the
  secret key is read in exactly one place.
- Keys come from environment variables (.env locally, GitHub Secrets in
  Actions), never from code. Errors name a missing variable, never its value.

Why it matters: every pipeline script that reads or writes the database
goes through here, and it keeps the most powerful key in the project
contained to the pipeline.
"""

import os

from dotenv import load_dotenv
from supabase import Client, create_client

# Reads .env into environment variables. In GitHub Actions there's no .env
# file; the variables come from GitHub Secrets instead, and this does nothing.
load_dotenv()


def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        # Name the missing variable, but never print its value.
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set (see .env.example)")
    return create_client(url, key)
