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

# Common English words that look like department codes (3-4 uppercase letters) but aren't.
# Without this, "WHAT 200-level courses" would match as course code "WHAT 200".
_DEPT_FALSE_POSITIVES = frozenset({
    'WHAT', 'THAT', 'HAVE', 'THIS', 'WHEN', 'THEN', 'WITH', 'FROM',
    'TAKE', 'GIVE', 'FIND', 'LIST', 'SHOW', 'NEED', 'WANT', 'LIKE',
    'DOES', 'EACH', 'MANY', 'MORE', 'MUCH', 'MOST', 'NEXT', 'SOME',
    'SUCH', 'VERY', 'WELL', 'WILL', 'THEY', 'THEM', 'YOUR', 'YEAR',
    'ALSO', 'INTO', 'OVER', 'LAST', 'LONG', 'LOOK', 'MAKE', 'JUST',
    'KNOW', 'LESS', 'MUST', 'NONE', 'ONLY', 'PLAN', 'REAL', 'SAME',
    'TELL', 'TEST', 'TIME', 'TRUE', 'TURN', 'TYPE', 'WAIT', 'WORK',
    'OPEN', 'HOLD', 'STAY', 'STOP', 'STEP', 'BOTH', 'EVEN', 'WERE',
    'BEEN', 'KEEP', 'WENT', 'BEST', 'PICK', 'SKIP', 'HELP', 'DONE',
})

# Cache for course titles to avoid repeated DB queries
_title_to_id_cache: dict = {}
_id_to_title_cache: dict = {}  # Reverse lookup
_duplicate_titles: dict = {}  # Titles that map to multiple courses
_cache_loaded = False

def _normalize_title(title: str) -> str:
    """Normalize a title for matching: lowercase, strip, remove trailing period."""
    return title.lower().strip().rstrip('.')

def _load_title_cache():
    """Load all course titles into memory for fast lookups."""
    global _title_to_id_cache, _id_to_title_cache, _duplicate_titles, _cache_loaded
    if _cache_loaded:
        return
    
    # First pass: collect all courses per normalized title
    title_to_courses: dict = {}
    with DBSession() as session:
        courses = session.query(Course.id, Course.title).all()
        for course_id, title in courses:
            if title:
                normalized = _normalize_title(title)
                if normalized not in title_to_courses:
                    title_to_courses[normalized] = []
                title_to_courses[normalized].append(course_id)
                _id_to_title_cache[course_id] = title
    
    # Second pass: identify duplicates and pick default (prefer COMP)
    for normalized, course_ids in title_to_courses.items():
        if len(course_ids) > 1:
            # Store all options for disambiguation
            _duplicate_titles[normalized] = course_ids
            # Pick default: prefer COMP, then alphabetically first
            comp_courses = [c for c in course_ids if c.startswith('COMP ')]
            if comp_courses:
                _title_to_id_cache[normalized] = comp_courses[0]
            else:
                _title_to_id_cache[normalized] = sorted(course_ids)[0]
        else:
            _title_to_id_cache[normalized] = course_ids[0]
    
    _cache_loaded = True


