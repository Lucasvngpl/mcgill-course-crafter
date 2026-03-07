# qa_agent.py
#
# This file is the "brain" of the system. It takes a student's question and
# produces a final answer by orchestrating three main steps:
#
#   1. RETRIEVE  — ask the vector store (ChromaDB) for relevant courses/programs
#   2. AUGMENT   — enrich that raw retrieval with full course details from PostgreSQL
#   3. GENERATE  — assemble a prompt and ask GPT-4o-mini to write the final answer
#
# This pattern is called RAG: Retrieval-Augmented Generation. The idea is that
# instead of asking the LLM to answer from memory (which hallucinate), we first
# find relevant facts ourselves and paste them into the prompt as context. The LLM
# then just has to read and summarize — a task it's very good at.

import pathlib
import os
import re
from dotenv import load_dotenv
from deterministic_logic import get_courses_requiring


# ─────────────────────────────────────────────────────────────────────────────
# SETUP: Load environment variables and initialize the LLM
#
# dotenv reads key=value pairs from the .env file into os.environ so the rest
# of the code can call os.getenv("KEY") without hardcoding secrets.
# ─────────────────────────────────────────────────────────────────────────────

# Load .env from the backend directory (works locally; on Railway, env vars are set in dashboard)
env_path = pathlib.Path(__file__).parent / ".env"
load_dotenv(env_path, override=True)
from langchain_openai import ChatOpenAI
from rag_layer import hybrid_search, enrich_context, set_llm

# Quick sanity check — fail loudly at startup rather than silently mid-request
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY not set in environment")

# ChatOpenAI wraps the OpenAI API in a LangChain interface.
# temperature=0.1 keeps answers factual and consistent (0 = deterministic, 1 = creative).
# We use gpt-4o-mini because it's fast and cheap — sufficient for structured Q&A.
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, openai_api_key=os.getenv("OPENAI_API_KEY"))

# Share our LLM with rag_layer so it can use it for query reformulation (e.g. expanding
# "calc 3" → "MATH 222") without needing its own separate model instance.
set_llm(llm)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER UTILITIES
#
# Small, focused functions used throughout generate_answer(). Keeping them
# separate makes the main function easier to read.
# ─────────────────────────────────────────────────────────────────────────────

def clean_title(title: str, course_id: str = "") -> str:
    """Return a usable title, or empty string if it's a placeholder/missing.

    Some courses in the DB have a title like "Placeholder for MATH 318" because
    we scraped the course code but couldn't find the title. We treat those the
    same as having no title, so the LLM doesn't repeat the placeholder text.
    """
    if not title or title.startswith("Placeholder for") or title == "N/A":
        return ""
    return title.rstrip(".")


def format_course_label(course_id: str, title: str) -> str:
    """Format a course as 'CODE (Title)' or just 'CODE' if title is missing.

    Example: format_course_label("COMP 250", "Introduction to CS") → "COMP 250 (Introduction to CS)"
    Example: format_course_label("MATH 318", "")                   → "MATH 318"
    """
    clean = clean_title(title, course_id)
    if clean:
        return f"{course_id} ({clean})"
    return course_id


