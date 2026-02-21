import { useState, useEffect } from "react";
import QueryForm from "./components/QueryForm";
import AnswerCard from "./components/AnswerCard";
import { askQuestion } from "./lib/api";
import { supabase } from "./lib/supabase"; // Our single Supabase client (handles auth, DB, etc.)


type Message = {
  question: string;
  answer: string;
  error?: string | null;
};

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

  /*


  Authentication flow:
  - On mount, we subscribe to Supabase auth state changes (sign in, sign out, token refresh)
  - Whenever auth state changes, we update our local `user` state with the current user (or null if signed out)
  - When user clicks "Sign in", we call supabase.auth.signInWithOAuth() which redirects to Google's OAuth flow
  - After signing in, Supabase redirects back to our app with a session, which triggers the auth state change and updates `user`
  - When user clicks "Sign out", we call supabase.auth.signOut() which clears the session and triggers auth state change to set `user` back to null

  */
  // Tracks the currently signed-in Supabase user (null = not signed in)
  const [user, setUser] = useState<any>(null);
  // Store the access token so we can send it to the backend with API requests
  const [accessToken, setAccessToken] = useState<string | null>(null);

  // On mount, subscribe to auth state changes (sign in, sign out, token refresh)
  // Whenever auth state changes, update our local user state and token
  useEffect(() => {
    // onAuthStateChange returns a subscription object we need to clean up
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        // session is null when signed out, has .user and .access_token when signed in
        setUser(session?.user ?? null);
        setAccessToken(session?.access_token ?? null);
      }
    );

    // Cleanup: unsubscribe when component unmounts (prevents memory leaks)
    return () => subscription.unsubscribe();
  }, []); // Empty array = only run once on mount

  // Redirects the browser to Google's OAuth consent screen
  // Supabase handles the entire OAuth flow and redirects back with a session
  const handleSignIn = async () => {
    await supabase.auth.signInWithOAuth({ provider: "google" });
  };

  // Clears the Supabase session (removes tokens from localStorage)
  // onAuthStateChange will fire and set user back to null
  const handleSignOut = async () => {
    await supabase.auth.signOut();
  };

  const handleSubmit = async (question: string) => {
    // Add placeholder message
    setMessages((prev) => [...prev, { question, answer: "", error: null }]);
    setLoading(true);

    try {
      // Pass the access token so backend can identify the user (null for anonymous)
      console.log("[DEBUG] accessToken:", accessToken ? "present" : "null"); // Remove later
      const answer = await askQuestion(question, accessToken);
      // Update last message with answer
      setMessages((prev) =>
        prev.map((msg, i) =>
          i === prev.length - 1 ? { ...msg, answer } : msg
        )
      );
    } catch (err) {
      // Update last message with error
      setMessages((prev) =>
        prev.map((msg, i) =>
          i === prev.length - 1
            ? { ...msg, error: err instanceof Error ? err.message : "Unknown error" }
            : msg
        )
      );
    } finally {
      setLoading(false);
    }
  };


  /*
  UI Flow:
  - Header: Shows app name and sign in/out button. If signed in, also shows user email.
  - Main: Shows list of messages (question + answer). If loading, shows loading state on last message. If no messages, shows prompt to ask a question.
  - Footer: Fixed input form to ask new questions. Disabled when loading.
  */

  return (
    <div className="flex min-h-screen flex-col bg-surface text-on-surface">
      {/* Header */}
      <header className="border-b border-outline bg-surface-alt p-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-on-surface-strong">CourseCraft AI</h1>
          <p className="text-sm text-on-surface">Ask about McGill courses, prerequisites, and more</p>
        </div>
        {/* Conditional rendering: show different UI based on whether user is signed in */}
        {user ? (
          // User IS signed in — show their email and a sign-out button
          <div className="flex items-center gap-3">
            <span className="text-sm text-on-surface">{user.email}</span>
            <button
              onClick={handleSignOut}
              className="rounded bg-outline px-3 py-1 text-sm text-on-surface hover:bg-outline/80"
            >
              Sign out
            </button>
          </div>
        ) : (
          // User is NOT signed in — show sign-in button
          <button
            onClick={handleSignIn}
            className="rounded bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:bg-primary/90"
          >
            Sign in 
          </button>
        )}
      </header>

      {/* Chat messages */}
      <main className="flex-1 overflow-y-auto p-4">
        <div className="mx-auto flex max-w-3xl flex-col gap-6">
          {messages.length === 0 && (
            <p className="text-center text-on-surface/50">
              Ask a question to get started...
            </p>
          )}

          {messages.map((msg, index) => (
            <AnswerCard
              key={index}
              question={msg.question}
              answer={msg.answer}
              loading={loading && index === messages.length - 1}
              error={msg.error}
            />
          ))}
        </div>
      </main>

      {/* Input form - fixed at bottom */}
      <footer className="border-t border-outline bg-surface-alt p-4">
        <div className="mx-auto max-w-3xl">
          <QueryForm loading={loading} onSubmit={handleSubmit} />
        </div>
      </footer>
    </div>
  );
}