def find_course_by_title(query: str) -> tuple[Optional[str], Optional[list[str]]]:
    """Find a course ID by matching the course title in the query.
    
    Supports:
    - Exact title match (case-insensitive)
    - Partial title match (title contained in query)
    - Query contained in title
    
    Returns a tuple of:
    - course_id: The matched course ID (or default if ambiguous)
    - alternatives: List of alternative course IDs if ambiguous, None otherwise
    """
    _load_title_cache()
    
    if not _title_to_id_cache:
        return None, None
    
    query_lower = query.lower().strip()
    
    # Remove common question phrases to isolate the course title
    # e.g., "What are the prerequisites for Introduction to Computer Science?"
    # e.g., "What is Introduction to Computer Science about?"
    prefix_patterns = [
        r"what are the prerequisites for\s+",
        r"what are the prereqs for\s+",
        r"what do i need for\s+",
        r"prerequisites for\s+",
        r"prereqs for\s+",
        r"requirements for\s+",
        r"what is\s+",
        r"tell me about\s+",
        r"describe\s+",
        r"when is\s+",
        r"is\s+",
    ]
    
    suffix_patterns = [
        r"\s+about\??$",
        r"\s+offered\??$",
        r"\s+like\??$",
        r"\??$",
    ]
    
    cleaned_query = query_lower
    for pattern in prefix_patterns:
        cleaned_query = re.sub(pattern, "", cleaned_query, flags=re.IGNORECASE)
    for pattern in suffix_patterns:
        cleaned_query = re.sub(pattern, "", cleaned_query, flags=re.IGNORECASE)
    cleaned_query = _normalize_title(cleaned_query)  # Normalize: strip, lowercase, remove trailing period
    
    def check_ambiguous(normalized_title: str) -> tuple[str, Optional[list[str]]]:
        """Check if a title is ambiguous and return alternatives if so."""
        course_id = _title_to_id_cache[normalized_title]
        if normalized_title in _duplicate_titles:
            return course_id, _duplicate_titles[normalized_title]
        return course_id, None
    
    # 1. Exact match on cleaned query
    if cleaned_query in _title_to_id_cache:
        return check_ambiguous(cleaned_query)
    
    # 2. Check if any title is contained in the query (longest match first to prefer more specific)
    titles_by_length = sorted(_title_to_id_cache.keys(), key=len, reverse=True)
    query_normalized = _normalize_title(query_lower)
    for title in titles_by_length:
        if len(title) >= 5 and title in query_normalized:  # Minimum 5 chars to avoid false positives
            return check_ambiguous(title)
    
    # 3. Check if cleaned query is contained in any title (for partial matches)
    if len(cleaned_query) >= 5:
        for title, course_id in _title_to_id_cache.items():
            if cleaned_query in title:
                return check_ambiguous(title)
    
    return None, None


def extract_all_course_ids(query: str) -> list[str]:
    """Extract ALL course IDs from query, normalized to 'DEPT NNN' format.

    Examples:
    - "Can I take PHYS 230 and PHYS 258?" → ["PHYS 230", "PHYS 258"]
    - "COMP 250" → ["COMP 250"]
    """
    matches = _COURSE_ID_RE.findall(query)
    seen = set()
    result = []
    for dept, num in matches:
        course_id = f"{dept.upper()} {num.upper()}"
        if course_id not in seen:
            seen.add(course_id)
            result.append(course_id)
    return result


def extract_course_id(query: str) -> tuple[Optional[str], Optional[list[str]]]:
    """Extract a course ID from query, normalize to 'DEPT NNN' format.

    Supports both course codes and titles.

    Examples:
    - "COMP 250" → ("COMP 250", None)
    - "What are the prerequisites for Introduction to Computer Science?" → ("COMP 250", None)
    - "What is Operating Systems about?" → ("COMP 310", ["COMP 310", "ECSE 427"]) -- ambiguous

    Returns a tuple of:
    - course_id: The matched course ID
    - alternatives: List of alternative course IDs if ambiguous, None otherwise
    """
    # First, try regex match for course code (e.g., "COMP 250") - never ambiguous
    match = _COURSE_ID_RE.search(query)
    if match:
        return f"{match.group(1).upper()} {match.group(2).upper()}", None

    # Second, try to find by course title (may be ambiguous)
    course_id, alternatives = find_course_by_title(query)
    if course_id:
        return course_id, alternatives

    return None, None




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
                "offered_fall": course.offered_fall,
                "offered_winter": course.offered_winter,
                "offered_summer": course.offered_summer,
            }
    return None


# STEP 5️⃣ — Planning & Recommendation Queries

