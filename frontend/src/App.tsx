import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Toaster } from "sonner";
import QueryForm from "./components/QueryForm";
import AnswerCard from "./components/AnswerCard";
import { askQuestion } from "./lib/api";
import { supabase } from "./lib/supabase";

type Message = {
  question: string;
  answer: string;
  error?: string | null;
};

const SUGGESTED_PROMPTS = [
  "What are the prerequisites for COMP 251?",
  "I've taken MATH 140 and 141 — what can I take next?",
  "What's the difference between COMP 202 and COMP 206?",
  "I'm a U1 CS student. What should I take this semester?",
];

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [user, setUser] = useState<any>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auth
  
  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange( // Listen for auth  changes to update user and access 
      (_event, session) => {
        setUser(session?.user ?? null);
        setAccessToken(session?.access_token ?? null);
      }
    );
    return () => subscription.unsubscribe();
  }, []);

  // Auto-scroll to newest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSignIn = async () => {
    await supabase.auth.signInWithOAuth({ provider: "google" }); // This is where we trigger Google OAuth sign-in 
  };

  const handleSignOut = async () => { // Sign the user out 
    await supabase.auth.signOut();
  };

  const handleSubmit = async (question: string) => { // When a user submits a question, we add it to the messages list with an empty answer and set loading to true. 
  // We then call the askQuestion API function from our backend with the question and access token. If we get an answer back, we update the last message with the answer. If there's an error, we update the last message with the error message. Finally, we set loading to false.
    setMessages((prev) => [...prev, { question, answer: "", error: null }]);
    setLoading(true);
    try {
      const answer = await askQuestion(question, accessToken);
      setMessages((prev) =>
        prev.map((msg, i) =>
          i === prev.length - 1 ? { ...msg, answer } : msg
        )
      );
    } catch (err) {
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


  // UI

  return (
    <div className="flex h-screen flex-col bg-[#131314] text-[#e3e3e3]">
      <Toaster position="top-center" theme="dark" />

      {/* Header */}
      <header className="flex shrink-0 items-center justify-between border-b border-white/8 px-6 py-3">
        <div className="flex items-center gap-2.5">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="size-6 text-white">
            <path fillRule="evenodd" d="M9 4.5a.75.75 0 0 1 .721.544l.813 2.846a3.75 3.75 0 0 0 2.576 2.576l2.846.813a.75.75 0 0 1 0 1.442l-2.846.813a3.75 3.75 0 0 0-2.576 2.576l-.813 2.846a.75.75 0 0 1-1.442 0l-.813-2.846a3.75 3.75 0 0 0-2.576-2.576l-2.846-.813a.75.75 0 0 1 0-1.442l2.846-.813A3.75 3.75 0 0 0 7.466 7.89l.813-2.846A.75.75 0 0 1 9 4.5ZM18 1.5a.75.75 0 0 1 .728.568l.258 1.036c.236.94.97 1.674 1.91 1.91l1.036.258a.75.75 0 0 1 0 1.456l-1.036.258c-.94.236-1.674.97-1.91 1.91l-.258 1.036a.75.75 0 0 1-1.456 0l-.258-1.036a3.375 3.375 0 0 0-1.91-1.91l-1.036-.258a.75.75 0 0 1 0-1.456l1.036-.258a3.375 3.375 0 0 0 1.91-1.91l.258-1.036A.75.75 0 0 1 18 1.5ZM16.5 15a.75.75 0 0 1 .712.513l.394 1.183c.15.447.5.799.948.948l1.183.395a.75.75 0 0 1 0 1.422l-1.183.395c-.447.15-.799.5-.948.948l-.395 1.183a.75.75 0 0 1-1.422 0l-.395-1.183a1.5 1.5 0 0 0-.948-.948l-1.183-.395a.75.75 0 0 1 0-1.422l1.183-.395c.447-.15.799-.5.948-.948l.395-1.183A.75.75 0 0 1 16.5 15Z" clipRule="evenodd" />
          </svg>
          <span className="font-semibold text-[#e3e3e3]">CourseCraft AI</span>
          <span className="hidden text-xs text-[#5f6368] sm:inline">· McGill University</span>
        </div>

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

      {/* Messages */}
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col gap-1 px-4 py-6">

          {/* Empty state */}
          <AnimatePresence>
            {messages.length === 0 && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
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
                <div className="grid w-full max-w-lg grid-cols-1 gap-2 sm:grid-cols-2">
                  {SUGGESTED_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      onClick={() => handleSubmit(prompt)}
                      className="rounded-xl border border-white/8 bg-white/4 px-4 py-3 text-left text-sm text-[#c4c7c5] transition hover:border-white/15 hover:bg-white/7"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Message list */}
          <AnimatePresence initial={false}>
            {messages.map((msg, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, ease: "easeOut" }}
              >
                <AnswerCard
                  question={msg.question}
                  answer={msg.answer}
                  loading={loading && index === messages.length - 1}
                  error={msg.error}
                />
              </motion.div>
            ))}
          </AnimatePresence>

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input */}
      <div className="shrink-0 border-t border-white/8 bg-[#131314] px-4 pb-5 pt-4">
        <div className="mx-auto max-w-3xl">
          <QueryForm loading={loading} onSubmit={handleSubmit} />
          <p className="mt-3 text-center text-xs text-[#5f6368]">
            CourseCraft may make mistakes. Always verify with the official McGill eCalendar.
          </p>
        </div>
      </div>
    </div>
  );
}
