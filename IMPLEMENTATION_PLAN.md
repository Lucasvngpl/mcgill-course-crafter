# Implementation Plan: User Profile & Academic Planning System

## Overview

Transform the McGill Course Planning application from an anonymous Q&A chatbot into a full-featured academic planning platform with OAuth authentication, user profiles, academic history tracking, conversational onboarding, and semester-by-semester timeline visualization.

---

## Current Architecture

**Backend:**

- FastAPI + SQLAlchemy + PostgreSQL
- LangChain RAG with ChromaDB vectors
- 2 tables: `courses` and `prereq_edge`
- **NO authentication** - completely open API

**Frontend:**

- React 19 + TypeScript + Tailwind CSS
- **NO routing** - single-page chat interface
- Simple `useState` for local state management

---

## Target Architecture

**Backend:**

- OAuth authentication (Google/GitHub) with JWT tokens
- 5 new database tables for user data
- Protected API endpoints with user context injection
- AI-powered transcript parsing and conversational onboarding

**Frontend:**

- Multi-page app with React Router (chat, planning, profile)
- Auth context and Zustand state management
- Conversational onboarding in planning tab
- Timeline visualization (semester-by-semester grid)

---

## Phase 1: Backend Foundation

### 1.1 Database Schema

**Create 5 new tables** (in [backend/models/user.py](backend/models/user.py)):

1. **`users`** - Core user identity
   - `id`, `email`, `name`, `oauth_provider`, `oauth_id`, `created_at`, `updated_at`

2. **`user_profiles`** - Academic profile
   - `user_id` (FK), `program`, `year_standing` (U0/U1/U2/U3), `major`, `minor`, `interests`, `constraints`, `onboarding_completed`

3. **`academic_history`** - Courses taken/in-progress
   - `user_id` (FK), `course_id` (FK), `grade`, `term`, `year`, `credits`, `status` (completed/in_progress/planned)

4. **`high_school_credits`** - HS credentials for exemptions
   - `user_id` (FK), `credential_type` (IB/AP/A-Level), `subject`, `level`, `score`, `exempted_courses` (JSON array)

5. **`course_plans`** - Planned future courses
   - `user_id` (FK), `course_id` (FK), `term`, `year`, `notes`, `planned_at`

**Migration Strategy:**

- Set up Alembic in `backend/alembic/`
- Create additive-only migration (no ALTER on existing tables)
- Add indexes: `(user_id, status)`, `(user_id, term, year)`

### 1.2 Authentication System

**Create auth module** with 3 files:

1. **[backend/auth/oauth.py](backend/auth/oauth.py)** - OAuth provider config
   - Use `authlib` library
   - Register Google and GitHub OAuth apps
   - Read client IDs/secrets from environment

2. **[backend/auth/jwt.py](backend/auth/jwt.py)** - JWT token management
   - `create_access_token(data, expires_delta)` - Generate JWT
   - `verify_token(token)` - Validate and decode JWT
   - Use `python-jose` library with HS256 algorithm
   - 7-day token expiry

3. **[backend/auth/dependencies.py](backend/auth/dependencies.py)** - FastAPI dependency
   - `get_current_user(credentials)` - Extract user from JWT
   - Query database for user by ID
   - Raise 401 if invalid token

**Environment variables to add:**

```bash
JWT_SECRET_KEY=<generate-strong-random-key>
GOOGLE_CLIENT_ID=<from-google-console>
GOOGLE_CLIENT_SECRET=<from-google-console>
GITHUB_CLIENT_ID=<from-github-oauth-app>
GITHUB_CLIENT_SECRET=<from-github-oauth-app>
FRONTEND_URL=http://localhost:5173
```

### 1.3 API Endpoints

**Create 4 new route modules:**

1. **[backend/routes/auth.py](backend/routes/auth.py)** - Authentication endpoints
   - `GET /auth/google` - Redirect to Google OAuth
   - `GET /auth/google/callback` - Handle OAuth callback, create/find user, return JWT
   - `GET /auth/github` - Redirect to GitHub OAuth
   - `GET /auth/github/callback` - Handle GitHub callback
   - `GET /auth/me` - Get current user info
   - `POST /auth/logout` - Logout (client-side token deletion)

2. **[backend/routes/profile.py](backend/routes/profile.py)** - Profile management
   - `GET /profile` - Get user profile (create default if not exists)
   - `PUT /profile` - Update profile fields
   - `GET /profile/summary` - Generate LLM context summary (year, major, completed courses)

