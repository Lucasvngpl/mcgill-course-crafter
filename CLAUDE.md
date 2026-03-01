# McGill CourseCraft AI - Project Context

## What This Project Is

A full-stack RAG-powered course planning assistant for McGill University students. Users ask questions about courses, prerequisites, and planning. The system uses hybrid search (ChromaDB vectors + PostgreSQL deterministic queries) and GPT-4o-mini to generate answers. The creator, Lucas, is building this project to get real student users but also as a learning exercise in AI engineering and full-stack so we should walk him through the steps not just blindly write code withou comments or expalantions because we want to teach him.

## Architecture

### Backend (FastAPI + Python)

- **Entry point:** `backend/server.py` - FastAPI app with endpoints
- **RAG pipeline:** `backend/rag_layer.py` - hybrid search (semantic + SQL)
- **LLM layer:** `backend/qa_agent.py` - GPT-4o-mini via LangChain
- **Course logic:** `backend/course_logic.py` + `backend/deterministic_logic.py` - prereq queries, eligibility checks
- **Database:** `backend/db_setup.py` - SQLAlchemy models (Course, PrereqEdge)
- **Scraper:** `backend/scraper.py` - BeautifulSoup scraper for McGill course catalogue

### Frontend (React 19 + TypeScript + Tailwind)

- **Entry:** `frontend/src/main.tsx` → `frontend/src/App.tsx`
- **Components:** `frontend/src/components/QueryForm.tsx`, `AnswerCard.tsx`
- **API client:** `frontend/src/lib/api.ts`
- **Auth client:** `frontend/src/lib/supabase.ts`
- **Animations:** framer-motion (message entrance), sonner (toasts)
- **Routing:** react-router-dom — to be added next, currently single-page

### Database (PostgreSQL — Supabase)

- **Course tables:** `courses` (8065 courses), `prereq_edge` (prereq relationships)
- **User tables:** `user_profiles`, `user_courses`, `chat_messages` (live in Supabase)

### Deployment

- **Frontend:** Vercel
- **Backend:** Railway (`cd backend && uvicorn server:app`)
- **Database:** Supabase PostgreSQL (single DB for courses + users)

## Current Implementation Status

### Decided & Planned

- **Auth:** Supabase Auth (Google/GitHub OAuth) - NOT custom OAuth
- **Database:** Migrating everything to Supabase PostgreSQL (single database for courses + users)
- **Auth is optional:** Anonymous users get full chat access. Sign-in unlocks profile, saved history, planning tab, personalized recommendations
- **Onboarding:** Conversational bot in planning tab (asks year, major, courses taken, HS credits, interests)
- **Visualization:** Timeline view (semester-by-semester grid)
- **State management:** Zustand for frontend profile/plan state
- **Routing:** react-router-dom for multi-page app

### Architecture Decisions Made

1. **Supabase over custom OAuth** - Less boilerplate, handles OAuth/JWT automatically, only need token verification on backend
2. **Single database (Supabase)** - Course data + user data in one place, avoids cross-database queries
3. **Auth is optional** - Existing `/query` endpoint stays open, new user-specific endpoints require auth
4. **Conversational onboarding over forms** - Bot asks questions one at a time in planning tab
5. **optional later AI parses HS transcripts** - for context for incoming students selecting courses to understand which they are exempt from, eventually adding to table all the course exemptions
6. **Timeline visualization** - Custom Tailwind component, no heavy charting library

### Database Tables

**Existing:**

- `courses` - 8065 McGill courses (id, title, description, credits, prereq_text, etc.)
- `prereq_edge` - prerequisite relationships (empty - relationships live in prereq_text)

**User tables (created, live in Supabase):**

- `auth.users` - managed by Supabase automatically
- `user_profiles` - 1:1 with user. year_standing, major, minor, program, interests, constraints, notes, onboarding_completed
- `user_courses` - 1:many. course_id, grade, term, year, status (completed/in_progress/planned), source (manual/extracted)
- `course_plans` - 1:many. course_id, term, year, notes (not yet wired to frontend)
- `chat_messages` - 1:many. role (user/assistant), content, created_at, session_id (not yet wired)

### Message Flow (Hybrid Chat + Fact Extraction)

