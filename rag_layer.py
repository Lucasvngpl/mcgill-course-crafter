# rag_layer.py
import re
from typing import Optional
import chromadb
from chromadb.utils import embedding_functions
from db_connection import Session as DBSession
from db_setup import Course
from deterministic_logic import get_courses_requiring

# Import LLM for query understanding (will be set by qa_agent)
_llm = None

def set_llm(llm_instance):
    """Set the LLM instance for query understanding."""
    global _llm
    _llm = llm_instance



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
            text = " ".join(filter(None, [
                course.title or "",
                course.description or "",
                course.prereq_text or "",
                course.coreq_text or ""
            ]))
            documents.append({
                "id": course.id,
                "text": text,
                "title": course.title,
                "department": (course.id.split()[0] if course.id else None)
            })
        return documents

# Step 2️⃣ — Build and persist the Chroma collection
def build_vector_store():
    """embed those documents with a SentenceTransformer model and persist them into a Chroma DB"""
    '''creates a PersistentClient at ./chroma_db, creates an embedding function (all‑MiniLM‑L6‑v2), 
    gets/creates a Chroma collection, loads docs from DB, extracts ids and (intended) texts, and adds them to the collection'''
    client = chromadb.PersistentClient(path="./chroma_db")
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    collection = client.get_or_create_collection(
        name="courses_collection",
        embedding_function=embedding_fn
    )

    docs = load_course_docs() or []
    # filter & normalize, dedupe by id (keep first occurrence)
    seen = set()
    clean_docs = []
    for d in docs:
        _id = d.get("id")
        if _id is None:
            continue
        _id = str(_id).strip()
        if not _id or _id in seen:
            continue
        seen.add(_id)
        clean_docs.append({
            "id": _id,
            "text": str(d.get("text", "")),
            "title": str(d.get("title", "") or ""),
            "department": str(d.get("department", "") or "")
        })

    ids = [d["id"] for d in clean_docs]
    texts = [d["text"] for d in clean_docs]
    metadatas = [{"title": d["title"], "department": d["department"]} for d in clean_docs]

    print(f"Preparing to index {len(ids)} documents (original {len(docs)})")
    if not ids:
        print("No valid documents to index. Exiting.")
        return

    if not (len(ids) == len(texts) == len(metadatas)):
        print("Length mismatch after cleaning — aborting.")
        return

    # Try bulk add first, avoiding Chroma max-batch-size errors

    try:
        batch_size = min(5000, len(ids))
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i+batch_size]
            batch_texts = texts[i:i+batch_size]
            batch_metadatas = metadatas[i:i+batch_size]
            collection.add(ids=batch_ids, documents=batch_texts, metadatas=batch_metadatas)
        print(f"✅ Chroma vector store built with {len(ids)} documents (batched, batch_size={batch_size})")
        return
    except Exception:
        import traceback
        print("Batched add failed, falling back to per-document add to locate bad entries.")
        traceback.print_exc()

    # Fallback: add one-by-one to find failing document(s)
    for idx, (_id, txt, meta) in enumerate(zip(ids, texts, metadatas)):
        try:
            collection.add(ids=[_id], documents=[txt], metadatas=[meta])
        except Exception:
            print(f"❌ Failed to add document at index {idx}, id={_id!r}")
            import traceback
            traceback.print_exc()
            # Option: continue to attempt remaining docs or break; we break to let you inspect the failing item
            break
    else:
        print("✅ All documents added individually (fallback succeeded).")

