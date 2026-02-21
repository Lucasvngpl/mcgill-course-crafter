import pathlib
import os
import re
from dotenv import load_dotenv
from deterministic_logic import get_courses_requiring

# Load .env from the backend directory (works locally; on Railway, env vars are set in dashboard)
env_path = pathlib.Path(__file__).parent / ".env"
load_dotenv(env_path, override=True)
from langchain_openai import ChatOpenAI
from rag_layer import hybrid_search, enrich_context, set_llm

# quick sanity check (do NOT print the key in logs; just fail loudly if missing)
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY not set in environment")

# 1️⃣ Initialize model
llm = ChatOpenAI(model="gpt-5", temperature=0.7, openai_api_key=os.getenv("OPENAI_API_KEY"))

# Set LLM in rag_layer for query understanding
set_llm(llm)

# Course nickname mapping
COURSE_ALIASES = {
    # Math courses
    "calc 1": "MATH 140", "calculus 1": "MATH 140",
    "calc 2": "MATH 141", "calculus 2": "MATH 141",
    "calc 3": "MATH 222", "calculus 3": "MATH 222",
    "linear algebra": "MATH 133", "lin alg": "MATH 133",
    "discrete math": "MATH 240", "discrete": "MATH 240",
    "ode": "MATH 323", "pde": "MATH 324",
    "real analysis": "MATH 242",
    # CS courses
    "intro to cs": "COMP 202", "intro cs": "COMP 202",
    "data structures": "COMP 250",
    "algorithms": "COMP 251",
    "operating systems": "COMP 310", "os": "COMP 310",
    "databases": "COMP 421",
    "ai": "COMP 424",
    "machine learning": "COMP 551", "ml": "COMP 551",
    "compilers": "COMP 520",
    "computer graphics": "COMP 557", "graphics": "COMP 557",
}

def replace_aliases(query: str) -> str:
    """Replace course nicknames with actual course codes."""
    result = query
    # Sort by length (longest first) to avoid partial replacements
    for alias in sorted(COURSE_ALIASES.keys(), key=len, reverse=True):
        pattern = r'\b' + re.escape(alias) + r'\b'
        if re.search(pattern, result, re.IGNORECASE):
            result = re.sub(pattern, COURSE_ALIASES[alias], result, flags=re.IGNORECASE)
    return result


def clean_title(title: str, course_id: str = "") -> str:
    """Return a usable title, replacing placeholder/missing titles with empty string."""
    if not title or title.startswith("Placeholder for") or title == "N/A":
        return ""
    return title


def format_course_label(course_id: str, title: str) -> str:
    """Format a course as 'CODE (Title)' or just 'CODE' if title is placeholder/missing."""
    clean = clean_title(title, course_id)
    if clean:
        return f"{course_id} ({clean})"
    return course_id


