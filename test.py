from db_connection import Session
from db_setup import PrereqEdge

session = Session()
edges = session.query(PrereqEdge).limit(5).all()
for e in edges:
    print(e.src_course_id, "→", e.dst_course_id, e.kind)
