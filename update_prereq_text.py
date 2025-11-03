import re
from scraper import fetch_html, parse_course_page
from db_connection import Session
from db_setup import Course

BASE_URL = "https://coursecatalogue.mcgill.ca/courses/"

def main():
    print("🔄 Updating prerequisite and corequisite text for existing courses...")
    
    with Session() as session:
        # Get all courses from the database
        courses = session.query(Course).all()
        total = len(courses)
        print(f"Found {total} courses in database to update")
        
        for idx, course in enumerate(courses, start=1):
            # Generate the URL for the course
            url_safe_id = course.id.replace(' ', '-').lower()
            course_url = f"{BASE_URL}{url_safe_id}/index.html"
            
            print(f"({idx}/{total}) 📄 Updating {course.id} - {course.title}...")
            
            try:
                # Fetch the page and use your existing parsing logic
                course_html = fetch_html(course_url)
                parsed_data = parse_course_page(course_html, course_url)
                
                # Update just the prereq and coreq text fields
                if 'prereq_text' in parsed_data:
                    course.prereq_text = parsed_data['prereq_text']
                    print(f"   ✅ Updated prereq text: {parsed_data['prereq_text'][:50]}...")
                
                if 'coreq_text' in parsed_data:
                    course.coreq_text = parsed_data['coreq_text']
                    print(f"   ✅ Updated coreq text: {parsed_data['coreq_text'][:50]}...")
                
                # Commit changes for each course
                session.commit()
                
            except Exception as e:
                print(f"   ❌ Error updating {course.id}: {str(e)}")
                session.rollback()

    print("✅ Update complete!")

if __name__ == "__main__":
    main()