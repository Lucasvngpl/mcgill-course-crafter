from langchain_openai import ChatOpenAI
from rag_layer import hybrid_search

# 1️⃣ Initialize model
llm = ChatOpenAI(model="gpt-4-turbo")

# 2️⃣ Prompt construction
def generate_answer(query):
    # Hybrid search to retrieve relevant documents
    retrieved_docs = hybrid_search(query)

    # combine context from retrieved documents
    context = "\n\n".join([
        f"{r['title']} ({r['course_id']}): dept={r['department']}"
        for r in retrieved_docs
    ])
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
        
    