def get_entry_level_courses(department: str = None, term: str = None, limit: int = 10) -> list[dict]:
    """Find entry-level courses (no prerequisites) for a department.
    
    Args:
        department: Filter by department prefix (e.g., 'COMP', 'MATH')
        term: Filter by term offered ('fall', 'winter', 'summer')
        limit: Maximum number of courses to return
    
    Returns:
        List of course dicts sorted by course number (lowest first)
    """
    with DBSession() as session:
        query = session.query(Course)
        
        # Filter by department if specified
        if department:
            query = query.filter(Course.id.like(f"{department.upper()} %"))
        
        # Get all matching courses
        courses = query.all()
        
        # Filter for entry-level (no prereqs or minimal prereqs)
        entry_level = []
        for c in courses:
            prereq_text = (c.prereq_text or "").strip().lower()
            # No prerequisites or just CEGEP/high school requirements
            is_entry = (
                not prereq_text or 
                prereq_text == "none" or
                "cegep" in prereq_text and "comp" not in prereq_text.lower() and "math" not in prereq_text.lower()
            )
            if is_entry:
                # Check term if specified
                if term:
                    term_lower = term.lower()
                    if term_lower == 'fall' and not c.offered_fall:
                        continue
                    if term_lower == 'winter' and not c.offered_winter:
                        continue
                    if term_lower == 'summer' and not c.offered_summer:
                        continue
                
                entry_level.append({
                    "id": c.id,
                    "title": c.title,
                    "department": c.offered_by,
                    "credits": float(c.credits or 0),
                    "prereqs": c.prereq_text,
                    "coreqs": c.coreq_text,
                    "description": c.description,
                    "offered_fall": c.offered_fall,
                    "offered_winter": c.offered_winter,
                    "offered_summer": c.offered_summer,
                })
        
        # Sort by course number (extract number from ID like "COMP 250" -> 250)
        def get_course_num(course):
            try:
                return int(course["id"].split()[1][:3])
            except:
                return 999
        
        entry_level.sort(key=get_course_num)
        return entry_level[:limit]


def get_courses_by_level(department: str, level: int, term: str = None, limit: int = 10) -> list[dict]:
    """Find courses at a specific level (100, 200, 300, etc.).
    
    Args:
        department: Department prefix (e.g., 'COMP')
        level: Course level (100, 200, 300, 400, 500, 600)
        term: Filter by term offered
        limit: Maximum number of courses
    """
    with DBSession() as session:
        # Match courses like "COMP 2XX" for level 200
        level_prefix = str(level)[0]  # "200" -> "2"
        query = session.query(Course).filter(
            Course.id.like(f"{department.upper()} {level_prefix}%")
        )
        
        courses = query.all()
        result = []
        
        for c in courses:
            # Check term if specified
            if term:
                term_lower = term.lower()
                if term_lower == 'fall' and not c.offered_fall:
                    continue
                if term_lower == 'winter' and not c.offered_winter:
                    continue
                if term_lower == 'summer' and not c.offered_summer:
                    continue
            
            result.append({
                "id": c.id,
                "title": c.title,
                "department": c.offered_by,
                "credits": float(c.credits or 0),
                "prereqs": c.prereq_text,
                "coreqs": c.coreq_text,
                "description": c.description,
                "offered_fall": c.offered_fall,
                "offered_winter": c.offered_winter,
                "offered_summer": c.offered_summer,
            })
        
        # Sort by course number
        result.sort(key=lambda x: x["id"])
        return result[:limit]


def get_available_courses(completed_courses: list[str], department: str = None, term: str = None, limit: int = 15) -> list[dict]:
    """Find courses the student can take based on completed prerequisites.
    
    Args:
        completed_courses: List of course IDs the student has completed (e.g., ["COMP 250", "MATH 133"])
        department: Optional department filter
        term: Optional term filter
        limit: Maximum number of courses
    
    Returns:
        Courses where all prerequisites are satisfied by completed_courses
    """
    with DBSession() as session:
        query = session.query(Course)
        
        if department:
            query = query.filter(Course.id.like(f"{department.upper()} %"))
        
        courses = query.all()
        completed_set = set(c.upper().strip() for c in completed_courses)
        available = []
        
        for c in courses:
            # Skip if already completed
            if c.id in completed_set:
                continue
            
            # Check term if specified
            if term:
                term_lower = term.lower()
                if term_lower == 'fall' and not c.offered_fall:
                    continue
                if term_lower == 'winter' and not c.offered_winter:
                    continue
                if term_lower == 'summer' and not c.offered_summer:
                    continue
            
            prereq_text = (c.prereq_text or "").strip()
            
            # If no prereqs, it's available
            if not prereq_text:
                available.append(c)
                continue
            
            # Check if prereqs are satisfied
            # Extract course codes from prereq text
            prereq_codes = set(re.findall(r'\b([A-Z]{3,4})\s*(\d{3}[A-Z]?)\b', prereq_text.upper()))
            prereq_ids = {f"{dept} {num}" for dept, num in prereq_codes}
            
            # Simple check: if any prereq is in completed courses, consider it potentially available
            # (This is a simplification - real prereq logic can be complex with OR/AND)
            if prereq_ids and prereq_ids.issubset(completed_set):
                available.append(c)
            elif prereq_ids and any(pid in completed_set for pid in prereq_ids):
                # At least one prereq is met - might be available (OR logic)
                available.append(c)
        
        result = []
        for c in available:
            result.append({
                "id": c.id,
                "title": c.title,
                "department": c.offered_by,
                "credits": float(c.credits or 0),
                "prereqs": c.prereq_text,
                "coreqs": c.coreq_text,
                "description": c.description,
                "offered_fall": c.offered_fall,
                "offered_winter": c.offered_winter,
                "offered_summer": c.offered_summer,
            })
        
        # Sort by course number
        result.sort(key=lambda x: x["id"])
        return result[:limit]


