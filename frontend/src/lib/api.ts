// src/lib/api.ts
// URL of your FastAPI backend
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"; // Fallback to localhost if env variable is not set

// A source is either a course (code + title) or a program (name + faculty)
// shown in the "thinking" header after the answer loads.
export type Source =
  | { type: "course"; id: string; title: string }
  | { type: "program"; name: string; faculty: string; url: string };

export type AnswerResult = {
  answer: string;
  sources: Source[];
};

// token is optional — if provided, backend can identify the user and personalize responses
export async function askQuestion(question: string, token?: string | null): Promise<AnswerResult> {
    // Build headers — always include Content-Type, optionally include auth token
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
    };
    // If user is signed in, attach their Supabase JWT so backend can identify them
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}/query`, {
        method: "POST",
        headers,
        body: JSON.stringify({ question }),
    });

    if (!response.ok) {
        throw new Error("Failed to fetch answer from the server."); // Error handling
    }
    const data = await response.json(); // Parse the JSON response
    // FastAPI returns: { "answer": "...", "sources": [...] }
    return {
        answer: data.answer as string,
        sources: (data.sources ?? []) as Source[],
    };
}
