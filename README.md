# mcgill-course-crafter 🚀​

An intelligent course planning assistant for McGill University students. Ask natural language questions about prerequisites, corequisites, and course sequences — get accurate answers grounded in real catalogue data.

**Live Demo:** [[mcgill-course-crafter.vercel.app](https://mcgill-course-crafter.vercel.app)](https://mcgill-course-crafter.vercel.app/)

---

## What It Does

McGill's course catalogue is a maze. CourseCraft AI makes it simple:

```
You: "Can I take COMP 273 after taking COMP 206?"

CourseCraft AI: "Yes! COMP 206 is a corequisite for COMP 273, meaning you can 
Take COMP 273 at the same time as COMP 206, or any semester after completing it."
```

The system understands the difference between:
- **Prerequisites** — must complete *before* taking a course
- **Corequisites** — can take *at the same time* or *after* completing

---

## Features

- **Natural Language Q&A** — Ask questions like you'd ask an advisor
- **8,000+ Courses Indexed** — Scraped from McGill's official catalog
- **Hybrid Search** — Combines semantic vector search with deterministic SQL lookups
- **Corequisite-Aware Logic** — Understands nuanced academic rules most systems miss

---

## Tech Stack ​🖥️​

| Layer | Technology |
|-------|------------|
| **Frontend** | React, TypeScript, Tailwind CSS |
| **Backend** | FastAPI, Python |
| **LLM** | OpenAI GPT-4o-mini via LangChain |
| **Vector DB** | ChromaDB with SentenceTransformer embeddings |
| **Database** | PostgreSQL (SQLAlchemy ORM) |
| **Deployment** | Vercel (frontend), Railway (backend + database) |

---

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  React Frontend │────▶│  FastAPI Server │────▶│   PostgreSQL    │
│    (Vercel)     │     │    (Railway)    │     │   (Railway)     │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │ ChromaDB │ │ LangChain│ │  OpenAI  │
              │ (Vectors)│ │  (RAG)   │ │ GPT-4o   │
              └──────────┘ └──────────┘ └──────────┘
```

**Query Flow:**
1. User asks a question
2. Intent classification determines query type
3. Hybrid search retrieves relevant courses (semantic + SQL)
4. Context enrichment adds full course details
5. LLM generates natural language response

---

## Project Structure

```
mcgill_scraper/
├── server.py              # FastAPI endpoints
├── qa_agent.py            # LLM chain + answer generation
├── rag_layer.py           # Hybrid search (semantic + deterministic)
├── deterministic_logic.py # SQL-based course lookups
├── db_setup.py            # SQLAlchemy models
├── db_connection.py       # Database connection
├── scraper.py             # BeautifulSoup course scraper
├── chroma_db/             # Vector store (local)
├── coursecraft-frontend/  # React frontend
│   ├── src/
│   │   ├── components/    # UI components
│   │   ├── lib/api.ts     # API client
│   │   └── App.tsx        # Main app
│   └── package.json
├── requirements.txt
└── README.md
```

## Key Design Decisions

**Why hybrid search?**  
Pure semantic search misses exact matches. Pure SQL can't handle fuzzy queries. Combining both gives the best of both worlds.

**Why separate prereqs and coreqs?**  
Most systems treat them the same. But "COMP 206 is a corequisite" means something different than "COMP 206 is a prerequisite." This distinction matters for accurate advising.

**Why GPT-4o-mini?**  
Fast, cheap, and smart enough for this use case. The RAG pipeline does the heavy lifting — the LLM just needs to synthesize the retrieved context.

---

## Evaluation

`backend/eval_retrieval.py` samples 20 prerequisite questions from the catalogue at random (fixed seed).
An answer counts only if it names every course code in the official prerequisite text.
The baseline is plain RAG: top-5 ChromaDB hits and the same gpt-4o-mini, with no router or SQL.

| Question type | CourseCraft | Vector search only |
|---|---|---|
| "What are the prerequisites for X?" | 10/10 | 0/10 |
| "What courses require X?" / "What can I take after X?" | 10/10 (median 21 ms, no LLM call) | 1/10 |

Vector search alone rarely retrieves the right course for a code like "ENGL 203", so the model answers that it has no information.
Every answer is in `backend/eval_results.json`.
Rerun with `cd backend && python eval_retrieval.py`.

---

## Future Improvements

- [ ] Video game skill-tree style course completion integration + Degree requirement tracking
- [ ] Course schedule optimization
- [ ] Multi-turn conversation memory