# Step 3️⃣ — Semantic search to find similar courses
def semantic_search(query: str, n_results: int = 5):
    """run a semantic query against the persisted Chroma collection and return matching course ids + scores"""
    '''connects to the same Chroma DB, recreates the embedding model, gets the collection, 
       soruns a query, and returns a list of dicts with course_id and score'''
    client = chromadb.PersistentClient(path="./chroma_db")
    # Recreate the same embedding model used for indexing
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

    collection = client.get_or_create_collection(
        name="courses_collection",
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

# Helper function to use LLM to understand query intent and reformulate for better retrieval
def understand_query_for_retrieval(query: str) -> dict:
    """Use LLM to understand the query and reformulate it for semantic search.
    
    Returns a dict with:
    - reformulated_query: Better query for semantic search
    - search_strategy: 'semantic' or 'prereq_lookup'
    - course_code: Extracted course code if applicable
    """
    if not _llm:
        # Fallback to original query if LLM not available
        return {
            "reformulated_query": query,
            "search_strategy": "semantic",
            "course_code": None
        }
    
    understanding_prompt = f"""Analyze this query about McGill University courses and determine:
1. What is the user really asking for?
2. If asking "which courses require X", extract the course code X
3. Reformulate the query to search for courses that would answer this question

Query: "{query}"

Respond in this exact JSON format:
{{
    "intent": "prereq_lookup" or "general_search",
    "course_code": "COMP 250" or null,
    "reformulated_query": "courses that have COMP 250 as a prerequisite" or the original query
}}

Examples:
- "Which courses require COMP 250?" -> {{"intent": "prereq_lookup", "course_code": "COMP 250", "reformulated_query": "courses with COMP 250 as prerequisite"}}
- "What is COMP 250 about?" -> {{"intent": "general_search", "course_code": "COMP 250", "reformulated_query": "What is COMP 250 about?"}}
- "Tell me about machine learning courses" -> {{"intent": "general_search", "course_code": null, "reformulated_query": "machine learning courses"}}

JSON response only:"""

    try:
        response = _llm.invoke(understanding_prompt)
        import json
        # Try to extract JSON from response
        content = response.content.strip()
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        result = json.loads(content)
        return {
            "reformulated_query": result.get("reformulated_query", query),
            "search_strategy": result.get("intent", "general_search"),
            "course_code": result.get("course_code")
        }
    except Exception as e:
        # Fallback on error
        print(f"LLM query understanding failed: {e}, using original query")
        return {
            "reformulated_query": query,
            "search_strategy": "semantic",
            "course_code": None
        }

# STEP 4️⃣ — Hybrid Search: Combine semantic + structured logic

def hybrid_search(query: str, dept: str = None, prereq_of: str = None, n_results: int = 50): # Hybrid Search (semantic + deterministic)
    """Combine semantic retrieval with my logic from the SQLAlchemy layer.
    
    Uses LLM to understand query intent and reformulate for better retrieval.
    """
    
    # Use LLM to understand the query if prereq_of not explicitly provided
    if not prereq_of:
        query_understanding = understand_query_for_retrieval(query)
        
        # If LLM detected a prerequisite lookup, use deterministic logic
        if query_understanding["search_strategy"] == "prereq_lookup" and query_understanding["course_code"]:
            prereq_of = query_understanding["course_code"]
        else:
            # Use reformulated query for better semantic search
            query = query_understanding["reformulated_query"]
    
    # If this is a prerequisite query, use both semantic search and deterministic lookup
    if prereq_of:
        # Semantic search: find courses that mention this course code in their text
        # This will find courses that have it in description, prereqs, etc.
        semantic_query = f"{prereq_of} prerequisite"
        semantic_results = semantic_search(semantic_query, n_results=100)
        
        # Deterministic lookup: find courses that explicitly list it as prerequisite
        prereq_targets = get_courses_requiring(prereq_of) or []
        
        # Combine both approaches - prioritize deterministic matches but include semantic matches
        all_course_ids = set(prereq_targets)
        for r in semantic_results:
            all_course_ids.add(r["course_id"])
        
        if not all_course_ids:
            return []
        
        # Fetch full metadata/enrichment for all targets
        enriched = enrich_context(list(all_course_ids))
        
        # Score: deterministic matches get score 0.0, semantic matches keep their scores
        semantic_scores = {r["course_id"]: r["score"] for r in semantic_results}
        deterministic_matches = set(prereq_targets)
        
        combined = []
        for e in enriched:
            course_id = e["id"]
            # Use semantic score if available, otherwise 0.0 for deterministic matches
            score = semantic_scores.get(course_id, 0.0)
            # Boost score slightly for deterministic matches
            if course_id in deterministic_matches:
                score = min(score, 0.0)  # Ensure deterministic matches are ranked highest
            
            combined.append({
                "course_id": course_id,
                "score": score,
                **{k: v for k, v in e.items() if k != "id"}
            })
        
        # Sort by score (lower is better for distance, but deterministic should come first)
        combined.sort(key=lambda x: (x["course_id"] not in deterministic_matches, x["score"]))
        return combined
    
    # For general queries, use semantic search with reformulated query
    # Increased n_results to give LLM more context to work with
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

    return combined

def enrich_context(course_ids: list[str]): # Context Enrichment (post-retrieval)
    """Fetch additional info (credits, offered_by, prereqs/coreqs) for retrieved courses.""" # given a list of course IDs, return enriched info from the DB
    with DBSession() as session:
        courses = session.query(Course).filter(Course.id.in_(course_ids)).all()
        enriched = []
        for c in courses:
            enriched.append({
                "id": c.id,
                "title": c.title,
                "department": c.offered_by,
                "credits": float(c.credits or 0),
                "offered_fall": c.offered_fall,
                "offered_winter": c.offered_winter,
                "offered_summer": c.offered_summer,
                "prereqs": c.prereq_text,
                "coreqs": c.coreq_text,
                "description": c.description,
            })
        return enriched




