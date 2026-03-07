// AnswerCard renders a single question + answer pair in the chat.
// It receives data from App.tsx via "props" — read-only values passed down from the parent.

import { useState, useEffect } from "react";
// useState  — lets this component remember local state (copied flag, expanded thinking)
// useEffect — runs side effects after render (cycling status text while loading)

import { toast } from "sonner";
// toast — shows a small pop-up notification (like "Copied!") without a full page reload

import ReactMarkdown from "react-markdown";
// ReactMarkdown converts markdown syntax (**, -, #) into real HTML elements.
// Without this, **bold** would show as literal asterisks in a plain <p> tag.

import type { Source } from "../lib/api";
// Source is the union type for course and program sources returned by the backend

// TypeScript: defines exactly what props this component expects.
type AnswerCardProps = {
  question: string;       // the user's question text
  answer: string;         // the AI's answer text (empty string while loading)
  sources: Source[];      // courses and programs the backend retrieved to answer the question
  loading?: boolean;      // true while we're waiting for the API response
  error?: string | null;  // set if the API call failed
};

// Status messages that cycle while the backend is thinking.
// They rotate every 1.5 seconds to feel alive without being distracting.
const LOADING_STATUSES = [
  "Retrieving courses...",
  "Analyzing requirements...",
  "Viewing program data...",
  "Checking prerequisites...",
];

