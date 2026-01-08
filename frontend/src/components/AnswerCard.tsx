// Receives the answer (or loading / error), Displays a styled card
// src/components/AnswerCard.tsx
// A presentational component: it doesn't call the API.
// It just displays "question" + "answer" and a couple simple actions.

type AnswerCardProps = {
  question: string;
  answer: string;
  loading?: boolean;
  error?: string | null;
};

export default function AnswerCard({
  question,
  answer,
  loading = false,
  error = null,
}: AnswerCardProps) {
  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      // For learning: you can replace this alert with a nicer toast later
      alert("Copied!");
    } catch {
      alert("Copy failed (browser permissions)");
    }
  };

  return (
    <div className="flex w-full flex-col gap-4">
      {/* --- User message bubble --- */}
      <div className="w-full max-w-2xl rounded-radius border border-outline bg-surface-alt p-6 text-left">
        {/* Header row: avatar + name */}
        <div className="flex items-center gap-2 text-on-surface-strong">
          {/* Simple avatar circle (no external image needed) */}
          <div className="flex size-8 items-center justify-center rounded-full bg-outline text-xs font-bold text-on-surface-strong">
            U
          </div>
          <span className="text-sm font-bold">You</span>
        </div>

        {/* Body: the user's question */}
        <p className="mt-4 text-sm text-on-surface sm:pl-10 sm:mt-0">
          {question || "Ask something to get started..."}
        </p>

        {/* Actions row */}
        <div className="mt-2 flex items-center gap-2 sm:pl-10">
          <button
            type="button"
            onClick={() => copyToClipboard(question)}
            className="rounded-full p-1 text-on-surface/75 hover:bg-surface/50 hover:text-on-surface
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            title="Copy your question"
            aria-label="Copy your question"
            disabled={!question}
          >
            {/* Copy icon */}
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="size-4">
              <path
                fillRule="evenodd"
                d="M13.887 3.182c.396.037.79.08 1.183.128C16.194 3.45 17 4.414 17 5.517V16.75A2.25 2.25 0 0 1 14.75 19h-9.5A2.25 2.25 0 0 1 3 16.75V5.517c0-1.103.806-2.068 1.93-2.207.393-.048.787-.09 1.183-.128A3.001 3.001 0 0 1 9 1h2c1.373 0 2.531.923 2.887 2.182ZM7.5 4A1.5 1.5 0 0 1 9 2.5h2A1.5 1.5 0 0 1 12.5 4v.5h-5V4Z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* --- AI message bubble --- */}
      <div className="w-full max-w-2xl rounded-radius border border-outline bg-surface-alt p-6 text-left">
        {/* Header row: “AI badge” + name */}
        <div className="flex items-center gap-2 text-on-surface-strong">
          <span className="flex size-8 items-center justify-center rounded-full bg-primary text-on-primary">
            {/* Robot-ish icon */}
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="size-5">
              <path d="M6 12.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 0 1h-3a.5.5 0 0 1-.5-.5M3 8.062C3 6.76 4.235 5.765 5.53 5.886a26.6 26.6 0 0 0 4.94 0C11.765 5.765 13 6.76 13 8.062v1.157a.93.93 0 0 1-.765.935c-.845.147-2.34.346-4.235.346s-3.39-.2-4.235-.346A.93.93 0 0 1 3 9.219zm4.542-.827a.25.25 0 0 0-.217.068l-.92.9a25 25 0 0 1-1.871-.183.25.25 0 0 0-.068.495c.55.076 1.232.149 2.02.193a.25.25 0 0 0 .189-.071l.754-.736.847 1.71a.25.25 0 0 0 .404.062l.932-.97a25 25 0 0 0 1.922-.188.25.25 0 0 0-.068-.495c-.538.074-1.207.145-1.98.189a.25.25 0 0 0-.166.076l-.754.785-.842-1.7a.25.25 0 0 0-.182-.135" />
              <path d="M8.5 1.866a1 1 0 1 0-1 0V3h-2A4.5 4.5 0 0 0 1 7.5V8a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1v1a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-1a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1v-.5A4.5 4.5 0 0 0 10.5 3h-2zM14 7.5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V7.5A3.5 3.5 0 0 1 5.5 4h5A3.5 3.5 0 0 1 14 7.5" />
            </svg>
          </span>
          <span className="text-sm font-bold">CourseCraft AI</span>
        </div>

        {/* Body: loading / error / answer */}
        <div className="mt-4 text-sm text-on-surface sm:pl-10 sm:mt-0">
          {loading && <p className="opacity-75">Generating…</p>}

          {!loading && error && (
            <p className="text-danger">
              {error}
            </p>
          )}

          {!loading && !error && (
            <p className="whitespace-pre-wrap">{answer || "No answer yet."}</p>
          )}
        </div>

        {/* Actions row */}
        <div className="mt-2 flex items-center gap-2 sm:pl-10">
          <button
            type="button"
            onClick={() => copyToClipboard(answer)}
            className="rounded-full p-1 text-on-surface/75 hover:bg-surface/50 hover:text-on-surface
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            title="Copy answer"
            aria-label="Copy answer"
            disabled={!answer || loading}
          >
            {/* Copy icon */}
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="size-4">
              <path
                fillRule="evenodd"
                d="M13.887 3.182c.396.037.79.08 1.183.128C16.194 3.45 17 4.414 17 5.517V16.75A2.25 2.25 0 0 1 14.75 19h-9.5A2.25 2.25 0 0 1 3 16.75V5.517c0-1.103.806-2.068 1.93-2.207.393-.048.787-.09 1.183-.128A3.001 3.001 0 0 1 9 1h2c1.373 0 2.531.923 2.887 2.182ZM7.5 4A1.5 1.5 0 0 1 9 2.5h2A1.5 1.5 0 0 1 12.5 4v.5h-5V4Z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
