
import pathlib
import re
from dotenv import find_dotenv, load_dotenv
from deterministic_logic import get_courses_requiring

# Load .env explicitly (use absolute path to be safe) BEFORE importing libs
load_dotenv("/Users/Lucas/mcgill_scraper/.env", override=True)
import os
# load .env BEFORE importing modules that may read OPENAI_API_KEY
env_path = find_dotenv()
if env_path:
    load_dotenv(env_path)
else:
    load_dotenv()  # fallback to default .env in cwd
# debug (safe): show working dir and whether key is present (does NOT print the key)
print("cwd:", pathlib.Path.cwd())
print(".env found:", bool(env_path or pathlib.Path(".env").exists()))
print("OPENAI_API_KEY present:", bool(os.getenv("OPENAI_API_KEY")))
from langchain_openai import ChatOpenAI
from rag_layer import hybrid_search, enrich_context, set_llm

# quick sanity check (do NOT print the key in logs; just fail loudly if missing)
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY not set in environment")

# 1️⃣ Initialize model
llm = ChatOpenAI(model="gpt-5", temperature=0.7, openai_api_key=os.getenv("OPENAI_API_KEY"))

# Set LLM in rag_layer for query understanding
set_llm(llm)


def detect_query_type(query: str):
    """Detect if user is asking for reverse prereqs."""
    reverse_patterns = [
        r"what can i take after",
        r"what courses? require",
        r"i finished .+,? what'?s next",
        r"after .+,? what",
        r"courses? that need",
    ]
    for pattern in reverse_patterns:
        if re.search(pattern, query.lower()):
            return "reverse_prereq"
    return "prereq"



# 2️⃣ Prompt construction
def generate_answer(query):
    query_type = detect_query_type(query)
    
    # Extract course ID
    match = re.search(r'\b([A-Z]{3,4})[\s\-]?(\d{3}[A-Z]?)\b', query.upper())
    
    if match and query_type == "reverse_prereq":
        course_id = f"{match.group(1)} {match.group(2)}"
        courses = get_courses_requiring(course_id)
        if courses:
            return f"Courses that require {course_id}: {', '.join(courses)}"
        return f"No courses in the database list {course_id} as a prerequisite."




    # Hybrid search to retrieve relevant documents
    retrieved_docs = hybrid_search(query)

    # 2️⃣ Enrich retrieved docs
    top_ids = [r["course_id"] for r in retrieved_docs]
    context_docs = enrich_context(top_ids)

    # 3️⃣ Build context string
    context = "\n\n".join(
        f"{d['id']} ({d['credits']} credits, {d['department']}) - {d['description']}\nPrereqs: {d['prereqs'] or 'None'}\nCoreqs: {d['coreqs'] or 'None'}"
        for d in context_docs
    )
    prompt = f"""You are a helpful academic assistant for McGill University.
Use only the context below to answer the student's question.

[UNDERSTANDING STUDENT QUESTIONS]
Students ask about prerequisites in different ways. These mean the SAME thing:
- "What are the prerequisites for X?" = "What do I need before X?" = "What's required for X?"
- "Which courses require X?" = "What can I take after X?" = "What courses need X?" = "I finished X, what's next?"

[CRITICAL RULES]
- Use ONLY the context provided — do NOT make up information.
- If the context doesn't contain the answer, say "I don't have enough information to answer that."
- When listing courses, include ALL matches from the context.
- For prerequisite questions: look at the "Prereqs:" field of the course asked about.
- For "what requires X" questions: look for courses where X appears in their "Prereqs:" field.

Question: {query}
Context:
{context}
Answer clearly and concisely:
"""
    # 3️⃣ Generate answer using the LLM
    response = llm.invoke(prompt)
    return response.content


# 4️⃣ Test
if __name__ == "__main__":
    print(generate_answer("Which courses require COMP 250?"))
        
    
