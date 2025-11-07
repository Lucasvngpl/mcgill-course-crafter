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




