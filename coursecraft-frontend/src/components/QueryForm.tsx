// src/components/QueryForm.tsx
import { useState } from "react";

type QueryFormProps = {
  loading: boolean;
  onSubmit: (question: string) => void;
};

export default function QueryForm({ loading, onSubmit }: QueryFormProps) {
  const [question, setQuestion] = useState("");

  const handleSubmit = () => {
    if (!question.trim()) return;
    onSubmit(question);
  };

  return (
    <div className="w-full">
      {/* Container: relative so icon/button can be absolutely positioned */}
      <div className="relative w-full">
        {/* Screen-reader-only label for accessibility */}
        <label htmlFor="aiPrompt" className="sr-only">
          AI prompt
        </label>

        {/* Left icon (Sparkles) */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          aria-hidden="true"
          className="absolute left-3 top-1/2 size-4 -translate-y-1/2 fill-primary"
        >
          <path
            fillRule="evenodd"
            d="M5 4a.75.75 0 0 1 .738.616l.252 1.388A1.25 1.25 0 0 0 6.996 7.01l1.388.252a.75.75 0 0 1 0 1.476l-1.388.252A1.25 1.25 0 0 0 5.99 9.996l-.252 1.388a.75.75 0 0 1-1.476 0L4.01 9.996A1.25 1.25 0 0 0 3.004 8.99l-1.388-.252a.75.75 0 0 1 0-1.476l1.388-.252A1.25 1.25 0 0 0 4.01 6.004l.252-1.388A.75.75 0 0 1 5 4ZM12 1a.75.75 0 0 1 .721.544l.195.682c.118.415.443.74.858.858l.682.195a.75.75 0 0 1 0 1.442l-.682.195a1.25 1.25 0 0 0-.858.858l-.195.682a.75.75 0 0 1-1.442 0l-.195-.682a1.25 1.25 0 0 0-.858-.858l-.682-.195a.75.75 0 0 1 0-1.442l.682-.195a1.25 1.25 0 0 0 .858-.858l.195-.682A.75.75 0 0 1 12 1ZM10 11a.75.75 0 0 1 .728.568.968.968 0 0 0 .704.704.75.75 0 0 1 0 1.456.968.968 0 0 0-.704.704.75.75 0 0 1-1.456 0 .968.968 0 0 0-.704-.704.75.75 0 0 1 0-1.456.968.968 0 0 0 .704-.704A.75.75 0 0 1 10 11Z"
            clipRule="evenodd"
          />
        </svg>

        {/* The input */}
        <input
          id="aiPrompt"
          type="text"
          name="prompt"
          placeholder="Ask AI ..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={loading}
          className="
            w-full rounded-radius border border-outline bg-surface-alt
            px-3 py-2 pl-10 pr-24 text-sm text-on-surface
            placeholder:text-on-surface/60
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary
            disabled:cursor-not-allowed disabled:opacity-75
            dark:bg-surface-alt/50 dark:text-on-surface
          "
          onKeyDown={(e) => {
            // Nice UX: Enter submits, Shift+Enter allows future multiline (if you swap to textarea)
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />

        {/* The button (absolute right) */}
        <button
          type="button"
          onClick={handleSubmit}
          disabled={loading}
          className="
            absolute right-3 top-1/2 -translate-y-1/2
            rounded-radius bg-primary px-3 py-1.5 text-xs font-semibold tracking-wide
            text-on-primary transition
            hover:opacity-80 disabled:opacity-60 disabled:cursor-not-allowed
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary
          "
        >
          {loading ? "Generating..." : "Generate"}
        </button>
      </div>
    </div>
  );
}
