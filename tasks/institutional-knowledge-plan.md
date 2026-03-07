# Institutional Knowledge Plan

> **Status: ACTIVE — implement before Planning Features (Step 10)**
> Designed: 2026-02-28

---

## What This Unlocks

Right now the system knows individual courses well but is blind to the layer around them.
An advisor doesn't just know what COMP 302 covers — they know what programs require it,
which students should take it when, and what it leads to. This plan fills that gap.

**Queries this unlocks:**

- "I want to take AI courses — what should I look at?"
- "What are good poli sci courses for a first year?"
- "What does the CS major actually require?"
- "I'm a U0 Science student — what should I be taking this semester?"
- "How do I get into COMP 551?" (traces full prereq chain, not just one level)

---

## Phase 0: Quick Win — Fix the Regex Bug (do this first, ~30 min)

**Problem:** `qa_agent.py` has hardcoded aliases (e.g. "AI courses" → always COMP 424)
that short-circuit semantic search. This means topically similar courses (COMP 551, COMP 596,
COMP 767) are never surfaced when they should be.

**Fix:** Remove the hardcoded alias mapping from `qa_agent.py`. Let the semantic search
do its job — it already embeds course descriptions, and COMP 551's description
("machine learning", "neural networks") will rank highly for "AI courses" queries.

**Test after:** Ask "what AI courses does McGill offer?" and verify multiple courses come
back (not just COMP 424).

---

## Phase 1: LLM Scraping Agent

### Goal

Scrape all undergraduate program requirements from the McGill course catalogue and
save one JSON file per program to `backend/institutional_data/programs/`.

### Target Site

`https://coursecatalogue.mcgill.ca/en/undergraduate/`

The site appears to be static HTML, so simple `requests` + `BeautifulSoup` is enough
(no headless browser needed). Verify this by inspecting page source before building.

### Navigation Path the Agent Follows

```
coursecatalogue.mcgill.ca/en/undergraduate/
  └── [Faculty links: Engineering, Science, Arts, Management, ...]
        └── Academic Units (departments within faculty)
              └── Programs tab
                    └── Each program page
                          ├── Program description text
                          ├── Required courses (with course IDs) in courses tab
                          └── Complementary/elective courses (with course IDs) in courses tab
```

### What Gets Scraped Per Program

```json
{
  "faculty": "Faculty of Science",
  "program_name": "Computer Science (B.Sc. Major)",
  "program_type": "major",
  "description": "The Computer Science program at McGill...",
  "required_courses": [
    "COMP-250",
    "COMP-251",
    "COMP-302",
    "COMP-330",
    "MATH-240"
  ],
  "complementary_courses": ["COMP-424", "COMP-551", "COMP-360"],
  "source_url": "https://coursecatalogue.mcgill.ca/en/undergraduate/..."
}
```

### Caching Strategy (run once, cache aggressively)

- Output directory: `backend/institutional_data/programs/`
- Filename: `{faculty_slug}_{program_slug}.json` (e.g. `science_computer-science-bsc-major.json`)
- **If the file already exists, skip that program entirely** — no re-scraping
- To refresh: delete the relevant JSON file(s) and re-run
- Full re-scrape only needed when eCalendar updates annually

### LLM's Role in Extraction

The HTML on program pages is structured but messy. After BeautifulSoup parses the raw HTML,
use the LLM (gpt-4o-mini or claude-haiku — cheapest capable model) to:

1. Extract the program description as clean prose
2. Identify and list all course IDs mentioned under "required" sections
3. Identify and list all course IDs mentioned under "complementary/elective" sections

This avoids brittle regex patterns for parsing course lists out of HTML.

### Scope: Majors Only (for now)

- Majors only — no minors or concentrations in this pass
- All faculties (Science, Arts, Engineering, Management, + others as found)
- Estimated programs: ~100–150 across all faculties

### Agent File

`backend/institutional_scraper.py` — standalone script, run manually:

```bash
cd backend && python institutional_scraper.py
```

---

