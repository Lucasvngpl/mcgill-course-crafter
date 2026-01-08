import { useState } from "react";
import QueryForm from "./components/QueryForm";
import AnswerCard from "./components/AnswerCard";
import { askQuestion } from "./lib/api";

type Message = {
  question: string;
  answer: string;
  error?: string | null;
};

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (question: string) => {
    // Add placeholder message
    setMessages((prev) => [...prev, { question, answer: "", error: null }]);
    setLoading(true);

    try {
      const answer = await askQuestion(question);
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

  return (
    <div className="flex min-h-screen flex-col bg-surface text-on-surface">
      {/* Header */}
      <header className="border-b border-outline bg-surface-alt p-4">
        <h1 className="text-xl font-bold text-on-surface-strong">CourseCraft AI</h1>
        <p className="text-sm text-on-surface">Ask about McGill courses, prerequisites, and more</p>
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