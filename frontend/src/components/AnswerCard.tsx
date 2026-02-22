import { useState } from "react";
import { toast } from "sonner";

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

      {/* AI message — left aligned with avatar */}
      <div className="flex items-start gap-3 pr-8">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="mt-0.5 size-5 shrink-0 text-[#9aa0a6]">
          <path fillRule="evenodd" d="M9 4.5a.75.75 0 0 1 .721.544l.813 2.846a3.75 3.75 0 0 0 2.576 2.576l2.846.813a.75.75 0 0 1 0 1.442l-2.846.813a3.75 3.75 0 0 0-2.576 2.576l-.813 2.846a.75.75 0 0 1-1.442 0l-.813-2.846a3.75 3.75 0 0 0-2.576-2.576l-2.846-.813a.75.75 0 0 1 0-1.442l2.846-.813A3.75 3.75 0 0 0 7.466 7.89l.813-2.846A.75.75 0 0 1 9 4.5ZM18 1.5a.75.75 0 0 1 .728.568l.258 1.036c.236.94.97 1.674 1.91 1.91l1.036.258a.75.75 0 0 1 0 1.456l-1.036.258c-.94.236-1.674.97-1.91 1.91l-.258 1.036a.75.75 0 0 1-1.456 0l-.258-1.036a3.375 3.375 0 0 0-1.91-1.91l-1.036-.258a.75.75 0 0 1 0-1.456l1.036-.258a3.375 3.375 0 0 0 1.91-1.91l.258-1.036A.75.75 0 0 1 18 1.5ZM16.5 15a.75.75 0 0 1 .712.513l.394 1.183c.15.447.5.799.948.948l1.183.395a.75.75 0 0 1 0 1.422l-1.183.395c-.447.15-.799.5-.948.948l-.395 1.183a.75.75 0 0 1-1.422 0l-.395-1.183a1.5 1.5 0 0 0-.948-.948l-1.183-.395a.75.75 0 0 1 0-1.422l1.183-.395c.447-.15.799-.5.948-.948l.395-1.183A.75.75 0 0 1 16.5 15Z" clipRule="evenodd" />
        </svg>

        <div className="flex-1 min-w-0">
          <p className="mb-2 text-xs font-medium text-[#9aa0a6]">CourseCraft AI</p>

          {/* Typing indicator */}
          {loading && (
            <div className="flex items-center gap-1.5 h-5">
              {[0, 0.15, 0.3].map((delay, i) => (
                <span
                  key={i}
                  className="size-2 rounded-full bg-[#9aa0a6] animate-bounce"
                  style={{ animationDelay: `${delay}s`, animationDuration: "1s" }}
                />
              ))}
            </div>
          )}

          {/* Error */}
          {!loading && error && (
            <p className="text-sm text-red-400">{error}</p>
          )}

          {/* Answer */}
          {!loading && !error && answer && (
            <>
              <p className="text-sm leading-relaxed text-[#e3e3e3] whitespace-pre-wrap">{answer}</p>

              {/* Copy button */}
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