def detect_planning_query(query: str) -> Optional[dict]:
    """Detect if the query is a planning/recommendation query.
    
    Returns a dict with:
        - type: 'first_semester', 'by_level', 'available', 'recommendation'
        - department: extracted department (e.g., 'COMP')
        - term: extracted term (e.g., 'fall', 'winter')
        - level: extracted level for level-based queries
        - completed: list of completed courses (for 'available' type)
    
    Returns None if not a planning query.
    """
    query_lower = query.lower()
    result = {"type": None, "department": None, "term": None, "level": None, "completed": []}
    
    # Extract department
    dept_patterns = [
        # Computer Science & Engineering
        (r'\b(cs|comp(?:uter)?(?:\s+science)?)\b', 'COMP'),
        (r'\b(software\s+engineering?|swe)\b', 'ECSE'),
        (r'\b(ecse|electrical(?:\s+engineering)?|ece)\b', 'ECSE'),
        (r'\b(mech(?:anical)?(?:\s+engineering)?)\b', 'MECH'),
        (r'\b(civil(?:\s+engineering)?|cive)\b', 'CIVE'),
        (r'\b(mining(?:\s+engineering)?|mimi)\b', 'MIMI'),
        # Sciences
        (r'\b(math(?:ematics)?)\b', 'MATH'),
        (r'\b(phys(?:ics)?)\b', 'PHYS'),
        (r'\b(chem(?:istry)?)\b', 'CHEM'),
        (r'\b(biol(?:ogy)?)\b', 'BIOL'),
        (r'\b(biochem(?:istry)?|bioc)\b', 'BIOC'),
        (r'\b(neurosci(?:ence)?|nrsc)\b', 'NRSC'),
        (r'\b(microbiol(?:ogy)?|immunol(?:ogy)?|mimm)\b', 'MIMM'),
        (r'\b(anat(?:omy)?)\b', 'ANAT'),
        (r'\b(physiol(?:ogy)?|phgy)\b', 'PHGY'),
        (r'\b(atmospheric|oceanograph(?:y|ic)?|atoc)\b', 'ATOC'),
        (r'\b(earth\s+(?:and\s+)?planetary|epsc)\b', 'EPSC'),
        (r'\b(pharmac(?:y|ology)|phar)\b', 'PHAR'),
        # Social Sciences
        (r'\b(econ(?:omics)?)\b', 'ECON'),
        (r'\b(psyc(?:hology)?)\b', 'PSYC'),
        (r'\b(soci(?:ology)?)\b', 'SOCI'),
        (r'\b(anth(?:ropology)?)\b', 'ANTH'),
        (r'\b(poli(?:tical)?\s*sci(?:ence)?|political\s+science)\b', 'POLI'),
        (r'\b(geog(?:raphy)?)\b', 'GEOG'),
        (r'\b(ling(?:uistics)?)\b', 'LING'),
        (r'\b(kine(?:siology)?)\b', 'KINE'),
        (r'\b(social\s+work|swrk)\b', 'SWRK'),
        (r'\b(nutr(?:ition)?|diet(?:etics)?)\b', 'NUTR'),
        # Humanities
        (r'\b(hist(?:ory)?)\b', 'HIST'),
        (r'\b(english|engl)\b', 'ENGL'),
        (r'\b(french\s+(?:language|lit|studies?)|fren)\b', 'FREN'),
        (r'\b(phil(?:osophy)?)\b', 'PHIL'),
        (r'\b(relig(?:ion|ious\s+stud(?:ies)?))\b', 'RELI'),
        (r'\b(art\s+hist(?:ory)?|arth)\b', 'ARTH'),
        (r'\b(music|musc)\b', 'MUSC'),
        # Professional / Other
        (r'\b(mgmt|management)\b', 'MGMT'),
        (r'\b(nurs(?:ing)?)\b', 'NURS'),
        (r'\b(envir(?:onmental)?(?:\s+stud(?:ies)?)?|envi)\b', 'ENVI'),
        (r'\b(educ(?:ation)?|edpe|edsl)\b', 'EDPE'),
    ]
    for pattern, dept in dept_patterns:
        if re.search(pattern, query_lower):
            result["department"] = dept
            break
    
    # Extract term
    if any(t in query_lower for t in ['fall', 'autumn', 'first semester', 'semester 1', 'f1']):
        result["term"] = "fall"
    elif any(t in query_lower for t in ['winter', 'second semester', 'semester 2', 'w2']):
        result["term"] = "winter"
    elif 'summer' in query_lower:
        result["term"] = "summer"
    
    # Extract level/year (U2/U3/U4 are McGill-specific year notations)
    level_patterns = [
        (r'\bu2\b', 200),
        (r'\bu3\b', 300),
        (r'\bu4\b', 400),
        (r'\b(second|2nd|sophomore)\s*(year)?\b', 200),
        (r'\b(third|3rd|junior)\s*(year)?\b', 300),
        (r'\b(fourth|4th|senior)\s*(year)?\b', 400),
        (r'\b(graduate|grad|masters?|phd)\b', 500),
        (r'\b(\d)00[\s-]?level\b', None),  # "200-level" - extract from match
    ]
    for pattern, level in level_patterns:
        match = re.search(pattern, query_lower)
        if match:
            if level is None:
                # Extract from pattern like "200-level"
                result["level"] = int(match.group(1)) * 100
            else:
                result["level"] = level
            break
    
    # Detect query type
    first_semester_patterns = [
        r'\bu0\b',                          # McGill U0 (Foundation Program) → entry-level
        r'\bu1\b',                          # McGill U1 (first year) → entry-level courses
        r'foundation\s+program',
        r'first\s*(semester|year)',
        r'start(ing)?\s*(with|out)',
        r'begin(ning|ner)?',
        r'intro(ductory|duction)?',
        r'entry[\s-]?level',
        r'no\s*prereq',
        r'should\s+i\s+take\s+first',
        r'take\s+first',
    ]
    
    available_patterns = [
        # Only match when multiple courses are mentioned (e.g., "after COMP 250 and MATH 133")
        r'(after|with|having|completed?|done|finished|took)\s+[A-Z]{3,4}\s*\d{3}.+[A-Z]{3,4}\s*\d{3}',
        r'available\s+to\s+(me|take)',
    ]
    
    recommendation_patterns = [
        r'should\s+i\s+take',
        r'recommend',
        r'suggest',
        r'best\s+courses?',
        r'good\s+courses?',
        r'what\s+courses?\s+(should|to)',
    ]
    
    # Check for first semester / entry level queries
    if any(re.search(p, query_lower) for p in first_semester_patterns):
        result["type"] = "first_semester"
        return result
    
    # Check for "available after completing X" queries
    if any(re.search(p, query_lower) for p in available_patterns):
        result["type"] = "available"
        # Extract completed courses from query
        completed = re.findall(r'\b([A-Z]{3,4})\s*(\d{3}[A-Z]?)\b', query.upper())
        result["completed"] = [f"{dept} {num}" for dept, num in completed]
        return result
    
    # Check for level-based queries
    if result["level"]:
        result["type"] = "by_level"
        return result
    
    # Check for general recommendation queries
    if any(re.search(p, query_lower) for p in recommendation_patterns):
        result["type"] = "recommendation"
        return result

    # Even with no specific type, return partial result if we have dept/term info.
    # This lets hybrid_search inject relevant department courses into the LLM context
    # for queries like "What COMP courses are offered in fall?" that don't match
    # any specific pattern but clearly mention a department.
    if result["department"] or result["term"]:
        return result

    return None


