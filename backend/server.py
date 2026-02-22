# This is a simple Python API using FastAPI.
# Later build a TypeScript React frontend that talks to this Python API.
import os
import pathlib
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import jwt  # PyJWT: decodes and verifies JWT tokens
from jwt import PyJWKClient  # Fetches public keys from Supabase's JWKS endpoint
from qa_agent import generate_answer
from db_connection import Session as DBSession
from db_setup import Course, UserProfile, UserCourse
from dotenv import load_dotenv

load_dotenv()


import threading

# Track whether the vector store is ready (for /query to check)
vector_store_ready = threading.Event()


def _build_vector_store_sync():
    """Build ChromaDB in a background thread so the server can start immediately."""
    try:
        from rag_layer import build_vector_store
        build_vector_store()
        print("[STARTUP] Vector store built successfully")
    except Exception as e:
        print(f"[STARTUP] ERROR building vector store: {e}")
    finally:
        vector_store_ready.set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup: build ChromaDB vector store if it doesn't exist yet
    # (Railway has an ephemeral filesystem, so this runs on every deploy)
    chroma_sqlite = pathlib.Path(__file__).parent / "chroma_db" / "chroma.sqlite3"
    if not chroma_sqlite.exists():
        print("[STARTUP] ChromaDB not found, building in background...")
        thread = threading.Thread(target=_build_vector_store_sync, daemon=True)
        thread.start()
    else:
        print("[STARTUP] ChromaDB already exists, skipping build")
        vector_store_ready.set()
    yield


app = FastAPI(title="CourseCraft RAG API", version="0.1", lifespan=lifespan)

# JWKS (JSON Web Key Set) client — fetches the public key from Supabase
# Your Supabase project publishes its public key at this URL
# PyJWT uses it to verify ES256-signed tokens (newer Supabase projects use ES256, not HS256)
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mwfrlwbowmkrobyvuqdc.supabase.co")
jwks_client = PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")

# Define the request body schema
class QueryRequest(BaseModel):
    question: str


def get_user_id_from_token(request: Request) -> str | None:
    """
    Extract the user ID from the Supabase JWT in the Authorization header.
    Returns None if no token or invalid token (anonymous user).
    Does NOT raise errors — auth is optional for the /query endpoint.

    How it works:
    1. Frontend sends: Authorization: Bearer <jwt-token>
    2. We decode the JWT using our Supabase project's secret key
    3. The decoded payload contains 'sub' (subject) = the user's UUID
    4. We return that UUID so the endpoint can load user-specific data
    """
    # Get the Authorization header (e.g., "Bearer eyJhbG...")
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None  # No token = anonymous user, that's fine

    # Extract just the token part (everything after "Bearer ")
    token = auth_header.split(" ")[1]

    try:
        # Step 1: Fetch the correct public key from Supabase's JWKS endpoint
        # The JWKS endpoint publishes the ES256 public key that matches the token's "kid" header
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Step 2: Decode and verify the JWT using that public key
        # algorithms=["ES256"] — newer Supabase projects sign tokens with ES256 (elliptic curve)
        # audience="authenticated" ensures this token is for a logged-in user
        payload = jwt.decode(
            token,
            signing_key.key,  # The actual public key object
            algorithms=["ES256"],
            audience="authenticated",
        )
        # 'sub' is the standard JWT claim for subject = the user's UUID
        return payload.get("sub")
    except Exception as e:
        print(f"[AUTH] JWT decode error: {e}")  # Keep this one for monitoring
        return None  # Invalid/expired token = treat as anonymous


def build_user_context(user_id: str) -> str | None:
    """
    Load the user's profile and courses from the database,
    and format them as a text string to inject into the LLM prompt.

    Returns None if user has no profile yet.
    """
    with DBSession() as session:
        # Load profile
        profile = session.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()

        if not profile:
            return None  # User exists in auth but hasn't done onboarding yet

        # Load completed/in-progress courses
        courses = session.query(UserCourse).filter(
            UserCourse.user_id == user_id,
            UserCourse.status.in_(["completed", "in_progress"])
        ).all()

        # Build context string that gets prepended to the LLM prompt
        lines = ["[STUDENT PROFILE]"]
        if profile.year_standing:
            lines.append(f"Year: {profile.year_standing}")
        if profile.major:
            lines.append(f"Major: {profile.major}")
        if profile.minor:
            lines.append(f"Minor: {profile.minor}")
        if profile.interests:
            lines.append(f"Interests: {profile.interests}")
        if profile.constraints:
            lines.append(f"Constraints: {profile.constraints}")

        if courses:
            # Group by status
            completed = [c.course_id for c in courses if c.status == "completed"]
            in_progress = [c.course_id for c in courses if c.status == "in_progress"]
            if completed:
                lines.append(f"Completed Courses: {', '.join(completed)}")
            if in_progress:
                lines.append(f"Currently Taking: {', '.join(in_progress)}")

        return "\n".join(lines)


# Add CORS middleware - allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/query")
async def handle_query(request: Request, body: QueryRequest):
    # Wait up to 120s for vector store to finish building (first deploy only)
    if not vector_store_ready.wait(timeout=120):
        raise HTTPException(status_code=503, detail="Server is still starting up. Please try again in a minute.")
    try:
        # Try to identify the user (returns None for anonymous users)
        user_id = get_user_id_from_token(request)

        # If user is signed in, load their profile for personalized responses
        user_context = None
        if user_id:
            user_context = build_user_context(user_id)

        # Pass user context to the LLM (None for anonymous = no personalization)
        answer = generate_answer(body.question, user_context=user_context)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/courses/{course_id}")
def get_course(course_id: str):
    """Retrieve course details by course ID."""
    

    with DBSession() as session:
        course = session.query(Course).filter(Course.id == course_id).first()
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        return {
            "id": course.id,
            "title": course.title,
            "description": course.description,
            "credits": float(course.credits),
            "offered_by": course.offered_by,
            "offered_fall": course.offered_fall,
            "offered_winter": course.offered_winter,
            "offered_summer": course.offered_summer,
            "prereq_text": course.prereq_text,
            "coreq_text": course.coreq_text,
            
            # Add other relevant fields as needed
        }
    
@app.get("/") # Root endpoint to check if the API is running
def root():
    return {"message": "CourseCraft API is running!"}

# more get endpoints can be added here as needed
# @app.get("/courses/{course_id}")
# def get_course(course_id: str):
# do this one yourself on ipad

