# deterministic_logic.py
import re
from db_connection import Session as DBSession
from db_setup import Course, PrereqEdge

def get_prereqs(course_id: str):
    """Return a list of prerequisite course IDs for a given course."""
    with DBSession() as session:
        prereqs = (
            session.query(PrereqEdge.src_course_id)
            .filter(PrereqEdge.dst_course_id == course_id, PrereqEdge.kind == "prereq")
            .all()
        )
        return [p[0] for p in prereqs]

def get_coreqs(course_id: str):
    """Return a list of corequisite course IDs for a given course."""
    with DBSession() as session:
        coreqs = (
            session.query(PrereqEdge.src_course_id)
            .filter(PrereqEdge.dst_course_id == course_id, PrereqEdge.kind == "coreq")
            .all()
        )
        return [c[0] for c in coreqs]

def get_courses_requiring(course_id: str):
    """Return a list of courses that list this course as a prerequisite."""
    if not course_id:
        return []

    # Normalize variants: COMP250, COMP-250 → COMP 250
    normalized = course_id.replace("-", " ").upper()
    # Match COMP250, COMP-250, COMP 250
    pattern = re.compile(rf'\b{normalized.replace(" ", "[- ]?")}\b', re.IGNORECASE)
    with DBSession() as session:
        matches = []
        # Query courses that have prerequisite text
        # This tells SQLAlechemy “I only care about the id and prereq_text columns from the Course table.”
        #
        results = session.query(Course.id, Course.prereq_text).filter(Course.prereq_text.isnot(None)).all() # Adds a SQL condition so you only pull rows where the prereq_text field isn’t null.
        for cid, text in results:
            if text and pattern.search(text):
                matches.append(cid)
    return matches

    # with DBSession() as session:
    #     required = ( # courses that require the given course as a prerequisite
    #         session.query(PrereqEdge.dst_course_id) 
    #         .filter(PrereqEdge.src_course_id == course_id, PrereqEdge.kind == "prereq") # filter for prereqs
    #         .all()
    #     )
    #     return [r[0] for r in required]

def can_take_course(completed_courses: list, current_courses: list, target_course: str):
    """Determine if a student can take a given course based on completed and current courses."""
    prereqs = get_prereqs(target_course)
    coreqs = get_coreqs(target_course)

    missing_prereqs = [p for p in prereqs if p not in completed_courses]
    missing_coreqs = [c for c in coreqs if c not in completed_courses + current_courses]

    eligible = len(missing_prereqs) == 0 and len(missing_coreqs) == 0

    return {
        "course": target_course,
        "eligible": eligible,
        "missing_prereqs": missing_prereqs,
        "missing_coreqs": missing_coreqs,
        "total_prereqs": len(prereqs),
        "total_coreqs": len(coreqs),
    }
