// AnswerCard renders a single question + answer pair in the chat.
// It receives data from App.tsx via "props" — read-only values passed down from the parent.

import { useState } from "react";
// useState — lets this component remember the "copied" flag between renders
import { toast } from "sonner";
// toast — shows a small pop-up notification (like "Copied!") without a full page reload

// TypeScript: defines exactly what props this component expects.
// The "?" means the prop is optional — the caller doesn't have to provide it.
type AnswerCardProps = {
  question: string;       // the user's question text
  answer: string;         // the AI's answer text (empty string while loading)
  loading?: boolean;      // true while we're waiting for the API response
  error?: string | null;  // set if the API call failed
};

// "export default" means other files can import this component by name.
// Props are destructured here — instead of `props.question`, we write `question` directly.
// The "= false" and "= null" are default values if the caller doesn't pass those props.
export default function AnswerCard({
  question,
  answer,
  loading = false,  // default: not loading
  error = null,     // default: no error
}: AnswerCardProps) {
  // useState(false) creates a piece of state called "copied", starting as false.
  // setCopied is the function that updates it. Calling it triggers a re-render.
  const [copied, setCopied] = useState(false);

  // async/await: clipboard operations are asynchronous (they talk to the browser API).
  // "try/catch" handles the case where copying fails (e.g., user denied clipboard permission).
  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text); // browser built-in clipboard API
      setCopied(true);                           // flip state → button changes to "Copied"
      toast.success("Copied to clipboard");      // show green pop-up notification
      setTimeout(() => setCopied(false), 2000);  // after 2 seconds, reset back to "Copy"
    } catch {
      toast.error("Copy failed"); // show red notification if clipboard was blocked
    }
  };

  // Everything inside the return() is JSX — looks like HTML but it's JavaScript.
  // React turns JSX into actual DOM elements.
  return (
    // "flex flex-col gap-4" = vertical stack with spacing between user bubble and AI bubble
    <div className="flex flex-col gap-4 py-2">

      {/* User message — right aligned pill bubble */}
      {/* "flex justify-end" pushes the bubble to the right side of the screen */}
      <div className="flex justify-end">
        {/* "max-w-[75%]" caps the bubble width so it doesn't stretch the full screen */}
        {/* "rounded-br-sm" = small radius on bottom-right only → gives the "speech bubble" look */}
        <div className="max-w-[75%] rounded-2xl rounded-br-sm bg-[#2a2d2f] px-4 py-3 text-sm leading-relaxed text-[#e3e3e3]">
          {question}  {/* just renders the text string */}
        </div>
      </div>

      {/* AI message — left aligned with an icon and label */}
      {/* "items-start" aligns the icon to the top of the message, not the center */}
      <div className="flex items-start gap-3 pr-8">
        {/* Sparkles SVG icon — acts as the AI "avatar" on the left */}
        {/* "shrink-0" prevents the icon from shrinking if the text beside it is long */}
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="mt-0.5 size-5 shrink-0 text-[#9aa0a6]">
          <path fillRule="evenodd" d="M9 4.5a.75.75 0 0 1 .721.544l.813 2.846a3.75 3.75 0 0 0 2.576 2.576l2.846.813a.75.75 0 0 1 0 1.442l-2.846.813a3.75 3.75 0 0 0-2.576 2.576l-.813 2.846a.75.75 0 0 1-1.442 0l-.813-2.846a3.75 3.75 0 0 0-2.576-2.576l-2.846-.813a.75.75 0 0 1 0-1.442l2.846-.813A3.75 3.75 0 0 0 7.466 7.89l.813-2.846A.75.75 0 0 1 9 4.5ZM18 1.5a.75.75 0 0 1 .728.568l.258 1.036c.236.94.97 1.674 1.91 1.91l1.036.258a.75.75 0 0 1 0 1.456l-1.036.258c-.94.236-1.674.97-1.91 1.91l-.258 1.036a.75.75 0 0 1-1.456 0l-.258-1.036a3.375 3.375 0 0 0-1.91-1.91l-1.036-.258a.75.75 0 0 1 0-1.456l1.036-.258a3.375 3.375 0 0 0 1.91-1.91l.258-1.036A.75.75 0 0 1 18 1.5ZM16.5 15a.75.75 0 0 1 .712.513l.394 1.183c.15.447.5.799.948.948l1.183.395a.75.75 0 0 1 0 1.422l-1.183.395c-.447.15-.799.5-.948.948l-.395 1.183a.75.75 0 0 1-1.422 0l-.395-1.183a1.5 1.5 0 0 0-.948-.948l-1.183-.395a.75.75 0 0 1 0-1.422l1.183-.395c.447-.15.799-.5.948-.948l.395-1.183A.75.75 0 0 1 16.5 15Z" clipRule="evenodd" />
        </svg>

        {/* "flex-1" makes this container take all remaining horizontal space */}
        {/* "min-w-0" prevents long words from overflowing — a flex child quirk */}
        <div className="flex-1 min-w-0">
          <p className="mb-2 text-xs font-medium text-[#9aa0a6]">CourseCraft AI</p>

          {/* Typing indicator — three bouncing dots shown while loading */}
          {/* "{loading && (...)}" is short-circuit evaluation:
              if loading is false, React skips the right side entirely (renders nothing).
              if loading is true, React renders the dots. */}
          {loading && (
            <div className="flex items-center gap-1.5 h-5">
              {/* [0, 0.15, 0.3] is an array of animation delay values (in seconds).
                  .map() turns the array into 3 <span> elements, one per delay.
                  "key={i}" is required by React to track each item in the list. */}
              {[0, 0.15, 0.3].map((delay, i) => (
                <span
                  key={i}
                  className="size-2 rounded-full bg-[#9aa0a6] animate-bounce"
                  // style= applies inline CSS. Here we stagger the bounce animation
                  // so dot 1 starts at 0s, dot 2 at 0.15s, dot 3 at 0.3s.
                  style={{ animationDelay: `${delay}s`, animationDuration: "1s" }}
                />
              ))}
            </div>
          )}

          {/* Error message — only shown if NOT loading AND there IS an error */}
          {/* "!loading && error" = both conditions must be true for this to render */}
          {!loading && error && (
            <p className="text-sm text-red-400">{error}</p>
          )}

          {/* Answer — only shown if NOT loading AND no error AND answer exists */}
          {/* All three conditions must be true. If answer is "" (empty string), it's falsy → nothing renders. */}
          {!loading && !error && answer && (
            // <> ... </> is a React Fragment — a wrapper that adds no extra DOM element.
            // We use it here because we want to return two siblings (text + button)
            // but JSX requires a single root element.
            <>
              {/* "whitespace-pre-wrap" preserves line breaks from the API response */}
              <p className="text-sm leading-relaxed text-[#e3e3e3] whitespace-pre-wrap">{answer}</p>

              {/* Copy button — clicking it calls copyToClipboard with the answer text */}
              <button
                type="button"
                onClick={() => copyToClipboard(answer)} // arrow function to pass `answer` as argument
                className="mt-2 flex items-center gap-1.5 text-xs text-[#9aa0a6] transition hover:text-[#e3e3e3]"
              >
                {/* Ternary: copied ? show "Copied" state : show "Copy" state */}
                {/* This is like an if/else inside JSX */}
                {copied ? (
                  // "Copied" state — green checkmark icon + green text
                  <>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="size-3.5 text-green-400">
                      <path fillRule="evenodd" d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" clipRule="evenodd" />
                    </svg>
                    <span className="text-green-400">Copied</span>
                  </>
                ) : (
                  // "Copy" state — clipboard icon + "Copy" text
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
