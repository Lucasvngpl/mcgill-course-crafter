from db_setup import Course, PrereqEdge

def save_course(session, course_data: dict):
    """Saves a course and its prerequisite edges to the database."""
    
    # This single line replaces the 10 lines of manual get/update logic.
    # It creates or updates the course in one step.
    course_details = {k: v for k, v in course_data.items() if k not in ['prereq_edges', 'coreq_edges']}
    course = session.merge(Course(**course_details))
    session.add(course)

    # Add prereq/coreq edges
    edges = course_data.get("prereq_edges", []) + course_data.get("coreq_edges", [])


    for edge_data in edges:
        # For each edge, ensure the source course exists (even as a placeholder)
        src_course_id = edge_data['src_course_id']
        src_course = session.get(Course, src_course_id)
        if not src_course:
            # Extract department code from course ID (e.g., "COMP" from "COMP 206")
            dept_code = src_course_id.split()[0]
            
            # Use a placeholder format that's consistent with what we'll get from scraping, bc we haven't scraped it yet but want to avoid nulls
            placeholder_dept = f"{dept_code} Department (Faculty placeholder)"
            
            # Use merge here too for consistency and safety
            src_course = session.merge(Course(
                id=src_course_id, 
                title=f"Placeholder for {src_course_id}", 
                description="N/A", 
                credits=0.0,
                offered_by=placeholder_dept  # More descriptive placeholder
            ))
            session.add(src_course)

        
    session.commit()