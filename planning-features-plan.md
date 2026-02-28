# Planning Features Implementation Plan
> **Status: DEFERRED — implement AFTER Step 12 (Institutional Knowledge)**
> Designed: 2026-02-28
> Interview notes captured here so nothing is forgotten.

---

## What This Plan Covers

Step 10 of the CLAUDE.md roadmap: routing, sidebar, onboarding bot, timeline grid, profile page, and supporting backend endpoints.

---

## Decisions Made (Interview Summary)

### Navigation
- **Left sidebar, collapsible** (icon-only when collapsed, label+icon when expanded)
- Toggle button to collapse/expand; collapsed state gives more horizontal space for the timeline
- Routes: `/` (Chat), `/plan` (Planning), `/profile` (Profile)

### Auth Gating
- **Planning + Profile are gated behind sign-in**
- Anonymous users see a sign-in prompt when they navigate to `/plan` or `/profile`
- Chat (`/`) stays fully open for everyone

### Planning Tab Layout
- **Onboarding first, then timeline**
- First visit → conversational onboarding bot
- After onboarding → smooth fade/slide transition, "All set!" message, timeline view appears
- Bot accessible again later (TBD — could be a button to re-open it)

### Onboarding Bot Flow
Questions in order:
1. Year standing (U0 / U1 / U2 / U3 / U4)
2. Faculty / major (free text)
3. Courses already completed (free text → LLM parses to course IDs, saves to `user_courses`)
4. HS exemptions (IB/AP/CEGEP) — **only asked if year is U0 or U1**

Backend: **dedicated `/onboard` endpoint** (not the /query RAG pipeline)
- Takes: `{ step, answer, user_id }`
- Returns: `{ next_question, done: bool, saved_facts: {...} }`
- Saves structured data to `user_profiles` and `user_courses` as answers come in
- LLM call for step 3 maps free-text course names → course IDs from PostgreSQL

### Timeline Grid
- **Horizontal scroll, semester columns**
- Each column = one semester (e.g. Fall 2025, Winter 2026, Fall 2026...)
- Courses are cards stacked vertically inside the column
- Columns start from the user's first semester (derived from year_standing + current date)

**Adding courses:**
- **Type-ahead search** (like McGill's Virtual Schedule Builder — screenshots TBD)
- Dropdown shows: **`COMP-250`** (bold) with `Introduction to Computer Science` (smaller text below)
- Search calls backend `/courses/search?q=<query>` endpoint
- Dropdown appears inline below a "+" button or search bar within each semester column

**Removing courses:**
- Hard delete from `course_plans` table (simple, no soft-delete for now)

### Profile Page
- Editable profile fields: year, major, minor, program
- Courses completed list (sourced from `user_courses` where status = 'completed')
  - Adding a course here also shows it in the timeline as a completed past semester
- Planned courses list (mirrors the timeline)
- Sign out button

### State Management
- **One global Zustand store** with slices:
  - `auth` — user, accessToken
  - `profile` — year_standing, major, minor, onboarding_completed
  - `plan` — semesters `[{ term, year, courses: [...] }]`

---

## Backend Endpoints to Build

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/onboard` | Onboarding bot step handler (saves profile + courses) |
| `GET` | `/courses/search?q=` | Type-ahead course search — returns id + title |
| `GET` | `/plan` | Load user's course plan (all semesters) |
| `POST` | `/plan/courses` | Add a course to a semester |
| `DELETE` | `/plan/courses/{id}` | Remove a course from a semester |
| `GET` | `/profile` | Load user profile |
| `PUT` | `/profile` | Update editable profile fields |

All new endpoints require auth (except `/courses/search` which can be public).

---

## Frontend Files to Create/Modify

```
frontend/src/
  main.tsx                     ← wrap in <BrowserRouter>
  App.tsx                      ← becomes <RouterRoot> (sidebar + <Outlet>)
  store/
    index.ts                   ← Zustand store (auth + profile + plan slices)
  pages/
    ChatPage.tsx               ← current App.tsx chat logic moved here
    PlanPage.tsx               ← onboarding bot OR timeline (based on onboarding_completed)
    ProfilePage.tsx            ← profile form + completed courses + sign out
  components/
    Sidebar.tsx                ← collapsible left nav
    AuthGuard.tsx              ← redirects to sign-in if not authed
    onboarding/
      OnboardingBot.tsx        ← conversational step-by-step UI
    planning/
      TimelineGrid.tsx         ← horizontal scroll semester grid
      SemesterColumn.tsx       ← one column (header + course cards + add button)
      CourseCard.tsx           ← card inside a semester column (course id + title + remove btn)
      CourseSearchDropdown.tsx ← type-ahead search input + results dropdown
  lib/
    api.ts                     ← add new API calls (search, plan CRUD, profile, onboard)
```

---

## Key UX Details to Remember

- **Sidebar collapse state** should persist in localStorage (survives page refresh)
- **Onboarding `done` flag** lives in `user_profiles.onboarding_completed` (already a column in DB)
- **Type-ahead search**: debounce 200ms before calling backend, min 2 chars to trigger
- **Dropdown item format**: bold course ID on top, muted course title below — no credits/semesters in dropdown
- **Timeline starting point**: derive from year_standing + current academic year (Fall 2026 = current semester for a new U1)
- **Virtual Schedule Builder reference**: Lucas will provide screenshots before implementing `CourseSearchDropdown.tsx` — hold that component for last

---

## Packages to Install

```bash
# Frontend
npm install react-router-dom zustand

# No new backend packages needed — existing FastAPI + SQLAlchemy covers new endpoints
```

---

## Implementation Order (when this plan is activated)

1. Install packages, set up routing scaffold (App.tsx → RouterRoot + Sidebar + pages)
2. AuthGuard component + auth gating for `/plan` and `/profile`
3. Zustand store (auth slice first, migrate existing user/accessToken state from App.tsx)
4. Backend: `/profile` GET+PUT and `/courses/search` endpoints
5. ProfilePage (editable fields + sign out — no courses list yet)
6. Backend: `/onboard` endpoint
7. OnboardingBot component + PlanPage (onboarding flow)
8. Backend: `/plan` CRUD endpoints
9. TimelineGrid + SemesterColumn + CourseCard
10. CourseSearchDropdown (after screenshots from Lucas)
11. Wire completed courses from profile → past semester columns on timeline
12. Polish: sidebar collapse persistence, transitions, empty states

---

## Open Questions (resolve before implementing)

- [ ] What does the Virtual Schedule Builder type-ahead look like exactly? (Lucas will provide screenshots)
- [ ] What academic year format should the timeline use? Calendar year (Fall 2025) or academic year (U1 Year)?
- [ ] Should there be a Summer semester column option, or just Fall + Winter?
- [ ] How many semesters should the timeline show by default? (e.g. current + 4 future = 5 columns?)
