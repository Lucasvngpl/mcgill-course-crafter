import re
from scraper import fetch_html, parse_course_page, get_all_course_links
from db_utils import save_course
from db_connection import Session
from db_setup import Course 

BASE_URL = "https://coursecatalogue.mcgill.ca/courses/"

# Main function to orchestrate the scraping and saving process
def main():
    print("🔍 Fetching course list from all departments...")
    # Use our new function to get course links from all departments
    course_links = get_all_course_links()
    print(f"Found {len(course_links)} total courses to process.")

    # Use a single session for all DB operations in this run
    with Session() as session:
        for idx, course_url in enumerate(course_links, start=1):
            print(f"({idx}/{len(course_links)}) 📄 Fetching {course_url}...")
            # Extract course ID from URL to check if it's already in the database
            match = re.search(r'/courses/([a-z]{3,4})-(\d{3}[a-z]?)/?', course_url, re.IGNORECASE)
            if match:
                dept, num = match.groups() #
                course_id = f"{dept.upper()} {num.upper()}"
                
                # Check if the course already exists in the database
                existing_course = session.query(Course).filter_by(id=course_id).first()
                if existing_course:
                    print(f"   ✅ Course {course_id} already in database, skipping.")
                    continue



            try:
                course_html = fetch_html(course_url)
                course_data = parse_course_page(course_html)
                if course_data:
                    print(f"   💾 Saving {course_data['id']} - {course_data['title']}...")
                    save_course(session, course_data)
                else:
                    print(f"   ⚠️  Failed to parse course data from {course_url}")
            except Exception as e:
                print(f"   ❌ Error processing {course_url}: {str(e)}")

if __name__ == "__main__":
    main()