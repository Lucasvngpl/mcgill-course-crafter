// QueryForm is the input bar at the bottom of the screen.
// It receives two props from App.tsx: the loading state, and a function to call when the user submits.

import { useState, useRef } from "react";
// useState — tracks the current text in the textarea
// useRef  — gives us a direct handle on the real DOM textarea element

// TypeScript: defines the shape of the props this component expects.
// "onSubmit" is a function type: it takes a string and returns nothing (void).
type QueryFormProps = {
  loading: boolean;
  onSubmit: (question: string) => void; // callback — App.tsx passes handleSubmit here
};

// Props are destructured directly in the function signature.
// This component is "controlled" — React owns the textarea's value via useState.
export default function QueryForm({ loading, onSubmit }: QueryFormProps) {
  // "question" holds whatever the user has typed so far.
  // Every keystroke calls setQuestion(), which triggers a re-render with the new text.
  const [question, setQuestion] = useState("");

  // useRef creates a stable reference to the actual <textarea> DOM element.
  // Unlike useState, changing a ref doesn't trigger a re-render — it's just a pointer.
  // We need this to manually manipulate the textarea's height (CSS, not React).
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = () => {
    // .trim() removes leading/trailing whitespace — prevents submitting blank messages.
    // "if (!question.trim() || loading) return" = bail out early if text is empty or still loading.
    if (!question.trim() || loading) return;
    onSubmit(question);   // call the function App.tsx passed in (handleSubmit in App.tsx)
    setQuestion("");       // clear the input after submitting
    // Reset the textarea's height back to one line.
    // "textareaRef.current" is the actual DOM <textarea> element.
    // We use .current because refs are objects: { current: <the DOM node> }.
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"; // let the browser recalculate natural height
    }
  };

  // Called on every keystroke inside the textarea.
  // "e" is the event object — e.target is the textarea DOM element itself.
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setQuestion(e.target.value); // update React state with whatever is now in the box

    // Auto-resize trick:
    // 1. Set height to "auto" so the browser collapses it to its natural minimum.
    // 2. Read scrollHeight — the full content height even if it overflows.
    // 3. Cap it at 160px with Math.min so it doesn't grow forever.
    // This gives us a textarea that grows with content up to 5-6 lines, then scrolls.
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
  };

  return (
    // "focus-within" is a CSS pseudo-class that applies when ANY child is focused.
    // So the border lightens when the user clicks into the textarea.
    <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-[#1e1f20] px-4 py-3 transition focus-within:border-white/20">
      {/* "sr-only" = screen reader only — hidden visually but read by accessibility tools */}
      <label htmlFor="aiPrompt" className="sr-only">Ask a question</label>

      {/* Controlled textarea: value={question} means React sets what's displayed.
          onChange={handleChange} means React updates state on every keystroke.
          Together, React is the "single source of truth" for the text — this is the
          "controlled input" pattern. */}
      <textarea
        ref={textareaRef}           // connect the ref so handleSubmit can reset height
        id="aiPrompt"               // matches the label's htmlFor — links them for accessibility
        rows={1}                    // start with one visible line
        placeholder="Ask about McGill courses, prerequisites..."
        value={question}            // controlled: React drives what's shown in the box
        onChange={handleChange}     // controlled: every keystroke updates React state
        disabled={loading}          // grays out and blocks input while waiting for an answer
        className="flex-1 resize-none bg-transparent text-sm leading-relaxed text-[#e3e3e3] placeholder:text-[#5f6368] focus:outline-none disabled:opacity-50"
        style={{ maxHeight: "160px" }} // hard cap in CSS as a safety net
        onKeyDown={(e) => {
          // "Enter without Shift" submits the form.
          // "Shift+Enter" is a newline (the default browser behavior), so we let it through.
          // e.preventDefault() stops the Enter key from inserting a newline before submitting.
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
          }
        }}
      />

      {/* Send button — disabled when loading or when the textarea is empty/whitespace */}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={loading || !question.trim()} // two conditions: either blocks the button
        aria-label="Send"                       // accessibility label for screen readers
        className="flex size-8 shrink-0 items-center justify-center rounded-full bg-[#c4c7c5] transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-30"
      >
        {/* Ternary: loading ? show spinner : show send arrow */}
        {loading ? (
          /* Spinner SVG — Tailwind's animate-spin rotates it 360° continuously */
          <svg className="size-4 animate-spin text-[#131314]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        ) : (
          /* Send arrow SVG — static icon when not loading */
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="size-4 text-[#131314]">
            <path d="M2.87 2.298a.75.75 0 0 0-.812 1.021L3.39 6.624a1 1 0 0 0 .928.626H8.25a.75.75 0 0 1 0 1.5H4.318a1 1 0 0 0-.927.626l-1.333 3.305a.75.75 0 0 0 .811 1.022l11-3.498a.75.75 0 0 0 0-1.426L2.87 2.298Z" />
          </svg>
        )}
      </button>
    </div>
  );
}
