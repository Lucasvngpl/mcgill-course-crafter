"""CourseCraft retrieval eval: full pipeline (router + SQL + enrichment) vs plain vector RAG.

Questions are sampled at random (fixed seed) from the course catalogue. The gold answer
is the set of course codes in the official prerequisite text, so scoring is mechanical:
an answer is correct only if it names every gold code.

Run from backend/: python eval_retrieval.py [n_per_type]
"""
import json, os, random, re, sys, time

from langchain_openai import ChatOpenAI
from db_connection import Session
from db_setup import Course
from rag_layer import semantic_search
import qa_agent  # loads backend/.env (OPENAI_API_KEY, DATABASE_URL)

SEED, N = 7, int(sys.argv[1]) if len(sys.argv) > 1 else 10
CODE = re.compile(r"\b([A-Z]{3,4})[\s-]?(\d{3}[A-Z]?)\b")
codes = lambda text: {f"{d} {n}" for d, n in CODE.findall(text or "")}

with Session() as s:
    courses = {c.id: c for c in s.query(Course).all() if not (c.title or "").startswith("Placeholder for")}

rng = random.Random(SEED)
# Type A: "prerequisites for X", gold = codes in X's prerequisite text (1-4 codes, all real courses).
pool_a = sorted(cid for cid, c in courses.items() if 1 <= len(codes(c.prereq_text) - {cid}) <= 4
                and codes(c.prereq_text) - {cid} <= courses.keys())
# Type B: "what requires X", gold = real courses whose prerequisite text names X (2-5 of them).
requiring = {}
for cid, c in courses.items():
    for p in codes(c.prereq_text) - {cid}:
        requiring.setdefault(p, set()).add(cid)
pool_b = sorted(p for p, req in requiring.items() if p in courses and 2 <= len(req) <= 5)

questions = [{"type": "prereqs_of", "q": f"What are the prerequisites for {x}?",
              "gold": sorted(codes(courses[x].prereq_text) - {x})} for x in rng.sample(pool_a, N)]
templates = ["What courses require {x}?", "What can I take after {x}?"]
questions += [{"type": "requires", "q": templates[i % 2].format(x=x), "gold": sorted(requiring[x])}
              for i, x in enumerate(rng.sample(pool_b, N))]

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)  # same model and temperature as qa_agent


def vector_only(q):
    """Plain RAG baseline: top-5 vector hits, same model, no router or SQL enrichment."""
    blocks = []
    for hit in semantic_search(q, n_results=5):
        if "program_text" in hit:
            blocks.append(hit["program_text"])
        elif (c := courses.get(hit["course_id"])):
            blocks.append(f"{c.id}: {c.title}. {c.description or ''} {c.prereq_text or ''} {c.coreq_text or ''}")
    prompt = ("You are a McGill course advisor. Answer the question using only the context.\n\n"
              "Context:\n" + "\n\n".join(blocks) + f"\n\nQuestion: {q}\nAnswer clearly and concisely:")
    return llm.invoke(prompt).content


results = []
for item in questions:
    row = dict(item)
    for name, fn in (("pipeline", lambda q: qa_agent.generate_answer(q)["answer"]), ("vector_only", vector_only)):
        t = time.perf_counter()
        answer = fn(item["q"])
        row[name] = {"correct": set(item["gold"]) <= codes(answer), "ms": round((time.perf_counter() - t) * 1000),
                     "answer": answer}
    results.append(row)
    print(f"{row['type']:10} pipeline={row['pipeline']['correct']!s:5} vector={row['vector_only']['correct']!s:5} {item['q']}", flush=True)

json.dump(results, open(os.path.join(os.path.dirname(__file__), "eval_results.json"), "w"), indent=1)
for name in ("pipeline", "vector_only"):
    for t in ("prereqs_of", "requires", None):
        rows = [r for r in results if t is None or r["type"] == t]
        ok = sum(r[name]["correct"] for r in rows)
        ms = sorted(r[name]["ms"] for r in rows)[len(rows) // 2]
        print(f"{name:12} {t or 'all':10} {ok}/{len(rows)} correct, median {ms} ms")
