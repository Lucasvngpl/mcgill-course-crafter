# This is a simple Python API using FastAPI.
# Later you’ll build a TypeScript React frontend that talks to this Python API.
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from qa_agent import generate_answer
from db_connection import Session as DBSession
from db_setup import Course


app = FastAPI(title="CourseCraft RAG API", version="0.1")

# Define the request body schema
class QueryRequest(BaseModel):
    question: str

# Add CORS middleware - allow your Vercel frontend
# Add CORS middleware - allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/query")
async def handle_query(request: QueryRequest):
    try:
        answer = generate_answer(request.question)  # qa_agent.generate_answer takes 1 arg
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

