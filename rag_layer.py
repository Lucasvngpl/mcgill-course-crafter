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
    


_COURSE_ID_RE = re.compile(r'\b([A-Z]{3,4})[\s\-]?(\d{3}[A-Z]?)\b', re.IGNORECASE)

def extract_course_id(query: str) -> Optional[str]:
    """Extract a course ID from query, normalize to 'DEPT NNN' format."""
    match = _COURSE_ID_RE.search(query)
    if match:
        return f"{match.group(1).upper()} {match.group(2).upper()}"
    return None   


def get_course_directly(course_id: str) -> Optional[dict]:
    """Fetch a single course by exact ID from the database."""
    with DBSession() as session:
        course = session.query(Course).filter_by(id=course_id).first()
        if course:
            return {
                "id": course.id,
                "title": course.title,
                "department": course.offered_by,
                "credits": float(course.credits or 0),
                "prereqs": course.prereq_text,
                "coreqs": course.coreq_text,
                "description": course.description,
            }
    return None


# STEP 4️⃣ — Hybrid Search: Combine semantic + structured logic

def hybrid_search(query: str, dept: str = None, prereq_of: str = None, n_results: int = 50): # Hybrid Search (semantic + deterministic)
    """Combine semantic retrieval with my logic from the SQLAlchemy layer.
    
    Uses LLM to understand query intent and reformulate for better retrieval.
    """

    # ✅ FIX 1: Extract course ID from query
    course_id = extract_course_id(query)

    # ✅ FIX 2: Detect query intent
    query_lower = query.lower()
    is_asking_prereqs_for = course_id and any(phrase in query_lower for phrase in [
        "prerequisite for", "prerequisites for", "prereqs for", 
        "what do i need for", "requirements for"
    ])

    is_asking_what_requires = course_id and any(phrase in query_lower for phrase in [ 
        "require", "need", "courses that use", "after", "next", 
    "finished", "completed", "done with", "taken", "what can i take"
    ]) and "for" not in query_lower
    # ✅ This correctly excludes "prerequisites FOR X" queries

    # ✅ FIX 3: Handle "prerequisites FOR X" - just fetch X's prereq_text
    if is_asking_prereqs_for and course_id:
        course = get_course_directly(course_id)
        if course:
            return [{
                "course_id": course["id"],
                "score": 0.0,
                **course
            }]
        # Course not found, fall through to semantic search
        # (This is intentional - we want to give semantic search a chance)
    # ✅ FIX 4: Handle "which courses REQUIRE X" - find courses listing X as prereq
    if is_asking_what_requires and course_id:
        prereq_of = course_id

    # Handle prereq_of (courses that require this course)
    if prereq_of:
        prereq_targets = get_courses_requiring(prereq_of) or []
        if not prereq_targets:
            return []
        enriched = enrich_context(prereq_targets)
        return [{"course_id": e["id"], "score": 0.0, **{k: v for k, v in e.items() if k != "id"}} for e in enriched]
    
    # ✅ FIX 5: If query mentions a course ID, fetch it directly first
    if course_id:
        course = get_course_directly(course_id)
        if course:
            return [{
                "course_id": course["id"],
                "score": 0.0,
                **course
            }]
    
    # Fall back to semantic search for general queries
    results = semantic_search(query, n_results)
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_collection("courses_collection")
    metadatas = collection.get(ids=[r["course_id"] for r in results])["metadatas"]
    combined = [{**r, **meta} for r, meta in zip(results, metadatas)]
    
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




