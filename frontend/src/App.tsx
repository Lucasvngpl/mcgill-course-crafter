// App.tsx is the "root" of the whole frontend. Every other component lives inside it.
// It owns the shared state (messages, user, loading) and passes pieces of it down to children.

import { useState, useEffect, useRef } from "react";
// useState  — lets a component remember a value between re-renders (like a variable that persists)
// useEffect — lets you run code *after* React renders the UI (subscriptions, side effects)
// useRef    — gives you a direct reference to a real DOM element (like document.getElementById but the React way)

import { motion, AnimatePresence } from "framer-motion";
// motion.div    — a regular <div> that framer-motion can animate (initial/animate/exit props)
// AnimatePresence — needed so that "exit" animations play before an element is removed from the DOM

import { Toaster } from "sonner";
// Toaster is the invisible container that actually renders toast notifications on screen.
// It needs to exist somewhere in the tree — we put it at the top level here.

import QueryForm from "./components/QueryForm";   // The input bar at the bottom
import AnswerCard from "./components/AnswerCard"; // Each question + answer pair in the chat
import { askQuestion } from "./lib/api";          // Function that calls our FastAPI backend
import { supabase } from "./lib/supabase";        // Our single Supabase client (auth + DB)


// TypeScript: defines the shape of one message object.
// The "?" means error is optional — not every message will have one.
type Message = {
  question: string;
  answer: string;
  error?: string | null;
};

// These live outside the component because they never change.
// Putting constants outside avoids re-creating them on every render.
const SUGGESTED_PROMPTS = [
  "What are the prerequisites for COMP 251?",
  "I've taken MATH 140 and 141 — what can I take next?",
  "What's the difference between COMP 202 and COMP 206?",
  "I'm a U1 CS student. What should I take this semester?",
];