def _retrieve_comparison_programs(query: str) -> list | None:
    """When the student asks to compare two programs, retrieve targeted program chunks for each.

    For 'What's the difference between CS Honours and CS Major?', this runs:
      - semantic_search('CS Honours program requirements', n_results=5)
      - semantic_search('CS Major program requirements', n_results=5)
    and returns the top program chunk from each search.

    This avoids the problem of a single generic search returning 50 loosely
    related programs (Math-CS Honours, Stats-CS, Physics-CS, etc.) which confuses
    the LLM into comparing the wrong pair.

    Returns a list of up to 2 retrieved_doc dicts (each has 'program_text', 'program_name', etc.)
    or None if this doesn't look like a comparison query.
    """
    # Try several comparison phrasings to extract the two program names.
    # We try most specific patterns first to avoid over-matching.
    patterns = [
        # "difference between X and Y"
        r'\bbetween\s+(.+?)\s+\band\b\s+(.+?)(?:\?|$)',
        # "what extra does X require that/vs Y"
        r'\b(?:extra|more|different).{0,20}?\b((?:CS|[A-Z]\w+)\s+(?:Honours?|Major|Minor|Program|BSc|BA))\b.{0,20}?\b(?:vs\.?|versus|than|that|compared to)\b.{0,10}?\b((?:CS|[A-Z]\w+)\s+(?:Honours?|Major|Minor|Program|BSc|BA))\b',
        # "X vs Y"
        r'\b((?:CS|[A-Z]\w+)\s+(?:Honours?|Major|Minor))\s+(?:vs\.?|versus)\s+((?:CS|[A-Z]\w+)\s+(?:Honours?|Major|Minor))',
    ]
    m = None
    for pat in patterns:
        m = re.search(pat, query, re.IGNORECASE)
        if m:
            break

    if not m:
        return None

    term_a = m.group(1).strip()
    term_b = m.group(2).strip()

    from rag_layer import semantic_search as _sem_search

    def _top_program(term: str) -> dict | None:
        """Find the best-matching program chunk for a query term."""
        results = _sem_search(f"{term} program requirements", n_results=5)
        for r in results:
            if r.get("course_id", "").startswith("program::") and r.get("program_text"):
                return r
        return None

    prog_a = _top_program(term_a)
    prog_b = _top_program(term_b)

    results = [r for r in [prog_a, prog_b] if r]
    return results if results else None


def detect_query_type(query: str):
    """Classify the question as 'prereq_chain', 'reverse_prereq', or generic 'prereq'.

    Why classify at all? Some questions have a clear, deterministic answer that we can
    compute directly from the database without involving the LLM. Routing those to the
    right handler gives faster, more reliable answers.

    - prereq_chain:   "Should I take COMP 202 before COMP 250?" → check if A is prereq of B
    - reverse_prereq: "What can I take after COMP 250?"         → find all courses that require A
    - prereq:         Everything else                            → fall through to the LLM
    """
    query_lower = query.lower()

    # These patterns catch "should I take X before Y" style questions
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

    # These patterns catch "what comes after X" style questions
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


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE: generate_answer(query, user_context)
#
# This is the only function called from server.py. It returns a dict:
#   { "answer": "...", "sources": [...] }
#
# user_context is an optional string injected into the prompt when the student
# is signed in. It looks like "[STUDENT PROFILE]\nYear: U1\nMajor: CS\n...".
# When it's None (anonymous user), the LLM answers generically.
# ─────────────────────────────────────────────────────────────────────────────