# STEP 4️⃣ — Hybrid Search: Combine semantic + structured logic

def hybrid_search(query: str, dept: str = None, prereq_of: str = None, n_results: int = 50): # Hybrid Search (semantic + deterministic)
    """Combine semantic retrieval with my logic from the SQLAlchemy layer.
    
    Uses LLM to understand query intent and reformulate for better retrieval.
    
    Returns a list of course dicts. If ambiguous, the first result will have
    'needs_clarification': True and 'alternatives': [...] with course options.
    
    For planning queries, returns a list with 'is_planning_query': True and
    'planning_type' indicating the type of recommendation.
    """

    # ✅ NEW: Check for planning/recommendation queries first
    # BUT: skip planning detection if query mentions a specific course code
    # e.g., "Should I take COMP 307 first year?" should fetch COMP 307 and let the LLM reason,
    # NOT return a generic "entry-level courses" list
    # A "specific course" means a real department code (e.g. COMP, MATH) + number.
    # Filter out common English words that match the pattern (e.g. "WHAT 200-level").
    _raw_matches = _COURSE_ID_RE.findall(query.upper())
    has_specific_course = any(dept not in _DEPT_FALSE_POSITIVES for dept, _ in _raw_matches)
    planning = detect_planning_query(query) if not has_specific_course else None
    if planning and planning.get("type"):
        planning_type = planning["type"]
        department = planning.get("department") or dept
        term = planning.get("term")
        
        if planning_type == "first_semester":
            # Fetch entry-level courses and pass them as context to the LLM
            courses = get_entry_level_courses(department=department, term=term, limit=12)
            if courses:
                return [{"course_id": c["id"], "score": 0.0} for c in courses]

        elif planning_type == "by_level":
            level = planning.get("level", 100)
            if department:
                courses = get_courses_by_level(department=department, level=level, term=term, limit=12)
                if courses:
                    return [{"course_id": c["id"], "score": 0.0} for c in courses]

        elif planning_type == "available":
            completed = planning.get("completed", [])
            if completed:
                courses = get_available_courses(completed_courses=completed, department=department, term=term, limit=15)
                if courses:
                    return [{"course_id": c["id"], "score": 0.0} for c in courses]

        elif planning_type == "recommendation":
            if department:
                level = planning.get("level")
                if level and level >= 200:
                    courses = get_courses_by_level(department=department, level=level, term=term, limit=12)
                else:
                    courses = get_entry_level_courses(department=department, term=term, limit=12)
                if courses:
                    return [{"course_id": c["id"], "score": 0.0} for c in courses]

    # ✅ FIX 1: Extract course ID from query (may be ambiguous)
    course_id, alternatives = extract_course_id(query)


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
            result = {
                "course_id": course["id"],
                "score": 0.0,
                **course
            }
            # Add disambiguation info if ambiguous
            if alternatives and len(alternatives) > 1:
                result["needs_clarification"] = True
                result["alternatives"] = alternatives
            return [result]
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
    
    # ✅ FIX 5: If query mentions course IDs, fetch ALL of them directly
    all_course_ids = extract_all_course_ids(query)
    if all_course_ids:
        results = []
        for cid in all_course_ids:
            course = get_course_directly(cid)
            if course:
                results.append({
                    "course_id": course["id"],
                    "score": 0.0,
                    **course
                })
        if results:
            # Add disambiguation info if the first course was ambiguous
            if alternatives and len(alternatives) > 1:
                results[0]["needs_clarification"] = True
                results[0]["alternatives"] = alternatives
            return results
    
    # Fall back to semantic search for general queries
    combined = semantic_search(query, n_results)

    # Context enrichment: if a department was identified but no structured route matched,
    # inject that department's courses so the LLM has relevant data to reason with.
    # This handles vague or unusually phrased questions (e.g. "I'm a U1 geography student,
    # what should I take?" or "What COMP courses run in fall?") without needing a rigid
    # pattern for every possible phrasing. enrich_context() will attach full details
    # (prereqs, offered terms, descriptions) so the LLM can filter and recommend correctly.
    if planning and planning.get("department"):
        dept = planning.get("department")
        dept_courses = get_entry_level_courses(department=dept, limit=15)
        existing_ids = {r["course_id"] for r in combined}
        for c in dept_courses:
            if c["id"] not in existing_ids:
                combined.append({"course_id": c["id"], "score": 0.5})

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




