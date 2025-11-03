from sqlalchemy.orm import Session
from db_connection import Session as DBSession
from db_setup import Course, PrereqEdge

def get_prereqs(course_id: str) -> list[str]:
    """Return a list of prerequisite course IDs for a given course."""
    with DBSession() as session:
        prereqs = (
            session.query(PrereqEdge.src_course_id)
            .filter(PrereqEdge.dst_course_id == course_id, PrereqEdge.kind == "prereq")
            .all()
        )
        return [p[0] for p in prereqs]

def get_coreqs(course_id: str) -> list[str]:
    """Return a list of corequisite course IDs for a given course."""
    with DBSession() as session:
        coreqs = (
            session.query(PrereqEdge.src_course_id)
            .filter(PrereqEdge.dst_course_id == course_id, PrereqEdge.kind == "coreq")
            .all()
        )
        return [c[0] for c in coreqs]

def can_take_course(completed_courses: list[str], current_courses: list[str], target_course: str) -> dict:
    """Determine if a student can take the target course based on completed prerequisites and current coreqs."""
    prereqs = get_prereqs(target_course)
    coreqs = get_coreqs(target_course)

    # Missing prerequisites = not completed before
    missing_prereqs = [p for p in prereqs if p not in completed_courses]

    # Missing corequisites = not completed or currently enrolled
    missing_coreqs = [c for c in coreqs if c not in completed_courses and c not in current_courses]
    eligible = len(missing_prereqs) == 0 and len(missing_coreqs) == 0

    return {
        "course": target_course,
        "eligible": eligible,
        "missing_prereqs": missing_prereqs,
        "missing_coreqs": missing_coreqs,
        "total_prereqs": len(prereqs),
        "total_coreqs": len(coreqs)
    }