def generate_answer(query, user_context=None):

    # ── STEP 1: RETRIEVE ────────────────────────────────────────────────────
    # hybrid_search() queries ChromaDB (vector similarity) and supplements the
    # results with deterministic SQL logic (e.g. department filters, entry-level
    # courses). It returns a list of dicts, each with at least a "course_id" key.
    #
    # We run this BEFORE query type detection because the planner inside
    # hybrid_search also infers things like department intent (e.g. "COMP courses
    # in fall") that we'd otherwise miss.
    retrieved_docs = hybrid_search(query)

    # ── STEP 2: QUERY ROUTING ───────────────────────────────────────────────
    # For a handful of question shapes we can answer deterministically — no LLM
    # needed. We check those here and return early if one matches.
    # This is faster, cheaper, and avoids hallucinations for simple lookups.
    query_type = detect_query_type(query)

    # Extract the first course code mentioned in the query (e.g. "COMP 250")
    # re.search scans the uppercased query for a DEPT + NUMBER pattern.
    match = re.search(r'\b([A-Z]{3,4})[\s\-]?(\d{3}[A-Z]?)\b', query.upper())
    course_id = f"{match.group(1)} {match.group(2)}" if match else ""

    # ── HANDLER A: "Should I take X before Y?" ──────────────────────────────
    # We look up both courses directly in the DB and check whether one appears
    # in the other's prereq/coreq text. No LLM needed — it's a string search.
    if query_type == "prereq_chain":
        codes = re.findall(r'\b([A-Z]{3,4})[\s\-]?(\d{3}[A-Z]?)\b', query.upper())
        if len(codes) >= 2:
            first_course = f"{codes[0][0]} {codes[0][1]}"
            second_course = f"{codes[1][0]} {codes[1][1]}"

            from rag_layer import get_course_directly
            target = get_course_directly(second_course)
            first_info = get_course_directly(first_course)

            if not target:
                return {"answer": f"I couldn't find **{second_course}** in the database. Please check the course code.", "sources": []}

            prereqs = target.get('prereqs', '') or ''
            coreqs = target.get('coreqs', '') or ''
            target_title = target.get('title', '')
            first_title = first_info.get('title', '') if first_info else ''

            target_str = format_course_label(second_course, target_title)
            first_str = format_course_label(first_course, first_title)

            if not prereqs and not coreqs:
                return {"answer": (
                    f"I don't have prerequisite or corequisite information for **{target_str}**.\n\n"
                    f"The course exists in the database but the requirement data wasn't scraped. "
                    f"Please check the [McGill eCalendar](https://www.mcgill.ca/study/2024-2025/courses/{second_course.replace(' ', '-').lower()}) directly."
                ), "sources": []}

            # Build a regex that matches "COMP 202" or "COMP-202" in the prereq text
            first_code_pattern = first_course.replace(' ', r'[\s\-]?')
            is_prereq = re.search(first_code_pattern, prereqs, re.IGNORECASE) if prereqs else False
            is_coreq = re.search(first_code_pattern, coreqs, re.IGNORECASE) if coreqs else False

            if is_prereq:
                return {"answer": (
                    f"**Yes**, {first_str} is a prerequisite for {target_str}.\n\n"
                    f"**Prerequisites for {second_course}:** {prereqs}"
                ), "sources": []}
            elif is_coreq:
                return {"answer": (
                    f"**{first_str} is a corequisite** (not prerequisite) for {target_str}.\n\n"
                    f"This means you can take them at the same time, OR complete {first_str} first.\n\n"
                    f"**Corequisites for {second_course}:** {coreqs}"
                    + (f"\n**Prerequisites for {second_course}:** {prereqs}" if prereqs else "")
                ), "sources": []}
            else:
                text = f"**No**, {first_str} is not listed as a direct prerequisite for {target_str}.\n\n"
                if prereqs:
                    text += f"**Prerequisites for {second_course}:** {prereqs}\n"
                if coreqs:
                    text += f"**Corequisites for {second_course}:** {coreqs}"
                if not prereqs and not coreqs:
                    text += f"{second_course} has no listed prerequisites or corequisites."
                return {"answer": text, "sources": []}

    # ── HANDLER B: "What can I take after X?" ───────────────────────────────
    # get_courses_requiring() does a SQL query: find all courses where course_id
    # appears in their prereq_text. Pure DB lookup, no LLM.
    if match and query_type == "reverse_prereq":
        course_id = f"{match.group(1)} {match.group(2)}"
        courses = get_courses_requiring(course_id)
        if courses:
            from rag_layer import get_course_directly
            course_list = []
            for cid in courses:
                course_info = get_course_directly(cid)
                course_list.append(f"• {format_course_label(cid, course_info.get('title', '') if course_info else '')}")

            source_info = get_course_directly(course_id)
            source_str = format_course_label(course_id, source_info.get('title', '') if source_info else '')

            return {"answer": f"After completing {source_str}, you can take:\n\n" + "\n".join(course_list), "sources": []}
        return {"answer": f"No courses in the database list {course_id} as a prerequisite.", "sources": []}

    # ── HANDLER C: Ambiguous course title ───────────────────────────────────
    # hybrid_search flags this when multiple courses share the same title (e.g.
    # "Introduction to Programming" could be COMP 202 or COMP 204). We ask the
    # student to be more specific instead of guessing.
    if retrieved_docs and retrieved_docs[0].get("needs_clarification"):
        alternatives = retrieved_docs[0].get("alternatives", [])
        if alternatives:
            alt_info = []
            for alt_id in alternatives:
                from rag_layer import get_course_directly
                alt_course = get_course_directly(alt_id)
                if alt_course:
                    alt_info.append(f"- {alt_id} ({alt_course.get('title', 'Unknown')}) - {alt_course.get('department', 'Unknown')}")
                else:
                    alt_info.append(f"- {alt_id}")

            return {"answer": (
                f"I found multiple courses with that title. Please specify which one you mean by including the course code:\n\n"
                + "\n".join(alt_info)
                + f"\n\nFor example, you can ask: \"{query.replace('?', '')} (COMP 310)?\" or just ask about a specific course code."
            ), "sources": []}

    # ── STEP 3: SEPARATE PROGRAMS FROM COURSES ──────────────────────────────
    # retrieved_docs is a mixed list — it may contain both course chunks (IDs like
    # "COMP-250") and program chunks (IDs like "program::cs-honours-bsc"). We split
    # them here because they need different handling:
    #
    # - Program chunks already contain their full prose text in the search result
    #   (no extra DB lookup needed). We collect those prose strings and inject them
    #   directly into the prompt under [PROGRAM REQUIREMENTS].
    #
    # - Course chunks are just IDs — we need to query PostgreSQL to get the title,
    #   credits, prereqs, etc. That happens in enrich_context() below.
    from rag_layer import extract_all_course_ids, get_course_directly

    program_texts = []    # full prose paragraphs from institutional program scrapes
    course_result_ids = []  # bare course IDs to be enriched from the DB

    # For comparison queries ("difference between X and Y"), do two targeted program
    # retrievals instead of using the single mixed search result. This ensures we fetch
    # exactly the programs the student named, not whatever happens to rank highest overall.
    comparison_retrieved = _retrieve_comparison_programs(query)

    if comparison_retrieved:
        # Use only the two targeted program chunks for the comparison
        for r in comparison_retrieved:
            prog_text = r.get("program_text", "")
            if prog_text:
                program_texts.append(prog_text)
        # Still populate course_result_ids from the general search for supporting context
        for r in retrieved_docs:
            cid = r.get("course_id", "")
            if not cid.startswith("program::"):
                course_result_ids.append(cid)
        # Replace retrieved_docs with the targeted programs for the sources section (step 8)
        retrieved_docs = comparison_retrieved + [r for r in retrieved_docs if not r.get("course_id", "").startswith("program::")]
    else:
        # General query: cap program chunks at 5 to avoid overwhelming the LLM with
        # dozens of loosely-related programs. retrieved_docs is sorted by relevance
        # (lower score = more similar), so the first N are the best matches.
        MAX_PROGRAM_CONTEXTS = 5
        program_count = 0
        for r in retrieved_docs:
            cid = r.get("course_id", "")
            if cid.startswith("program::"):
                prog_text = r.get("program_text", "")
                if prog_text and program_count < MAX_PROGRAM_CONTEXTS:
                    program_texts.append(prog_text)
                    program_count += 1
            else:
                course_result_ids.append(cid)

    # Save the directly-retrieved course IDs BEFORE we expand context below.
    # The sources shown in the thinking header should represent what the system
    # actually searched for — not the hundreds of support docs we fetch later
    # to help the LLM reason about prereq chains and program requirements.
    direct_course_source_ids = list(course_result_ids)

    # ── STEP 4: ENRICH CONTEXT ──────────────────────────────────────────────
    # enrich_context() takes a list of course IDs and fetches their full details
    # from PostgreSQL: title, description, credits, prereqs, coreqs, offered terms.
    # This is what gets pasted into the [COURSES] section of the LLM prompt.
    context_docs = enrich_context(course_result_ids)

    # 4a. EXPAND: fetch course details for every course mentioned in program prose.
    #
    # Program requirement pages list course codes like "COMP 252" inline. Without
    # this step, the LLM only sees "COMP 252" as a bare code — no title, no prereqs.
    # By fetching those courses from the DB, the LLM gets their full metadata.
    #
    # BUG NOTE: extract_all_course_ids() returns "MATH 318" (space-separated), but
    # the DB stores course IDs as "MATH-318" (hyphen). We normalize here so the
    # DB lookup actually finds the row.
    existing_ids = set(d["id"] for d in context_docs)
    program_course_ids = set()
    for prog_text in program_texts:
        for cid in extract_all_course_ids(prog_text):
            # extract_all_course_ids returns "COMP 252" (space), which matches the DB format
            if cid not in existing_ids:
                program_course_ids.add(cid)
    if program_course_ids:
        program_course_docs = enrich_context(list(program_course_ids))
        context_docs.extend(program_course_docs)
        existing_ids.update(d["id"] for d in program_course_docs)

        # Inject titles directly into the program prose text.
        #
        # Without this, the program prose says "...COMP 252, COMP 273..." and the LLM
        # has to cross-reference the [COURSES] section to find titles — which it often
        # skips. By replacing bare codes with "COMP 252 (Honours Algorithms...)" right
        # here, the LLM sees titles exactly where it reads the requirements.
        #
        # We only replace codes that have a real title and aren't already followed by "(".
        code_to_label = {}
        for d in program_course_docs:
            course_id = d["id"]   # already "COMP 252" (space) — that's the DB format
            label = format_course_label(course_id, d.get("title", ""))
            if label != course_id:            # skip courses with no real title
                code_to_label[course_id] = label

        if code_to_label:
            # Build one regex that matches any of the bare codes not already in parens.
            # Sorting by length (longest first) prevents "COMP 25" matching before "COMP 252".
            pattern = r'\b(' + '|'.join(re.escape(c) for c in sorted(code_to_label, key=len, reverse=True)) + r')\b(?!\s*\()'
            program_texts = [
                re.sub(pattern, lambda m: code_to_label[m.group(0)], text)
                for text in program_texts
            ]

    # 4b. EXPAND: fetch courses referenced inside prereq/coreq text.
    #
    # Only do this for non-program queries (e.g. simple prereq questions). When
    # program chunks are in the context we've already fetched all relevant courses
    # via step 4a, and fetching prereqs of those would balloon to hundreds of extra
    # courses and exceed the model's context limit.
    if not program_texts:
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

    # ── STEP 5: ASSEMBLE THE CONTEXT STRING ─────────────────────────────────
    # We format context_docs into readable text blocks and paste them into the
    # prompt. The LLM is instructed to answer ONLY from this context — not from
    # its training knowledge. This prevents hallucination.

    def format_offering(d):
        """Format the offering terms for a course (e.g. 'Fall, Winter')."""
        terms = []
        if d.get('offered_fall'):
            terms.append('Fall')
        if d.get('offered_winter'):
            terms.append('Winter')
        if d.get('offered_summer'):
            terms.append('Summer')
        return ', '.join(terms) if terms else 'Not specified'

    # Each course becomes one readable block. format_course_label strips placeholder
    # titles so a course with no real title appears as just "COMP 314" (no parenthetical).
    course_context = "\n\n".join(
        f"{format_course_label(d['id'], d.get('title', ''))} - {d['credits']} credits, {d['department']}\n"
        f"Description: {d['description'] if d.get('description') and d['description'] != 'N/A' else 'No description available.'}\n"
        f"Prereqs: {d['prereqs'] or 'None'}\n"
        f"Coreqs: {d['coreqs'] or 'None'}\n"
        f"Offered: {format_offering(d)}"
        for d in context_docs
    )

    # Program prose is injected verbatim — it's already human-readable from the scraper
    program_context = "\n\n".join(program_texts)

    # Programs go first so the LLM sees them prominently; courses follow as supporting detail
    if program_context and course_context:
        context = f"[PROGRAM REQUIREMENTS]\n{program_context}\n\n[COURSES]\n{course_context}"
    elif program_context:
        context = f"[PROGRAM REQUIREMENTS]\n{program_context}"
    else:
        context = course_context

    # ── STEP 6: BUILD THE PROMPT ─────────────────────────────────────────────
    # The prompt is a single big f-string that tells the LLM:
    #   - Who it is (McGill assistant)
    #   - The rules it must follow (use only context, be concise, etc.)
    #   - Common student phrasings to watch out for
    #   - The student's question
    #   - The context we assembled above
    #
    # Prompt engineering is iterative — these rules were added one by one as the
    # LLM got things wrong in testing. Each rule is a lesson learned.
    prompt = f"""You are a helpful academic assistant for McGill University. Use "I" naturally, keep it casual and conversational.
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
- If doesn't have description available, instead of saying "No description available." say "The course exists in the database but I can't find it's description. Please check the [McGill eCalendar](https://www.mcgill.ca/study/2024-2025/courses/{course_id.replace(' ', '-').lower()}) directly."

**RESPONSE FORMAT:**
- Course titles are already embedded in the context next to their codes, like "COMP 252 (Honours Algorithms and Data Structures)". Always include the title in parentheses when writing a course — copy it exactly as it appears in the context.
- If a course code appears with no parenthetical title anywhere in the context, list it by code only. Never invent or guess a title.
- When listing prerequisites, format as: "Prerequisites: COMP 202 (Foundations of Programming)"
- When describing program requirements, ALWAYS mention both required courses AND complementary/elective courses if both are listed in the context.
- Be concise. Answer the question directly — never repeat information, never list the same course twice, never add context the student didn't ask for.
- **COMPARISON QUESTIONS:** When asked what's different or extra between two programs:
  - First, identify which two programs the student named in their question. ONLY compare those two. Ignore all other programs in the context, even if they look similar.
  - Reason through the comparison INTERNALLY. Do NOT list both programs' courses in your answer — students don't need to see the intermediate work, only the final result.
  - Only output the courses that are exclusively in one program and not the other.
  - Pay attention to direction. "What extra does Honours require compared to Major?" means: courses in Honours that are NOT in Major. Do NOT include courses that are only in the Major — those are not extra requirements for Honours.
  - A course that appears in BOTH programs is shared and must not appear in the differences.
  - If two programs each require a different version of a related course (e.g. Honours has COMP 252 while Major has COMP 251), say "COMP 252 instead of COMP 251" rather than listing each as a separate difference.

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

    # Build this lookup now — needed for both title injection (Step 7b) and sources (Step 8).
    # Maps "COMP-252" → {id, title, prereqs, ...} so we can look up any course by DB id.
    enriched_by_id = {d["id"]: d for d in context_docs}

    # ── STEP 7: CALL THE LLM ────────────────────────────────────────────────
    # llm.invoke() sends the prompt to GPT-4o-mini and blocks until we get a
    # response. response.content is the answer string.
    response = llm.invoke(prompt)

    # ── STEP 7b: POST-PROCESS — INJECT COURSE TITLES ────────────────────────
    # Even with the title injection into program prose, the LLM sometimes copies
    # course codes without their titles. As a reliable fallback, we scan the
    # answer for bare course codes (e.g. "COMP 252") and replace them with the
    # full label ("COMP 252 (Honours Algorithms and Data Structures)") using the
    # enriched_by_id map we already have. This runs purely in Python — no extra
    # LLM call needed.
    #
    # The regex matches patterns like "COMP 252" or "MATH 340" that are NOT
    # already followed by a parenthesis (so we don't double-wrap existing labels).
    def inject_titles(text: str) -> str:
        def replace_code(m):
            dept, num = m.group(1), m.group(2)
            db_id = f"{dept} {num}"           # "COMP 252" — DB uses spaces, not hyphens
            d = enriched_by_id.get(db_id, {})
            return format_course_label(db_id, d.get("title", ""))
        return re.sub(r'\b([A-Z]{3,4}) (\d{3}[A-Z]?)\b(?!\s*\()', replace_code, text)

    answer_text = inject_titles(response.content)

    # ── STEP 8: BUILD SOURCES FOR THE FRONTEND ──────────────────────────────
    # The frontend "thinking" header shows which courses and programs the system
    # searched. We deliberately show only the DIRECTLY-retrieved items — not the
    # hundreds of support docs fetched in Steps 4a/4b to fill in prereq chains.
    # Those are internal enrichment, not "sources" in the user-facing sense.
    #
    # Course sources: the IDs that came straight out of the vector search (saved
    #   as direct_course_source_ids before we expanded context above).
    # Program sources: the program chunks from retrieved_docs, capped at 5 so
    #   we don't flood the UI with every tangentially-related program.
    sources = []

    # Courses — in relevance order from the semantic search
    seen_courses = set()
    for cid in direct_course_source_ids:
        if cid in seen_courses:
            continue
        seen_courses.add(cid)
        d = enriched_by_id.get(cid, {})
        title = clean_title(d.get("title", ""), cid) if d else ""
        sources.append({"type": "course", "id": cid, "title": title})

    # Programs — top 5 most relevant (retrieved_docs is sorted by relevance score)
    seen_programs = set()
    for r in retrieved_docs:
        cid = r.get("course_id", "")
        name = r.get("program_name", "")
        if cid.startswith("program::") and name and name not in seen_programs:
            seen_programs.add(name)
            sources.append({
                "type": "program",
                "name": name,
                "faculty": r.get("program_faculty", ""),
                "url": r.get("program_url", ""),
            })
            if len(seen_programs) >= 5:
                break

    return {"answer": answer_text, "sources": sources}


# ─────────────────────────────────────────────────────────────────────────────
# QUICK TEST — run this file directly to test a single query
# Usage: cd backend && python3 qa_agent.py
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(generate_answer("Which courses require COMP 250?"))
