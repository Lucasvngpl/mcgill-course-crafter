
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


def format_planning_response(planning_data: dict, original_query: str) -> str:
    """Format a response for planning/recommendation queries."""
    planning_type = planning_data.get("planning_type")
    courses = planning_data.get("courses", [])
    department = planning_data.get("department")
    term = planning_data.get("term")
    level = planning_data.get("level")
    completed = planning_data.get("completed", [])
    
    if not courses:
        return "I couldn't find any courses matching your criteria. Try being more specific about the department or term."
    
    def format_offering(c):
        terms = []
        if c.get('offered_fall'): terms.append('Fall')
        if c.get('offered_winter'): terms.append('Winter')
        if c.get('offered_summer'): terms.append('Summer')
        return ', '.join(terms) if terms else 'Not specified'
    
    def format_course(c):
        prereqs = c.get('prereqs') or 'None'
        offering = format_offering(c)
        desc = c.get('description', '')
        # Truncate description
        if len(desc) > 150:
            desc = desc[:150] + '...'
        return f"**{c['id']}** ({c.get('title', 'Unknown')})\n   - Prereqs: {prereqs}\n   - Offered: {offering}\n   - {desc}"
    
    # Build response based on planning type
    if planning_type == "first_semester":
        dept_name = department or "various departments"
        term_str = f" in {term.capitalize()}" if term else ""
        header = f"Here are entry-level {dept_name} courses with no prerequisites{term_str}:\n\n"
        
        # Highlight recommended first courses
        recommended = []
        others = []
        for c in courses:
            course_num = int(c['id'].split()[1][:3]) if c['id'].split()[1][:3].isdigit() else 999
            if course_num < 300:  # 100-200 level
                recommended.append(c)
            else:
                others.append(c)
        
        response = header
        if recommended:
            response += "**Recommended for beginners:**\n\n"
            for c in recommended[:5]:
                response += format_course(c) + "\n\n"
        
        if others and len(recommended) < 3:
            response += "\n**Other options:**\n\n"
            for c in others[:3]:
                response += format_course(c) + "\n\n"
        
        response += "\n💡 **Tip:** For Computer Science, COMP 202 or COMP 208 are typically the first programming courses, followed by COMP 250."
        return response
    
    elif planning_type == "by_level":
        dept_name = department or "various departments"
        level_str = f"{level}-level" if level else ""
        term_str = f" offered in {term.capitalize()}" if term else ""
        header = f"Here are {level_str} {dept_name} courses{term_str}:\n\n"
        
        response = header
        for c in courses[:8]:
            response += format_course(c) + "\n\n"
        
        return response
    
    elif planning_type == "available":
        completed_str = ', '.join(completed) if completed else 'your courses'
        dept_filter = f" in {department}" if department else ""
        term_str = f" for {term.capitalize()}" if term else ""
        header = f"Based on completing {completed_str}, here are courses you can take{dept_filter}{term_str}:\n\n"
        
        response = header
        for c in courses[:10]:
            response += format_course(c) + "\n\n"
        
        if len(courses) > 10:
            response += f"\n...and {len(courses) - 10} more courses available."
        
        return response
    
    else:
        # Generic recommendation
        response = "Here are some courses that might interest you:\n\n"
        for c in courses[:6]:
            response += format_course(c) + "\n\n"
        return response


