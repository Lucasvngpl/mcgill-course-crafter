
import pathlib

from dotenv import find_dotenv, load_dotenv

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
from rag_layer import hybrid_search
from rag_layer import enrich_context

# quick sanity check (do NOT print the key in logs; just fail loudly if missing)
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY not set in environment")

# 1️⃣ Initialize model
llm = ChatOpenAI(model="gpt-5", temperature=0.2, openai_api_key=os.getenv("OPENAI_API_KEY"))

# 2️⃣ Prompt construction
def generate_answer(query):
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
        
    