export default function App() {
  // useState returns [currentValue, setterFunction].
  // Calling the setter triggers a re-render with the new value.

  const [messages, setMessages] = useState<Message[]>([]); // all chat messages so far
  const [loading, setLoading] = useState(false);            // true while waiting for the API
  const [user, setUser] = useState<any>(null);              // the signed-in Supabase user, or null
  const [accessToken, setAccessToken] = useState<string | null>(null); // JWT sent to the backend

  // useRef gives us a stable reference to a DOM node.
  // We use it to scroll the page — we point it at an invisible <div> at the bottom of the chat.
  const messagesEndRef = useRef<HTMLDivElement>(null);


  useEffect(() => {
    // Tell Supabase: "whenever the user signs in or out, call this function"
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        // session is null when signed out, or has .user and .access_token when signed in
        setUser(session?.user ?? null);              // ?? null means "if undefined, use null"
        setAccessToken(session?.access_token ?? null);
      }
    );

    // Return a cleanup function — React calls this when the component unmounts.
    
    return () => subscription.unsubscribe();
  }, []); // This is where we trigger Google OAuth sign-in


  // --- EFFECT: Auto-scroll ---
  // [messages, loading] means "re-run every time messages or loading changes".
  useEffect(() => {
    // .current is the actual DOM element the ref points to.
    // ?. means "only call scrollIntoView if the element exists" (safe navigation).
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);


  // --- HANDLERS ---
  // async/await: these functions call the network and need to wait for a response.

  const handleSignIn = async () => {
    // Redirects the browser to Google's OAuth screen.
    // Supabase handles the entire flow and redirects back with a session.
    await supabase.auth.signInWithOAuth({ provider: "google" });
  };

  const handleSignOut = async () => {
    // Clears the session from localStorage. The auth listener above will fire
    // and set user back to null, which re-renders the header to show "Sign in".
    await supabase.auth.signOut();
  };

  const handleSubmit = async (question: string) => {
    // Step 1: immediately add the user's question to the list with an empty answer.
    // This makes the UI feel instant — the bubble appears right away.
    // prev is the previous messages array; we spread it (...prev) and add a new item.
    setMessages((prev) => [...prev, { question, answer: "", error: null }]);
    setLoading(true); // show the typing dots

    try {
      // Step 2: call our backend. This is async — we "await" the response.
      // accessToken is sent so the backend can identify this user.
      const answer = await askQuestion(question, accessToken);

      // Step 3: update ONLY the last message with the real answer.
      // .map() creates a new array — we never mutate state directly in React.
      // For every message, if it's the last one (i === prev.length - 1), replace it; otherwise keep it.
      setMessages((prev) =>
        prev.map((msg, i) =>
          i === prev.length - 1 ? { ...msg, answer } : msg
          // { ...msg, answer } = "copy all fields of msg, but override answer with the new value"
        )
      );
    } catch (err) {
      // Same pattern, but we write the error into the last message instead of the answer
      setMessages((prev) =>
        prev.map((msg, i) =>
          i === prev.length - 1
            ? { ...msg, error: err instanceof Error ? err.message : "Unknown error" }
            : msg
        )
      );
    } finally {
      // finally runs whether the try succeeded or the catch caught an error.
      // Always hide the loading indicator when done.
      setLoading(false);
    }
  };


  // --- UI ---
  // Everything below is JSX — looks like HTML but it's actually JavaScript.
  // React turns this into real DOM elements.

  return (
    // h-screen = full viewport height. flex flex-col = header/main/footer stacked vertically.
    <div className="flex h-screen flex-col bg-[#131314] text-[#e3e3e3]">

      {/* Toaster renders toast notifications (like "Copied!"). Invisible until triggered. */}
      <Toaster position="top-center" theme="dark" />

      {/* Header — shrink-0 prevents it from shrinking when the page is short */}
      <header className="flex shrink-0 items-center justify-between border-b border-white/8 px-6 py-3">
        <div className="flex items-center gap-2.5">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="size-6 text-white">
            <path fillRule="evenodd" d="M9 4.5a.75.75 0 0 1 .721.544l.813 2.846a3.75 3.75 0 0 0 2.576 2.576l2.846.813a.75.75 0 0 1 0 1.442l-2.846.813a3.75 3.75 0 0 0-2.576 2.576l-.813 2.846a.75.75 0 0 1-1.442 0l-.813-2.846a3.75 3.75 0 0 0-2.576-2.576l-2.846-.813a.75.75 0 0 1 0-1.442l2.846-.813A3.75 3.75 0 0 0 7.466 7.89l.813-2.846A.75.75 0 0 1 9 4.5ZM18 1.5a.75.75 0 0 1 .728.568l.258 1.036c.236.94.97 1.674 1.91 1.91l1.036.258a.75.75 0 0 1 0 1.456l-1.036.258c-.94.236-1.674.97-1.91 1.91l-.258 1.036a.75.75 0 0 1-1.456 0l-.258-1.036a3.375 3.375 0 0 0-1.91-1.91l-1.036-.258a.75.75 0 0 1 0-1.456l1.036-.258a3.375 3.375 0 0 0 1.91-1.91l.258-1.036A.75.75 0 0 1 18 1.5ZM16.5 15a.75.75 0 0 1 .712.513l.394 1.183c.15.447.5.799.948.948l1.183.395a.75.75 0 0 1 0 1.422l-1.183.395c-.447.15-.799.5-.948.948l-.395 1.183a.75.75 0 0 1-1.422 0l-.395-1.183a1.5 1.5 0 0 0-.948-.948l-1.183-.395a.75.75 0 0 1 0-1.422l1.183-.395c.447-.15.799-.5.948-.948l.395-1.183A.75.75 0 0 1 16.5 15Z" clipRule="evenodd" />
          </svg>
          <span className="font-semibold text-[#e3e3e3]">CourseCraft AI</span>
          <span className="hidden text-xs text-[#5f6368] sm:inline">· McGill University</span>
        </div>

        {/* Conditional rendering: user ? (signed-in UI) : (sign-in button)
            React evaluates this expression and renders the right branch */}
        {user ? (
          <div className="flex items-center gap-3">
            <span className="hidden text-xs text-[#9aa0a6] sm:inline">{user.email}</span>
            <button
              onClick={handleSignOut}
              className="rounded-full border border-white/10 px-3 py-1 text-xs text-[#9aa0a6] transition hover:bg-white/5"
            >
              Sign out
            </button>
          </div>
        ) : (
          <button
            onClick={handleSignIn}
            className="rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs font-medium text-white transition hover:bg-white/10"
          >
            Sign in
          </button>
        )}
      </header>

      {/* Main scrollable area — flex-1 means "take all remaining vertical space" */}
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col gap-1 px-4 py-6">

          {/* Empty state: only shown when there are no messages yet */}
          {/* AnimatePresence watches its children and plays "exit" before removing them */}
          <AnimatePresence>
            {messages.length === 0 && (
              // motion.div is a regular div that framer-motion can animate
              // initial = starting state, animate = target state, exit = state when removed
              <motion.div
                initial={{ opacity: 0, y: 12 }}   // starts invisible, 12px below position
                animate={{ opacity: 1, y: 0 }}    // animates to fully visible, normal position
                exit={{ opacity: 0, y: -8 }}      // when removed: fades out and drifts up
                transition={{ duration: 0.4 }}
                className="flex flex-col items-center gap-6 py-16 text-center"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="size-14 text-[#9aa0a6]">
                  <path fillRule="evenodd" d="M9 4.5a.75.75 0 0 1 .721.544l.813 2.846a3.75 3.75 0 0 0 2.576 2.576l2.846.813a.75.75 0 0 1 0 1.442l-2.846.813a3.75 3.75 0 0 0-2.576 2.576l-.813 2.846a.75.75 0 0 1-1.442 0l-.813-2.846a3.75 3.75 0 0 0-2.576-2.576l-2.846-.813a.75.75 0 0 1 0-1.442l2.846-.813A3.75 3.75 0 0 0 7.466 7.89l.813-2.846A.75.75 0 0 1 9 4.5ZM18 1.5a.75.75 0 0 1 .728.568l.258 1.036c.236.94.97 1.674 1.91 1.91l1.036.258a.75.75 0 0 1 0 1.456l-1.036.258c-.94.236-1.674.97-1.91 1.91l-.258 1.036a.75.75 0 0 1-1.456 0l-.258-1.036a3.375 3.375 0 0 0-1.91-1.91l-1.036-.258a.75.75 0 0 1 0-1.456l1.036-.258a3.375 3.375 0 0 0 1.91-1.91l.258-1.036A.75.75 0 0 1 18 1.5ZM16.5 15a.75.75 0 0 1 .712.513l.394 1.183c.15.447.5.799.948.948l1.183.395a.75.75 0 0 1 0 1.422l-1.183.395c-.447.15-.799.5-.948.948l-.395 1.183a.75.75 0 0 1-1.422 0l-.395-1.183a1.5 1.5 0 0 0-.948-.948l-1.183-.395a.75.75 0 0 1 0-1.422l1.183-.395c.447-.15.799-.5.948-.948l.395-1.183A.75.75 0 0 1 16.5 15Z" clipRule="evenodd" />
                </svg>
                <div>
                  <h2 className="text-2xl font-semibold text-[#e3e3e3]">What can I help with?</h2>
                  <p className="mt-1 text-sm text-[#9aa0a6]">
                    Ask about McGill courses, prerequisites, and planning
                  </p>
                </div>
                {/* .map() turns an array into JSX — one button per prompt */}
                <div className="grid w-full max-w-lg grid-cols-1 gap-2 sm:grid-cols-2">
                  {SUGGESTED_PROMPTS.map((prompt) => (
                    // key= is required by React when rendering lists.
                    // It helps React identify which item changed/moved/was removed.
                    <button
                      key={prompt}
                      onClick={() => handleSubmit(prompt)} // clicking a prompt submits it directly
                      className="rounded-xl border border-white/8 bg-white/4 px-4 py-3 text-left text-sm text-[#c4c7c5] transition hover:border-white/15 hover:bg-white/7"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Message list — renders one AnswerCard per message */}
          {/* initial={false} means: don't animate messages that are already there on first render */}
          <AnimatePresence initial={false}>
            {messages.map((msg, index) => (
              // Each new message slides up and fades in
              <motion.div
                key={index} // key tells React "this is item #index" for efficient updates
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, ease: "easeOut" }}
              >
                {/* Pass each message's data down to AnswerCard as "props" */}
                <AnswerCard
                  question={msg.question}
                  answer={msg.answer}
                  // Only the LAST card shows the loading dots (while we wait for the answer)
                  loading={loading && index === messages.length - 1}
                  error={msg.error}
                />
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Invisible anchor div — the auto-scroll useEffect targets this */}
          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input area — shrink-0 keeps it from shrinking, always visible at the bottom */}
      <div className="shrink-0 border-t border-white/8 bg-[#131314] px-4 pb-5 pt-4">
        <div className="mx-auto max-w-3xl">
          {/* Pass loading state and handleSubmit down to QueryForm as props */}
          <QueryForm loading={loading} onSubmit={handleSubmit} />
          <p className="mt-3 text-center text-xs text-[#5f6368]">
            CourseCraft may make mistakes. Always verify with the official McGill eCalendar.
          </p>
        </div>
      </div>
    </div>
  );
}
