# from db_connection import Session
# from db_setup import Course
# with Session() as s:
#     print("db_course_count =", s.query(Course).count())

# from rag_layer import load_course_docs
# docs = load_course_docs()
# print("docs_count =", len(docs))
# print("sample_docs =", docs[:3])
# import rag_layer
# rag_layer.build_vector_store()
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")
import os
from qa_agent import generate_answer


# from deterministic_logic import get_courses_requiring

# for q in ["COMP 250", "COMP-250", "COMP250", "comp 250"]:
#     print(q, "->", get_courses_requiring(q))




print("Key loaded:", bool(os.getenv("OPENAI_API_KEY")))

print(generate_answer('Which courses require COMP 250?'))