3. **[backend/routes/history.py](backend/routes/history.py)** - Academic history
   - `GET /history/courses` - Get all course history entries
   - `POST /history/courses` - Add course to history
   - `GET /history/hs-credits` - Get high school credits
   - `POST /history/hs-credits` - Add HS credit with exemptions
   - `POST /history/hs-credits/parse` - AI-powered transcript parsing

4. **[backend/routes/planning.py](backend/routes/planning.py)** - Course planning
   - `GET /plan` - Get course plan grouped by semester
   - `POST /plan` - Add course to plan
   - `GET /plan/recommendations` - Get AI recommendations based on profile

**Update [backend/server.py](backend/server.py):**

- Register OAuth with `oauth.init_app(app)`
- Include all new routers
- Update `/query` endpoint to require authentication (`Depends(get_current_user)`)
- Inject user context into `generate_answer()` call

### 1.4 User Context Injection into RAG

**Update [backend/qa_agent.py](backend/qa_agent.py):**

- Modify `generate_answer(query, user_context=None)` to accept optional user context dict
- Build context string: `"[STUDENT PROFILE]\nYear: {year}\nMajor: {major}\nCompleted Courses: {courses}"`
- Prepend to system prompt before LLM call
- LLM now has personalized context for every query

**Example context:**

```
[STUDENT PROFILE]
Year: U1
Major: Computer Science
Completed Courses: COMP 250, MATH 133, COMP 206, MATH 140
```

---

## Phase 2: AI-Powered Features

### 2.1 High School Transcript Parser

**Create [backend/services/transcript_parser.py](backend/services/transcript_parser.py):**

**Strategy:** Hybrid deterministic + AI fallback

1. **Deterministic lookup** - Curated `EXEMPTION_RULES` dict with McGill's official rules
   - Example: `IB Math HL 6+ → [MATH 140, MATH 141]`
2. **AI fallback** - Use GPT-4o for edge cases or unclear credentials
   - Prompt includes context of known exemption patterns
   - Returns JSON array of exempted course codes

**Function:**

```python
def parse_transcript(credential_type, subject, level, score) -> list[str]:
    # Try dict lookup first
    # Fall back to LLM if not found
    # Return list of exempted course IDs
```

**Integration:**

- Add `/history/hs-credits/parse` endpoint in [backend/routes/history.py](backend/routes/history.py)
- Frontend calls this when user enters HS credits during onboarding

### 2.2 Conversational Onboarding Bot

**Create [backend/services/onboarding.py](backend/services/onboarding.py):**

**State machine with 7 steps:**

1. `welcome` → Welcome message
2. `ask_year` → "What year are you in? (U0/U1/U2/U3)"
3. `ask_major` → "What's your major?"
4. `ask_completed_courses` → "Which courses have you completed?"
5. `ask_hs_credits` → "Any high school credits (IB/AP/A-levels)?"
6. `ask_interests` → "What are your academic interests/goals?"
7. `complete` → Save profile, show success message

**Function:**

```python
def get_onboarding_response(user_message, conversation_state) -> dict:
    # Returns: {'response': str, 'next_state': str, 'extracted_data': dict}
    # Extract structured data from natural language (e.g., "U1" from "I'm a first-year student")
```

**Helper functions:**

- `extract_year(message)` - Parse year standing from text
- `extract_courses(message)` - Regex extract course codes (COMP 250, MATH-133, etc.)
- `extract_hs_credits(message)` - LLM-powered extraction of credentials

**Create [backend/routes/onboarding.py](backend/routes/onboarding.py):**

- `POST /onboarding/chat` - Conversational endpoint for onboarding flow
- Accepts user message + current state
- Returns bot response + next state + extracted data

---

## Phase 3: Frontend Development

### 3.1 Install Dependencies

**Update [frontend/package.json](frontend/package.json):**

```bash
npm install react-router-dom zustand
```

- **react-router-dom** - Multi-page routing
- **zustand** - Lightweight state management for profile/plan data

### 3.2 Authentication Context

**Create [frontend/src/contexts/AuthContext.tsx](frontend/src/contexts/AuthContext.tsx):**

- Context provides: `user`, `token`, `login()`, `logout()`, `isAuthenticated`
- Store token in `localStorage`
- Fetch user info from `/auth/me` on mount
- Provide to entire app via `AuthProvider`

**Hook usage:**

```typescript
const { user, token, isAuthenticated, logout } = useAuth();
```

### 3.3 Profile State Store