## Phase 2: Load into ChromaDB

### Chunk Text Format: Natural Language Prose

Each program becomes one chunk. The LLM (during loading, not scraping) converts
the JSON into a human-readable prose chunk that's ideal for both semantic search
and LLM comprehension:

```
The Computer Science Major at McGill's Faculty of Science is a rigorous program
focused on theoretical foundations and practical software development. Required core
courses include: COMP-250 (Introduction to Computer Science), COMP-251 (Algorithms and
Data Structures), COMP-302 (Programming Languages and Paradigms), COMP-330 (Theory of
Computation), and MATH-240 (Discrete Structures). Complementary electives include courses
such as COMP-424 (Artificial Intelligence), COMP-551 (Applied Machine Learning), and
COMP-360 (Algorithm Design).
```

### ChromaDB Metadata Tags

```python
{
  "type": "program_req",       # distinguishes from "course" chunks
  "faculty": "Faculty of Science",
  "program": "Computer Science (B.Sc. Major)",
  "source_url": "https://..."
}
```

### Integration with Existing Pipeline

- Update `build_vector_store()` in `backend/rag_layer.py` to:
  1. Load courses as before (no change)
  2. After courses: load all JSON files from `backend/institutional_data/programs/`
  3. Convert each to prose → embed → add to ChromaDB with metadata
- **Retrieval stays the same**: top-K from the same pool (course chunks and program chunks
  compete on relevance — program chunks win when the query is program-level)

### Course Level Inference (simple heuristic)

Add a `level` metadata field to each course chunk based on course number:

- 100–299 → `"intro"` (first/second year accessible)
- 300–499 → `"upper"` (third/fourth year, usually has prereqs)
- 500+ → `"graduate"` (grad level)

This lets the LLM reason: "POLI 101 is an intro course, accessible to first years"
without any hardcoded logic.

---

## Phase 3: Validate with Real Queries

After loading, test these queries against the updated system:

| Query                                                           | Expected improvement                                                                                                          |
| --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| "What AI courses does McGill offer?"                            | Returns COMP 424, COMP 551, and more by understanding courses offered in program and descriptions semantically — not just one |
| "What are good poli sci courses for a first year?"              | Returns 100/200-level POLI courses with intro-friendly framing                                                                |
| "What does the CS major require?"                               | Pulls the CS program chunk, lists required + complementary                                                                    |
| "I'm a U0 Science student, what should I take?"                 | Can now give faculty-aware advice                                                                                             |
| "I want to study machine learning end-to-end, what's the path?" | Traces prereq chain from COMP 202 → 250 → 251 → 551                                                                           |

---

## Files to Create / Modify

| File                                   | Action     | Purpose                                   |
| -------------------------------------- | ---------- | ----------------------------------------- |
| `backend/qa_agent.py`                  | Modify     | Remove hardcoded alias mappings (Phase 0) |
| `backend/institutional_scraper.py`     | Create     | LLM scraping agent                        |
| `backend/institutional_data/programs/` | Create dir | JSON cache per program                    |
| `backend/rag_layer.py`                 | Modify     | Load institutional chunks into ChromaDB   |

---

## Open Questions (resolve during implementation)

- [ ] Is `coursecatalogue.mcgill.ca` actually static HTML? Inspect source before building scraper
- [ ] What's the exact HTML structure of a program page? (determines BeautifulSoup selectors)
- [ ] Does the new catalogue have all faculties, or are some still only on the old eCalendar?
- [ ] What's a safe request rate to avoid being blocked by McGill's servers?

---

## Implementation Order

1. Phase 0: Fix regex aliases in `qa_agent.py` (quick win, do immediately)
2. Inspect `coursecatalogue.mcgill.ca` source to understand HTML structure
3. Build `institutional_scraper.py` — nav logic first, extraction second
4. Test scraper on one faculty (Science) before running all
5. Run full scrape, verify JSON files look correct
6. Update `rag_layer.py` to load institutional chunks
7. Re-build ChromaDB and test with real queries
