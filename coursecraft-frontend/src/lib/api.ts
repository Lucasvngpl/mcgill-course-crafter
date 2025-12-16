// src/lib/api.ts
// URL of your FastAPI backend
const API_BASE_URL = "http://127.0.0.1:8000";

export async function askQuestion(question: string): Promise<string> {
    const response = await fetch(`${API_BASE_URL}/query`, { // Send a POST request to the /query endpoint
        method: "POST",
        headers: {
            "Content-Type": "application/json", // Specify JSON content type as we are sending JSON data which is essentially a string
        },
        body: JSON.stringify({ question }), // Send the question from user in the request body
    });
    
    if (!response.ok) {
        throw new Error("Failed to fetch answer from the server."); // Error handling
    }
    const data = await response.json(); // Parse the JSON response
    // FastAPI returns: { "answer": "..." }
    return (data as any).answer as string;

}