```
User message → Save to chat_messages
             → Load structured profile (all facts, NOT old messages)
             → LLM gets: system prompt + profile context + RAG results + user message
             → LLM returns: { answer, extracted_facts }
             → Save facts silently to academic_history/profile
             → Save assistant message to chat_messages
             → Return answer to frontend
```

- Existing RAG hybrid search (ChromaDB + SQL) stays exactly the same
- User profile context is ADDED to the prompt, not replacing anything
- Fact extraction happens in the same LLM call (no extra API call)
- Facts save silently (no confirmation needed)

### Implementation Order

1. ~~Set up Supabase project~~ DONE
2. ~~Migrate course data from Railway to Supabase~~ DONE (8065 courses)
3. ~~Update backend DATABASE_URL to point to Supabase~~ DONE
4. ~~Enable Supabase Auth (Google OAuth)~~ DONE
5. ~~Add user tables to Supabase (profiles, history, plans)~~ DONE
6. ~~Build frontend auth (Supabase JS SDK - signInWithOAuth, auth listener)~~ DONE
7. ~~Wire up backend JWT verification (ES256 + JWKS)~~ DONE
8. ~~Deploy to Railway + Vercel with Supabase~~ DONE
9. ~~Beautify chat UI (animations, dark glassmorphism, message bubbles)~~ DONE
10. Build planning features (routing, onboarding chat, timeline view, profile page) — **DEFERRED until after Step 12** — full design plan saved in `planning-features-plan.md`
11. Add fact extraction to LLM response flow
12. Institutional knowledge expansion (see Institutional Knowledge Roadmap below) <-- NEXT
13. Conversational ask-back (LLM requests clarification when needed)

## Institutional Knowledge Roadmap

The system currently knows individual courses well but is blind to the institutional layer that surrounds them — the stuff a real advisor would know. Things like what U0 status means, whether a student needs a foundation year, program requirements, and HS exemption rules. Without this, planning questions like "as a U0 Science student, should I take CHEM 110 this semester?" can't be answered properly.

The goal is not to hardcode handlers for specific question patterns. The LLM should just _know_ all of this context and reason with it naturally, the way a knowledgeable upper-year student or advisor would.

For example, once you scrape the eCalendar program/major requirement pages for business and store that context, the LLM will just know "management major → Desautels → here are the relevant course prefixes and required courses" the same way a real advisor would — without needing any hardcoded regex mappings, which we ideally want to avoid entirely. That's the right fix for MGMT and the whole class of similar problems.

> **Scraping strategy is TBD** — which eCalendar pages to target, how to structure the data, and how to chunk it for retrieval all need further discussion before implementation.

### Step 1: Institutional Knowledge Scraping

Scrape and store the broader McGill context that surrounds individual courses:

- **Program/major requirements** — eCalendar degree requirement pages per faculty/major: what courses are required, in what order, with what constraints (already in Future Ideas, now elevated)
- **U0/U1 rules** — what each status means per faculty, and what it implies for course selection and sequencing
- **Foundation year requirements** — e.g. Science U0 students lacking certain HS credits must complete specific foundation courses before advancing to U1
- **High school exemptions** — IB/AP/CEGEP credit rules that let students skip specific courses (already in Future Ideas, now elevated)
- **Faculty-specific progression rules** — things like "U1 Engineering students must complete X before registering for Y"

Data format, target URLs, and storage schema: **TBD — needs discussion.**

### Step 2: RAG Layer Enhancement for Institutional Context

Once institutional documents are scraped, load them into ChromaDB alongside course data:

- Tag each chunk by type: `program_req`, `faculty_rule`, `exemption_rule`, `foundation_year`, `course`
- On query, retrieve across all chunk types so the LLM sees both course info and institutional context together
- No hardcoded logic — just richer retrieval feeding a smarter prompt

### Step 3: Conversational Ask-Back

Allow the assistant to ask a clarifying question instead of guessing when it lacks enough context:

- Add an optional `follow_up_question` field to the LLM response structure
- If the LLM can't answer confidently without more info, it returns a question rather than a hedged non-answer
- Frontend renders this as a natural chat message — not a form or popup
- The student's reply feeds into the next message as additional context
- Example: "Should I take COMP 302 next semester?" → "What are you taking this semester? I want to make sure you meet the prereqs before recommending it."