# 2️⃣ Prompt construction
def generate_answer(query):
    # Check for planning queries FIRST (before reverse_prereq detection)
    # This is done early because planning queries like "What can I take after COMP 250?"
    # should be handled differently than simple "which courses require X?" queries
    
    # Hybrid search handles planning detection internally
    retrieved_docs = hybrid_search(query)
    
    # Check if this is a planning query
    if retrieved_docs and retrieved_docs[0].get("is_planning_query"):
        return format_planning_response(retrieved_docs[0], query)
    
    # Now check for other query types
    query_type = detect_query_type(query)
    
    # Extract course ID
    match = re.search(r'\b([A-Z]{3,4})[\s\-]?(\d{3}[A-Z]?)\b', query.upper())
    
    if match and query_type == "reverse_prereq":
        course_id = f"{match.group(1)} {match.group(2)}"
        courses = get_courses_requiring(course_id)
        if courses:
            # Get titles for each course
            from rag_layer import get_course_directly
            course_list = []
            for cid in courses:
                course_info = get_course_directly(cid)
                if course_info and course_info.get('title') and 'Placeholder' not in course_info.get('title', ''):
                    course_list.append(f"{cid} ({course_info['title']})")
                else:
                    course_list.append(cid)
            # Also get the title of the source course
            source_info = get_course_directly(course_id)
            if source_info and source_info.get('title') and 'Placeholder' not in source_info.get('title', ''):
                source_str = f"{course_id} ({source_info['title']})"
            else:
                source_str = course_id
            return f"Courses that require {source_str}:\n• " + "\n• ".join(course_list)
        return f"No courses in the database list {course_id} as a prerequisite."
    
    # Check if we need clarification (ambiguous course title)
    if retrieved_docs and retrieved_docs[0].get("needs_clarification"):
        alternatives = retrieved_docs[0].get("alternatives", [])
        if alternatives:
            # Fetch titles for all alternatives
            alt_info = []
            for alt_id in alternatives:
                from rag_layer import get_course_directly
                alt_course = get_course_directly(alt_id)
                if alt_course:
                    alt_info.append(f"- {alt_id} ({alt_course.get('title', 'Unknown')}) - {alt_course.get('department', 'Unknown')}")
                else:
                    alt_info.append(f"- {alt_id}")
            
            return (
                f"I found multiple courses with that title. Please specify which one you mean by including the course code:\n\n"
                + "\n".join(alt_info)
                + f"\n\nFor example, you can ask: \"{query.replace('?', '')} (COMP 310)?\" or just ask about a specific course code."
            )

    # 2️⃣ Enrich retrieved docs
    top_ids = [r["course_id"] for r in retrieved_docs]
    context_docs = enrich_context(top_ids)

    # 3️⃣ Build context string with offering information
    def format_offering(d):
        """Format the offering terms for a course."""
        terms = []
        if d.get('offered_fall'):
            terms.append('Fall')
        if d.get('offered_winter'):
            terms.append('Winter')
        if d.get('offered_summer'):
            terms.append('Summer')
        return ', '.join(terms) if terms else 'Not specified'
    
    context = "\n\n".join(
        f"{d['id']} ({d.get('title', 'Unknown Title')}) - {d['credits']} credits, {d['department']}\n"
        f"Description: {d['description']}\n"
        f"Prereqs: {d['prereqs'] or 'None'}\n"
        f"Coreqs: {d['coreqs'] or 'None'}\n"
        f"Offered: {format_offering(d)}"
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

**RESPONSE FORMAT:**
- Always include both course code AND title: "COMP 250 (Introduction to Computer Science)"
- When listing prerequisites, format as: "Prerequisites: COMP 202 (Foundations of Programming)"
- Never show just the code without the name. Look at course title in context.

**IMPORTANT RULES FOR COREQUISITES:**
A corequisite is a course that must be taken concurrently with OR may have been taken prior to another course.

This means:
- If Course A is a corequisite for Course B, a student can take B if they:
  1. Take A at the SAME TIME as B, OR
  2. Have ALREADY completed A in a previous semester

- Corequisites are NOT prerequisites. A student does NOT need to complete the corequisite before taking the course.

**Example:**
- COMP 273 has COMP 206 as a corequisite (not a prerequisite)
- This means: You can take COMP 273 if you're taking COMP 206 at the same time, OR if you've already completed COMP 206
- You do NOT need to finish COMP 206 before starting COMP 273

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
        
    
