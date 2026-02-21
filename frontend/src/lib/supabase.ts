import { createClient } from '@supabase/supabase-js'

// These come from frontend/.env (VITE_ prefix makes them available in browser)
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

// This is the single Supabase client your entire app will use
// It handles auth, database queries, and real-time subscriptions
export const supabase = createClient(supabaseUrl, supabaseAnonKey)
