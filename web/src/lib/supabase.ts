import { createClient } from '@supabase/supabase-js'

// Vite exposes env vars starting with VITE_ to the browser code. That's why
// only the *publishable* key belongs here: Row Level Security decides what
// it can read. The secret key must never appear in this folder.
const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY

export const supabase = url && key ? createClient(url, key) : null