## Key Files

- `backend/db_setup.py` - SQLAlchemy models (Course, PrereqEdge, UserProfile, UserCourse, ChatMessage)
- `backend/server.py` - FastAPI app, JWT auth, user context injection
- `backend/rag_layer.py` - Hybrid search (ChromaDB semantic + SQL deterministic)
- `backend/qa_agent.py` - LLM prompt construction via LangChain
- `frontend/src/App.tsx` - Main React component (will become router root)
- `frontend/src/lib/api.ts` - Frontend API client (sends Bearer token)
- `frontend/src/lib/supabase.ts` - Supabase client singleton

## User Context

- The developer (Lucas) is a first-year student learning as they build
- Prefers hands-on learning: explain concepts, give hints, let them write the code
- Has some SQLAlchemy knowledge
- Chose the simpler path for auth (Supabase) to focus learning on planning features. Eventually wants it to be full interactive intelligent application for many users at any point in undergrad to be able to answer questions about and plan anything related to course selection, from understanding corequisties and requirements and exemptions to planning ways to pivot and seeking advice with chat functionality.

## Future Ideas (Don't Forget)

1. **HS transcript parsing** - AI parses uploaded IB/AP/CEGEP transcripts and maps to McGill exemptions automatically. For incoming students who don't know which courses they're exempt from.
2. **user_facts catch-all table** - Flexible key-value store for things that don't fit in structured tables (scheduling constraints like "no 8am classes", misc preferences). Add if the `notes` field on profiles isn't enough.
3. **Program requirement scraping** — now tracked in the Institutional Knowledge Roadmap above.
4. **Major transfer advisor** — also tracked in the Institutional Knowledge Roadmap above.
5. **MCP Server** - Expose the RAG pipeline as an MCP server so the course knowledge base works inside other apps (Claude Desktop, Cursor, etc.) without replacing the web UI. Use MCP Resources to expose course/program data. Low lift once the core product is solid.

## Agent Workflow

### 1. Plan Before Building

- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- Write detailed specs upfront to reduce ambiguity
- If something goes sideways mid-implementation, STOP and re-plan — don't keep pushing
- Use plan mode for verification steps, not just building

### 2. Subagent Strategy

- Use subagents to keep the main context window clean
- Offload research, exploration, and parallel analysis to subagents
- One focused task per subagent

### 3. Self-Improvement Loop

- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write a rule that prevents the same mistake from happening again
- Review `tasks/lessons.md` at the start of each session for relevant lessons

### 4. Verification Before Done

- Never mark a task complete without proving it works
- Ask: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)

- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky, implement the elegant solution instead
- Skip this for simple, obvious fixes — don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing

- When given a bug report: just fix it — no hand-holding needed
- Point at logs, errors, and failing tests, then resolve them
- Always explain _what_ is broken and _why_ the fix works (Lucas is learning)

## Task Management

When working on a multi-step task:

1. **Plan First** — write plan to `tasks/todo.md` with checkable items, using askUserQuestion too. interview me in detail using the AskUserQuestionTool about literally anything: technical implementation, UI & UX, concerns, tradeoffs, etc. but make sure the questions are not obvious
   and be very in-depth and continue interviewing me continually until it's complete,
2. **Verify Plan** — check in with Lucas before starting implementation
3. **Track Progress** — mark items complete as you go
4. **Explain Changes** — give a high-level summary at each step
5. **Document Results** — add a review section to `tasks/todo.md` when done
6. **Capture Lessons** — update `tasks/lessons.md` after any correction

## Core Principles

- **Simplicity First** — make every change as simple as possible, impact minimal code
- **No Laziness** — find root causes, no temporary fixes, senior developer standards
- **Minimal Impact** — changes should only touch what's necessary, avoid introducing bugs

## Important Patterns

- Course IDs are formatted like "COMP-250" in the database
- Course aliases exist (e.g., "calc 3" -> "MATH 222") in qa_agent.py
- PrereqEdge uses composite primary key (src_course_id, dst_course_id, kind)
- Prerequisite chain traversal is currently single-level only (no recursive resolution)
- `can_take_course()` in course_logic.py validates eligibility but only checks immediate prereqs