// ThinkingHeader shows either:
//   - a cycling status line while loading (replaces bouncing dots)
//   - a collapsible "Thinking (N sources)" block once the answer arrives (if 3+ sources)
function ThinkingHeader({ loading, sources }: { loading: boolean; sources: Source[] }) {
  const [statusIdx, setStatusIdx] = useState(0);
  const [expanded, setExpanded] = useState(false);

  // Cycle through LOADING_STATUSES every 1.5s while loading.
  // The cleanup function (return) clears the interval when loading ends or the component unmounts.
  useEffect(() => {
    if (!loading) return;
    const t = setInterval(
      () => setStatusIdx((i) => (i + 1) % LOADING_STATUSES.length),
      4500
    );
    return () => clearInterval(t);
  }, [loading]);

  // While loading: show the animated status line in place of the bouncing dots
  if (loading) {
    return (
      <p className="mb-3 text-xs text-[#6b7280] animate-pulse">
        {LOADING_STATUSES[statusIdx]}
      </p>
    );
  }

  // After loading: only show if there are 3+ sources (simple answers stay clean)
  if (sources.length < 3) return null;

  // Separate programs and courses for grouped display
  const programs = sources.filter((s) => s.type === "program");
  const courses = sources.filter((s) => s.type === "course");

  return (
    <div className="mb-3 rounded-lg border border-white/8 bg-white/3 text-xs">
      {/* Clickable header row — toggles the expanded list */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-1.5 px-3 py-2 text-left text-[#6b7280] transition hover:text-[#9aa0a6]"
      >
        {/* Chevron rotates when expanded */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          fill="currentColor"
          className={`size-3 shrink-0 transition-transform ${expanded ? "rotate-90" : ""}`}
        >
          <path
            fillRule="evenodd"
            d="M6.22 4.22a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06l-3.25 3.25a.75.75 0 0 1-1.06-1.06L9.19 8 6.22 5.03a.75.75 0 0 1 0-1.06Z"
            clipRule="evenodd"
          />
        </svg>
        Thinking&nbsp;
        <span className="text-[#4b5563]">({sources.length} sources)</span>
      </button>

      {/* Expanded source list — programs first, then courses */}
      {expanded && (
        <div className="border-t border-white/8 px-3 pb-3 pt-2 space-y-3">
          {programs.length > 0 && (
            <div>
              <p className="mb-1 text-[10px] uppercase tracking-wider text-[#4b5563]">Programs</p>
              <ul className="space-y-0.5">
                {programs.map((s, i) =>
                  s.type === "program" ? (
                    <li key={i} className="text-[#9aa0a6]">
                      {s.name}
                      {s.faculty ? <span className="text-[#4b5563]"> — {s.faculty}</span> : null}
                    </li>
                  ) : null
                )}
              </ul>
            </div>
          )}

          {courses.length > 0 && (
            <div>
              <p className="mb-1 text-[10px] uppercase tracking-wider text-[#4b5563]">Courses</p>
              <ul className="space-y-0.5">
                {courses.map((s, i) =>
                  s.type === "course" ? (
                    <li key={i} className="font-mono text-[#9aa0a6]">
                      {s.id}
                      {s.title ? <span className="font-sans text-[#4b5563]"> ({s.title})</span> : null}
                    </li>
                  ) : null
                )}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// "export default" means other files can import this component by name.
export default function AnswerCard({
  question,
  answer,
  sources,
  loading = false,
  error = null,
}: AnswerCardProps) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success("Copied to clipboard");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Copy failed");
    }
  };

  return (
    <div className="flex flex-col gap-4 py-2">

      {/* User message — right aligned pill bubble */}
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-2xl rounded-br-sm bg-[#2a2d2f] px-4 py-3 text-sm leading-relaxed text-[#e3e3e3]">
          {question}
        </div>
      </div>

      {/* AI message — left aligned with an icon and label */}
      <div className="flex items-start gap-3 pr-8">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="mt-0.5 size-5 shrink-0 text-[#9aa0a6]">
          <path fillRule="evenodd" d="M9 4.5a.75.75 0 0 1 .721.544l.813 2.846a3.75 3.75 0 0 0 2.576 2.576l2.846.813a.75.75 0 0 1 0 1.442l-2.846.813a3.75 3.75 0 0 0-2.576 2.576l-.813 2.846a.75.75 0 0 1-1.442 0l-.813-2.846a3.75 3.75 0 0 0-2.576-2.576l-2.846-.813a.75.75 0 0 1 0-1.442l2.846-.813A3.75 3.75 0 0 0 7.466 7.89l.813-2.846A.75.75 0 0 1 9 4.5ZM18 1.5a.75.75 0 0 1 .728.568l.258 1.036c.236.94.97 1.674 1.91 1.91l1.036.258a.75.75 0 0 1 0 1.456l-1.036.258c-.94.236-1.674.97-1.91 1.91l-.258 1.036a.75.75 0 0 1-1.456 0l-.258-1.036a3.375 3.375 0 0 0-1.91-1.91l-1.036-.258a.75.75 0 0 1 0-1.456l1.036-.258a3.375 3.375 0 0 0 1.91-1.91l.258-1.036A.75.75 0 0 1 18 1.5ZM16.5 15a.75.75 0 0 1 .712.513l.394 1.183c.15.447.5.799.948.948l1.183.395a.75.75 0 0 1 0 1.422l-1.183.395c-.447.15-.799.5-.948.948l-.395 1.183a.75.75 0 0 1-1.422 0l-.395-1.183a1.5 1.5 0 0 0-.948-.948l-1.183-.395a.75.75 0 0 1 0-1.422l1.183-.395c.447-.15.799-.5.948-.948l.395-1.183A.75.75 0 0 1 16.5 15Z" clipRule="evenodd" />
        </svg>

        <div className="flex-1 min-w-0">
          <p className="mb-2 text-xs font-medium text-[#9aa0a6]">CourseCraft AI</p>

          {/* ThinkingHeader: shows cycling status while loading, collapsible sources after */}
          <ThinkingHeader loading={loading} sources={sources} />

          {/* Error message */}
          {!loading && error && (
            <p className="text-sm text-red-400">{error}</p>
          )}

          {/* Answer + copy button */}
          {!loading && !error && answer && (
            <>
              <div className="prose prose-sm prose-invert max-w-none text-[#e3e3e3]
                             [&_p]:leading-relaxed [&_p]:mb-2 [&_p:last-child]:mb-0
                             [&_ul]:my-1 [&_ul]:pl-4 [&_li]:my-0.5
                             [&_strong]:text-[#e3e3e3] [&_strong]:font-semibold">
                <ReactMarkdown>{answer}</ReactMarkdown>
              </div>
              <button
                type="button"
                onClick={() => copyToClipboard(answer)}
                className="mt-2 flex items-center gap-1.5 text-xs text-[#9aa0a6] transition hover:text-[#e3e3e3]"
              >
                {copied ? (
                  <>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="size-3.5 text-green-400">
                      <path fillRule="evenodd" d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" clipRule="evenodd" />
                    </svg>
                    <span className="text-green-400">Copied</span>
                  </>
                ) : (
                  <>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="size-3.5">
                      <path d="M3.5 3.5A1.5 1.5 0 0 1 5 2h4.879a1.5 1.5 0 0 1 1.06.44l2.122 2.12A1.5 1.5 0 0 1 13.5 5.62V11.5a1.5 1.5 0 0 1-1.5 1.5h-1v-3.379a3 3 0 0 0-.879-2.121L7.5 4.879A3 3 0 0 0 5.379 4H3.5v-.5Z" />
                      <path d="M2.5 5A1.5 1.5 0 0 0 1 6.5v7A1.5 1.5 0 0 0 2.5 15h7A1.5 1.5 0 0 0 11 13.5v-3.879a1.5 1.5 0 0 0-.44-1.06L8.44 6.439A1.5 1.5 0 0 0 7.378 6H2.5Z" />
                    </svg>
                    Copy
                  </>
                )}
              </button>
            </>
          )}
        </div>
      </div>

    </div>
  );
}
