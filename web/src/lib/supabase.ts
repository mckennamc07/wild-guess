import { createClient } from '@supabase/supabase-js'

// Vite exposes env vars starting with VITE_ to the browser code. That's why
// only the *publishable* key belongs here: Row Level Security decides what
// it can read. The secret key must never appear in this folder.
//
// Key decision: the client is null (not a crash) when the env vars are
// missing; api.ts then shows a clear "copy .env.example" error.
//
// Why it matters: one shared client for the whole site, and the line
// between the public key (here) and the secret key (pipeline only).
const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY

export const supabase = url && key ? createClient(url, key) : null