**Create [frontend/src/stores/profileStore.ts](frontend/src/stores/profileStore.ts):**

- Zustand store for: `profile`, `history`, `plan`
- Actions: `setProfile()`, `setHistory()`, `setPlan()`, `addToPlan()`
- Syncs with backend API calls

### 3.4 Routing Setup

**Update [frontend/src/main.tsx](frontend/src/main.tsx):**

- Wrap app in `<BrowserRouter>` and `<AuthProvider>`

**Update [frontend/src/App.tsx](frontend/src/App.tsx):**

- Replace chat UI with router
- Routes:
  - `/login` - Public login page
  - `/auth/callback` - OAuth callback handler
  - `/chat` - Protected chat page (existing functionality)
  - `/planning` - Protected planning page (NEW)
  - `/profile` - Protected profile page (optional)
  - `/` - Redirect to `/chat`

**Protected route pattern:**

```typescript
<Route element={<Layout />}>
  <Route path="/chat" element={isAuthenticated ? <ChatPage /> : <Navigate to="/login" />} />
</Route>
```

### 3.5 Layout Component

**Create [frontend/src/components/Layout.tsx](frontend/src/components/Layout.tsx):**

- Header with navigation tabs (Chat, Planning, Profile)
- User name + logout button
- Active tab highlighting
- `<Outlet />` for nested routes

### 3.6 Login Page

**Create [frontend/src/pages/LoginPage.tsx](frontend/src/pages/LoginPage.tsx):**

- Two OAuth buttons: "Continue with Google" and "Continue with GitHub"
- Redirect to backend OAuth endpoints: `/auth/google` and `/auth/github`
- Styled with Tailwind (centered card, icons)

### 3.7 Auth Callback Handler

**Create [frontend/src/pages/AuthCallback.tsx](frontend/src/pages/AuthCallback.tsx):**

- Extract `?token=...` from URL query params
- Call `login(token)` from AuthContext
- Redirect to `/chat`

### 3.8 Chat Page

**Create [frontend/src/pages/ChatPage.tsx](frontend/src/pages/ChatPage.tsx):**

- Move existing chat UI from [App.tsx](frontend/src/App.tsx) here
- Keep QueryForm and AnswerCard components
- Update `askQuestion()` to include auth token in headers

### 3.9 Planning Page

**Create [frontend/src/pages/PlanningPage.tsx](frontend/src/pages/PlanningPage.tsx):**

- Fetch profile on mount
- **If `onboarding_completed === false`:** Show conversational onboarding
- **If `onboarding_completed === true`:** Show timeline visualization
- Header shows year and major

### 3.10 Onboarding Chat Component

**Create [frontend/src/components/OnboardingChat.tsx](frontend/src/components/OnboardingChat.tsx):**

- Chat-like UI with message bubbles (bot vs user)
- Input field at bottom
- Call `/onboarding/chat` on each user message
- Display bot response
- Update conversation state with each exchange
- When state reaches `complete`, save profile and call `onComplete()` callback

**UI Flow:**

```
Bot: "What year are you in?"
User: "I'm a first-year student"
Bot: "Great! As a U1 student, what's your major?"
User: "Computer Science"
Bot: "Excellent choice! Have you completed any courses?"
...
Bot: "All set! Ready to start planning?"
```

### 3.11 Timeline Visualization

**Create [frontend/src/components/TimelineView.tsx](frontend/src/components/TimelineView.tsx):**

- Fetch `/plan` on mount
- Group courses by semester (key: `{year}-{term}`)
- Display as grid of semester cards
- Each card: "Fall 2025", list of courses
- Sort chronologically (Fall → Winter → Summer)
- Empty state: "No courses planned yet"

