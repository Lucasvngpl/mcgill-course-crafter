# rag_layer.py
import chromadb
from chromadb.utils import embedding_functions
from db_connection import Session as DBSession
from db_setup import Course
from deterministic_logic import get_courses_requiring

# Step 1️⃣ — Load courses from DB
def load_course_docs():
    """Extracts all course information from the database and prepares it for vectorization."""
    '''read course rows from Postgres and turn them into in-memory documents'''
    '''opens a DB session, queries all Course rows, builds a list of dicts with id, title, 
       description, prereq_text, coreq_text and returns it.'''

    with DBSession() as session:
        courses = session.query(Course).all()
        documents = []
        for course in courses:
            doc = {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "prerequisites": course.prereq_text,
                "corequisites": course.coreq_text,
            }
            documents.append(doc)
        return documents
    
# Step 2️⃣ — Build and persist the Chroma collection
def build_vector_store():
    """embed those documents with a SentenceTransformer model and persist them into a Chroma DB"""
    '''creates a PersistentClient at ./chroma_db, creates an embedding function (all‑MiniLM‑L6‑v2), 
    gets/creates a Chroma collection, loads docs from DB, extracts ids and (intended) texts, and adds them to the collection'''
    client = chromadb.PersistentClient(path="./chroma_db")
    # Choose the embedding model for converting text → vectors
    # Converts course text into high-dimensional numerical vectors that capture meaning rather than just words.
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    # Get or create a Chroma collection (similar to a “table” in a vector DB)
    collection = client.get_or_create_collection(
        name="courses_collection",
        embedding_function=embedding_fn
    )
    # Load all course documents from the PostgreSQL database
    docs = load_course_docs()
    # Extract the course IDs (used as document identifiers)
    ids = [d["id"] for d in docs]
    # Extract the text content for embedding
    texts = [d["text"] for d in docs]
    # Add these documents to the Chroma collection
    # A namespace or table inside Chroma where you store all related embeddings (e.g., all McGill courses).
    collection.add(ids=ids, documents=texts)
    print(f"✅ Chroma vector store built with {len(docs)} courses")

# Step 3️⃣ — Semantic search to find similar courses
def semantic_search(query: str, n_results: int = 5):
    """run a semantic query against the persisted Chroma collection and return matching course ids + scores"""
    '''connects to the same Chroma DB, recreates the embedding model, gets the collection, 
       soruns a query, and returns a list of dicts with course_id and score'''
    client = chromadb.PersistentClient(path="./chroma_db")
    # Recreate the same embedding model used for indexing
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

    collection = client.get_or_create_collection(
        name="courses",
        embedding_function=embedding_fn
    )
    # query means "search" Like saying: “Find courses that mean the same as this sentence.”
    results = collection.query(
        query_texts=[query], # what the user is searching for
        n_results=n_results # how many similar courses to return
    )
    out = [
        {"course_id": id_, "score": float(score)}
        for id_, score in zip(results["ids"][0], results["distances"][0])
    ]
    return out

# STEP 4️⃣ — Hybrid Search: Combine semantic + structured logic

def hybrid_search(query: str, dept: str = None, prereq_of: str = None, n_results: int = 5):
    """Combine semantic retrieval with structured filters from the SQL layer."""
    
    # First, get semantically similar courses from Chroma
    results = semantic_search(query, n_results)

    # Connect to the same Chroma DB again (to fetch metadata)
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_collection("courses_collection")

    # Retrieve metadata for those results (department, title, etc.)
    metadatas = collection.get(ids=[r["course_id"] for r in results])["metadatas"]

    # Combine vector results with metadata
    combined = [
        {**r, **meta} for r, meta in zip(results, metadatas)
    ]

    # Filter by department (symbolic condition)
    if dept:
        combined = [c for c in combined if c["department"].upper() == dept.upper()]

    # Filter by prerequisite relationships using the deterministic layer
    if prereq_of:
        prereq_targets = get_courses_requiring(prereq_of)
        combined = [c for c in combined if c["course_id"] in prereq_targets]

    return combined



