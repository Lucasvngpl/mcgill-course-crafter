# deterministic_logic.py
import re
from db_connection import Session as DBSession
from db_setup import Course

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
