# McGill CourseCraft AI - Project Context

## What This Project Is

A full-stack RAG-powered course planning assistant for McGill University students. Users ask questions about courses, prerequisites, and planning. The system uses hybrid search (ChromaDB vectors + PostgreSQL deterministic queries) and GPT-4o-mini to generate answers.

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
- **NO routing currently** - single-page chat interface

### Database (PostgreSQL)

- **Current tables:** `courses` (8000+ courses), `prereq_edge` (prerequisite relationships)
- **No user tables yet**

### Deployment

- **Frontend:** Vercel
- **Backend:** Railway (Procfile: `cd backend && uvicorn server:app`)
- **Database:** Supabase PostgreSQL (migrated from Railway). Railway still active in production - needs env var update when ready.

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

**New (To Be Created):**

- `auth.users` - Supabase manages this automatically (id, email, etc.)
- `user_profiles` - 1:1 with user. year_standing, major, minor, program, interests, constraints, notes (free text catch-all), onboarding_completed
- `academic_history` - 1:many. course_id, grade, term, year, status (completed/in_progress/planned), source (manual/extracted)
- `course_plans` - 1:many. course_id, term, year, notes
- `chat_messages` - 1:many. role (user/assistant), content, created_at, session_id

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
9. Beautify chat UI (animations, dark glassmorphism, message bubbles) <-- CURRENT
10. Build planning features (routing, onboarding chat, timeline view, profile page)
11. Add fact extraction to LLM response flow
12. Institutional knowledge expansion (see Institutional Knowledge Roadmap below)
13. Conversational ask-back (LLM requests clarification when needed)
14. Scrape program/major requirements + U0/U1/exemption rules from eCalendar

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

- `IMPLEMENTATION_PLAN.md` - Detailed implementation plan with code examples
- `backend/db_setup.py` - Current SQLAlchemy models
- `backend/server.py` - API endpoints
- `frontend/src/lib/api.ts` - Frontend API client
- `frontend/src/App.tsx` - Main React component (will become router)

## User Context

- The developer (Lucas) is a first-year student learning as they build
- Prefers hands-on learning: explain concepts, give hints, let them write the code
- Has some SQLAlchemy knowledge
- Chose the simpler path for auth (Supabase) to focus learning on planning features. Eventually wants it to be full interactive intelligent application for many users at any point in undergrad to be able to answer questions about and plan anything related to course selection, from understanding corequisties and requirements and exemptions to planning ways to pivot and seeking advice with chat functionality.

## Future Ideas (Don't Forget)

1. **High school course exemptions** - `course_exemptions` table (course_id, credential_type, subject, level, min_score). Scrape McGill's exemption pages to populate. Enables instant lookup: "IB Math HL 6 → exempt from MATH 140, MATH 141" without LLM. Could also use AI to parse HS transcripts for incoming students.
2. **Program/major requirements** - Scrape degree requirement pages from eCalendar (like the CS major CATALOG_URL already in .env). Store required courses per major so the LLM can answer "what courses do I need for X major?" Currently a gap — the DB has courses but not program structures.
3. **Major transfer advisor** - Handle questions like "which of my CS courses would transfer if I switched to Math?" Requires scraping degree requirements per major.
4. **user_facts catch-all table** - Flexible key-value store for things that don't fit in structured tables (scheduling constraints, preferences, misc context). Add if the free-text "notes" field on profiles isn't enough.

## Important Patterns

- Course IDs are formatted like "COMP-250" in the database
- Course aliases exist (e.g., "calc 3" -> "MATH 222") in qa_agent.py
- PrereqEdge uses composite primary key (src_course_id, dst_course_id, kind)
- Prerequisite chain traversal is currently single-level only (no recursive resolution)
- `can_take_course()` in course_logic.py validates eligibility but only checks immediate prereqs
