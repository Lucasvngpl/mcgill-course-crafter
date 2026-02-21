// src/lib/api.ts
// URL of your FastAPI backend
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"; // Fallback to localhost if env variable is not set

// token is optional — if provided, backend can identify the user and personalize responses
export async function askQuestion(question: string, token?: string | null): Promise<string> {
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
    // FastAPI returns: { "answer": "..." }
    return (data as any).answer as string;

}