**Layout:**

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Fall 2025    │ │ Winter 2026  │ │ Fall 2026    │
│ - COMP 250   │ │ - COMP 273   │ │ - COMP 310   │
│ - MATH 133   │ │ - MATH 223   │ │ - COMP 360   │
│ - COMP 206   │ │ - MATH 240   │ │ - ...        │
└──────────────┘ └──────────────┘ └──────────────┘
```

### 3.12 Update API Client

**Update [frontend/src/lib/api.ts](frontend/src/lib/api.ts):**

- Add auth token to all requests: `Authorization: Bearer ${token}`
- New functions:
  - `fetchProfile(token)` - GET /profile
  - `updateProfile(token, data)` - PUT /profile
  - `fetchPlan(token)` - GET /plan
  - `addToPlan(token, entry)` - POST /plan

---

## Implementation Order

### Week 1: Backend Foundation

1. Set up Alembic migrations (`alembic init alembic`)
2. Create [backend/models/user.py](backend/models/user.py) with 5 new tables
3. Run migrations (`alembic upgrade head`)
4. Test database schema with sample data

### Week 2: Authentication

5. Create [backend/auth/oauth.py](backend/auth/oauth.py), [jwt.py](backend/auth/jwt.py), [dependencies.py](backend/auth/dependencies.py)
6. Create [backend/routes/auth.py](backend/routes/auth.py) with OAuth endpoints
7. Register OAuth apps in Google/GitHub consoles
8. Test OAuth flow with Postman (redirect → callback → JWT)

### Week 3: Backend API

9. Create [backend/routes/profile.py](backend/routes/profile.py), [history.py](backend/routes/history.py), [planning.py](backend/routes/planning.py)
10. Update [backend/server.py](backend/server.py) to include routers and protect `/query`
11. Update [backend/qa_agent.py](backend/qa_agent.py) to accept user context
12. Test all endpoints with Postman

### Week 4: AI Features

13. Create [backend/services/transcript_parser.py](backend/services/transcript_parser.py)
14. Create [backend/services/onboarding.py](backend/services/onboarding.py)
15. Create [backend/routes/onboarding.py](backend/routes/onboarding.py)
16. Test AI parsing with sample IB/AP credentials

### Week 5: Frontend Foundation

17. Install `react-router-dom` and `zustand`
18. Create [frontend/src/contexts/AuthContext.tsx](frontend/src/contexts/AuthContext.tsx)
19. Create [frontend/src/stores/profileStore.ts](frontend/src/stores/profileStore.ts)
20. Update [frontend/src/main.tsx](frontend/src/main.tsx) and [App.tsx](frontend/src/App.tsx) with routing
21. Create [frontend/src/components/Layout.tsx](frontend/src/components/Layout.tsx)
22. Create [frontend/src/pages/LoginPage.tsx](frontend/src/pages/LoginPage.tsx) and [AuthCallback.tsx](frontend/src/pages/AuthCallback.tsx)

### Week 6: Frontend Pages

23. Create [frontend/src/pages/ChatPage.tsx](frontend/src/pages/ChatPage.tsx) (move existing chat)
24. Create [frontend/src/pages/PlanningPage.tsx](frontend/src/pages/PlanningPage.tsx)
25. Create [frontend/src/components/OnboardingChat.tsx](frontend/src/components/OnboardingChat.tsx)
26. Create [frontend/src/components/TimelineView.tsx](frontend/src/components/TimelineView.tsx)
27. Update [frontend/src/lib/api.ts](frontend/src/lib/api.ts) with auth and new endpoints

### Week 7: Integration & Testing

28. Test OAuth flow (Google + GitHub) end-to-end
29. Test onboarding conversational flow
30. Test timeline visualization with sample plans
31. Test context-aware chat (verify LLM sees user profile)
32. Fix bugs and edge cases

### Week 8: Deployment

33. Update environment variables in Railway (backend) and Vercel (frontend)
34. Deploy database migrations to production
35. Deploy backend and frontend
36. Test in production with real OAuth credentials
37. Monitor logs and fix any production issues

---

## Critical Files

**Backend:**

1. [backend/models/user.py](backend/models/user.py) - Database schema (5 new tables)
2. [backend/auth/dependencies.py](backend/auth/dependencies.py) - Auth middleware
3. [backend/services/onboarding.py](backend/services/onboarding.py) - Conversational onboarding
4. [backend/routes/auth.py](backend/routes/auth.py) - OAuth endpoints
5. [backend/server.py](backend/server.py) - Register routers, protect endpoints

**Frontend:**

1. [frontend/src/contexts/AuthContext.tsx](frontend/src/contexts/AuthContext.tsx) - Auth state
2. [frontend/src/App.tsx](frontend/src/App.tsx) - Routing setup
3. [frontend/src/pages/PlanningPage.tsx](frontend/src/pages/PlanningPage.tsx) - Main planning UI
4. [frontend/src/components/OnboardingChat.tsx](frontend/src/components/OnboardingChat.tsx) - Conversational onboarding
5. [frontend/src/components/TimelineView.tsx](frontend/src/components/TimelineView.tsx) - Semester visualization

---

## Key Technical Decisions

### 1. Authentication: OAuth + JWT

- **OAuth (Google/GitHub):** User preference, no password management
- **JWT tokens:** Stateless, scalable, 7-day expiry
- **Library:** `authlib` for OAuth, `python-jose` for JWT

### 2. Onboarding: Conversational Bot

- **Natural Q&A flow:** Bot asks questions one at a time
- **State machine:** 7 steps from welcome to complete
- **AI extraction:** Parse year/courses/HS credits from natural language

### 3. Transcript Parsing: Hybrid Approach

- **Deterministic first:** Lookup in curated `EXEMPTION_RULES` dict
- **AI fallback:** GPT-4o for edge cases
- **Return:** JSON array of exempted McGill course codes

### 4. Visualization: Timeline (Semester Grid)

- **Custom component:** Tailwind-styled semester cards
- **No library:** Avoids bundle bloat, full control
- **Layout:** Responsive grid, sorted chronologically

### 5. State Management: Zustand

- **Lightweight:** 1KB vs 12KB Redux
- **Simple API:** `set()` and selectors
- **Use case:** Profile, history, plan data

---

## Security Considerations

1. **User data isolation:** Every query filtered by `user_id` from JWT
2. **OAuth state validation:** Prevent CSRF attacks (handled by authlib)
3. **JWT secret security:** Strong 64-char secret, stored in env vars
4. **Rate limiting:** 100 requests/hour per user (use `slowapi`)
5. **SQL injection:** Using SQLAlchemy ORM (parameterized queries)

---

## Verification & Testing

### Backend Tests

- **Unit:** JWT creation/verification, transcript parsing, onboarding state machine
- **Integration:** OAuth flow, authenticated endpoints, user context injection
- **Tools:** pytest

### Frontend Tests

- **Component:** AuthContext login/logout, OnboardingChat flow, TimelineView rendering
- **E2E:** Complete OAuth flow, onboarding completion, adding courses
- **Tools:** Vitest, React Testing Library, Playwright

### Manual Testing Checklist

- [ ] OAuth login with Google works
- [ ] OAuth login with GitHub works
- [ ] Onboarding asks all 5 questions
- [ ] Profile saved correctly after onboarding
- [ ] Timeline displays semesters chronologically
- [ ] Chat responses include user context (e.g., "As a U1 CS student...")
- [ ] HS credit parser returns correct exemptions for IB Math HL 6
- [ ] Logout clears token and redirects to login

---

## Deployment Notes

### Backend (Railway)

- Run `alembic upgrade head` before deploying new code
- Add 5 new environment variables for OAuth and JWT
- Update CORS to allow Vercel frontend domain

### Frontend (Vercel)

- Set `VITE_API_URL` to Railway backend URL
- Update OAuth redirect URIs in Google/GitHub consoles
- Test build locally: `npm run build && npm run preview`

### Post-Deployment

- Monitor logs for errors (especially OAuth callbacks)
- Check database query performance (add indexes if needed)
- Set up database backups (Railway automatic backups)

---

## Future Enhancements

1. **Drag-and-drop timeline:** Reorder courses with `react-beautiful-dnd`
2. **Degree progress tracker:** Scrape major requirements, show completion %
3. **Collaborative planning:** Share plans with advisors/peers
4. **Course recommendations:** Collaborative filtering based on similar students
5. **Export to PDF/Calendar:** Generate printable semester plans
6. **Recursive prereq resolver:** Calculate transitive closure of prerequisites (COMP 310 → COMP 273 → COMP 206)

---

## Success Criteria

✅ **User can:**

1. Sign in with Google or GitHub
2. Complete conversational onboarding (answer 5 questions)
3. See their profile (year, major, completed courses)
4. View semester timeline with planned courses
5. Ask questions in chat and receive context-aware responses (e.g., "As a U1 student in CS who has completed COMP 250...")
6. Add high school credits and see exempted McGill courses
7. Log out and log back in to see saved data

✅ **System:**

- All user data isolated by user_id (no data leakage)
- OAuth flow secure (state validation)
- JWT tokens expire after 7 days
- LLM receives user context on every query
- Timeline displays courses chronologically

---

## Estimated Effort

**Total:** 6-8 weeks (1 developer, full-time)

- Backend: 3-4 weeks
- Frontend: 2-3 weeks
- Testing & Deployment: 1 week

**Breakdown:**

- Database schema: 3 days
- Authentication: 5 days
- API endpoints: 7 days
- AI features: 5 days
- Frontend routing & auth: 5 days
- Frontend pages & components: 7 days
- Testing: 5 days
- Deployment: 3 days
