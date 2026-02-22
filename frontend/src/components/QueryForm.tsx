import { useState, useRef } from "react";

type QueryFormProps = {
  loading: boolean;
  onSubmit: (question: string) => void;
};

export default function QueryForm({ loading, onSubmit }: QueryFormProps) {
  const [question, setQuestion] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = () => {
    if (!question.trim() || loading) return;
    onSubmit(question);
    setQuestion("");
    // Reset height after clearing
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setQuestion(e.target.value);
    // Auto-resize up to 160px
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
  };

  return (
    <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-[#1e1f20] px-4 py-3 transition focus-within:border-white/20">
      <label htmlFor="aiPrompt" className="sr-only">Ask a question</label>
      <textarea
        ref={textareaRef}
        id="aiPrompt"
        rows={1}
        placeholder="Ask about McGill courses, prerequisites..."
        value={question}
        onChange={handleChange}
        disabled={loading}
        className="flex-1 resize-none bg-transparent text-sm leading-relaxed text-[#e3e3e3] placeholder:text-[#5f6368] focus:outline-none disabled:opacity-50"
        style={{ maxHeight: "160px" }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
          }
        }}
      />

      {/* Send button */}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={loading || !question.trim()}
        aria-label="Send"
        className="flex size-8 shrink-0 items-center justify-center rounded-full bg-[#c4c7c5] transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-30"
      >
        {loading ? (
          /* Spinner */
          <svg className="size-4 animate-spin text-[#131314]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        ) : (
          /* Send arrow */
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="size-4 text-[#131314]">
            <path d="M2.87 2.298a.75.75 0 0 0-.812 1.021L3.39 6.624a1 1 0 0 0 .928.626H8.25a.75.75 0 0 1 0 1.5H4.318a1 1 0 0 0-.927.626l-1.333 3.305a.75.75 0 0 0 .811 1.022l11-3.498a.75.75 0 0 0 0-1.426L2.87 2.298Z" />
          </svg>
        )}
      </button>
    </div>
  );
}
