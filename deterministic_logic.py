# deterministic_logic.py
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
    with DBSession() as session:
        required = (
            session.query(PrereqEdge.dst_course_id)
            .filter(PrereqEdge.src_course_id == course_id, PrereqEdge.kind == "prereq")
            .all()
        )
        return [r[0] for r in required]

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