def detect_query_type(query: str):
    """Detect the type of query user is asking."""
    query_lower = query.lower()
    
    # Prerequisite chain question: "should i take X before Y"
    prereq_chain_patterns = [
        r'should i take .+ before',
        r'do i need .+ before',
        r'is .+ required (for|before)',
        r'take .+ before .+\?',
        r'need .+ (for|to take)',
    ]
    for pattern in prereq_chain_patterns:
        if re.search(pattern, query_lower):
            return "prereq_chain"
    
    # Reverse prereq patterns
    reverse_patterns = [
        r"what can i take after",
        r"what should i take after",
        r"what courses? require",
        r"i finished .+,? what'?s next",
        r"after .+,? what",
        r"courses? that need",
        r"what('s| is) next after",
        r"take after",
    ]
    for pattern in reverse_patterns:
        if re.search(pattern, query_lower):
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
def generate_answer(query, user_context=None):
    # user_context is an optional string like "[STUDENT PROFILE]\nYear: U1\nMajor: CS\n..."
    # When present, it gets injected into the LLM prompt so responses are personalized
    # When None (anonymous user), the LLM responds generically

    # Replace course nicknames with actual codes first
    query = replace_aliases(query)
    
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
    
    # Handle "should I take X before Y" questions
    if query_type == "prereq_chain":
        codes = re.findall(r'\b([A-Z]{3,4})[\s\-]?(\d{3}[A-Z]?)\b', query.upper())
        if len(codes) >= 2:
            first_course = f"{codes[0][0]} {codes[0][1]}"
            second_course = f"{codes[1][0]} {codes[1][1]}"
            
            from rag_layer import get_course_directly
            target = get_course_directly(second_course)
            first_info = get_course_directly(first_course)
            
            if not target:
                return f"I couldn't find **{second_course}** in the database. Please check the course code."
            
            prereqs = target.get('prereqs', '') or ''
            coreqs = target.get('coreqs', '') or ''
            target_title = target.get('title', '')
            first_title = first_info.get('title', '') if first_info else ''
            
            target_str = format_course_label(second_course, target_title)
            first_str = format_course_label(first_course, first_title)
            
            # Check if prereq AND coreq data is missing
            if not prereqs and not coreqs:
                return (
                    f"I don't have prerequisite or corequisite information for **{target_str}**.\n\n"
                    f"The course exists in the database but the requirement data wasn't scraped. "
                    f"Please check the [McGill eCalendar](https://www.mcgill.ca/study/2024-2025/courses/{second_course.replace(' ', '-').lower()}) directly."
                )
            
            # Check if first course is in prereqs or coreqs
            first_code_pattern = first_course.replace(' ', r'[\s\-]?')
            is_prereq = re.search(first_code_pattern, prereqs, re.IGNORECASE) if prereqs else False
            is_coreq = re.search(first_code_pattern, coreqs, re.IGNORECASE) if coreqs else False
            
            if is_prereq:
                return (
                    f"**Yes**, {first_str} is a prerequisite for {target_str}.\n\n"
                    f"**Prerequisites for {second_course}:** {prereqs}"
                )
            elif is_coreq:
                return (
                    f"**{first_str} is a corequisite** (not prerequisite) for {target_str}.\n\n"
                    f"This means you can take them at the same time, OR complete {first_str} first.\n\n"
                    f"**Corequisites for {second_course}:** {coreqs}"
                    + (f"\n**Prerequisites for {second_course}:** {prereqs}" if prereqs else "")
                )
            else:
                response = f"**No**, {first_str} is not listed as a direct prerequisite for {target_str}.\n\n"
                if prereqs:
                    response += f"**Prerequisites for {second_course}:** {prereqs}\n"
                if coreqs:
                    response += f"**Corequisites for {second_course}:** {coreqs}"
                if not prereqs and not coreqs:
                    response += f"{second_course} has no listed prerequisites or corequisites."
                return response
    
    if match and query_type == "reverse_prereq":
        course_id = f"{match.group(1)} {match.group(2)}"
        courses = get_courses_requiring(course_id)
        if courses:
            # Get titles for each course (simple format)
            from rag_layer import get_course_directly
            course_list = []
            for cid in courses:
                course_info = get_course_directly(cid)
                course_list.append(f"• {format_course_label(cid, course_info.get('title', '') if course_info else '')}")

            # Get source course title
            source_info = get_course_directly(course_id)
            source_str = format_course_label(course_id, source_info.get('title', '') if source_info else '')
            
            return f"After completing {source_str}, you can take:\n\n" + "\n".join(course_list)
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

    # 2️⃣ Enrich retrieved docs + fetch prerequisite courses for fuller context
    top_ids = [r["course_id"] for r in retrieved_docs]
    context_docs = enrich_context(top_ids)

    # Also fetch any courses mentioned in prereq/coreq text so the LLM can reason
    # about the full prerequisite chain (e.g., "Should I take X in first year?")
    from rag_layer import extract_all_course_ids, get_course_directly
    existing_ids = set(d["id"] for d in context_docs)
    extra_ids = set()
    for d in context_docs:
        for field in [d.get("prereqs", ""), d.get("coreqs", "")]:
            if field:
                for cid in extract_all_course_ids(field):
                    if cid not in existing_ids:
                        extra_ids.add(cid)
    if extra_ids:
        extra_docs = enrich_context(list(extra_ids))
        context_docs.extend(extra_docs)

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
        f"{format_course_label(d['id'], d.get('title', ''))} - {d['credits']} credits, {d['department']}\n"
        f"Description: {d['description'] if d.get('description') and d['description'] != 'N/A' else 'No description available.'}\n"
        f"Prereqs: {d['prereqs'] or 'None'}\n"
        f"Coreqs: {d['coreqs'] or 'None'}\n"
        f"Offered: {format_offering(d)}"
        for d in context_docs
    )
    prompt = f"""You are a helpful academic assistant for McGill University.
Use only the context below to answer the student's question.

[COMMON COURSE NICKNAMES]
Students often use nicknames for courses. Here are the mappings:
- "Calc 1" / "Calculus 1" = MATH 140
- "Calc 2" / "Calculus 2" = MATH 141  
- "Calc 3" / "Calculus 3" = MATH 222
- "Linear Algebra" / "Lin Alg" = MATH 133
- "Discrete Math" / "Discrete" = MATH 240
- "ODE" = MATH 323
- "PDE" = MATH 324
- "Real Analysis" = MATH 242
- "Intro to CS" / "Intro CS" = COMP 202
- "Data Structures" = COMP 250
- "Algorithms" = COMP 251
- "Operating Systems" / "OS" = COMP 310
- "Databases" = COMP 421
- "AI" = COMP 424
- "Machine Learning" / "ML" = COMP 551
- "Compilers" = COMP 520
- "Computer Graphics" / "Graphics" = COMP 557

When a student uses a nickname, treat it as the corresponding course code.

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
- When the course title is available, include both code AND title: "COMP 250 (Introduction to Computer Science)"
- When a course has no title listed in the context (just a course code with no parentheses), use the code only — do NOT say "title not provided" or make up a title.
- When listing prerequisites, format as: "Prerequisites: COMP 202 (Foundations of Programming)"

**TIMING & YEAR QUESTIONS:**
When a student asks "should I take X in first year or second year?" or "when should I take X?":
- Look at the course's prerequisites and corequisites
- Think about when those prereqs are typically completed (100-level = first year, 200-level = second year, etc.)
- Give a specific recommendation based on the prereq chain, e.g.: "COMP 307 requires COMP 206 and COMP 250, which are typically first-year courses. So second year is the earliest you could take it."
- Do NOT list unrelated entry-level courses. Focus on the specific course asked about.

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

{f"{user_context}" + chr(10) + chr(10) if user_context else ""}Question: {query}
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


