from scraper import fetch_html, parse_course_page
from db_utils import save_course
from db_setup import Base, Course # Import Base here
from db_connection import Session, engine

# Connect the models to the engine and create tables
Base.metadata.create_all(engine)

# Pick a real course page (example COMP 273)
url = "https://coursecatalogue.mcgill.ca/courses/comp-273/index.html"

# Step 1: Fetch HTML and parse course data
html = fetch_html(url)
course_data = parse_course_page(html)
print("✅ Scraped data:\n", course_data)

# Step 2: Save into the database
with Session() as session:
    save_course(session, course_data)

# Step 3: Query back from DB to confirm it’s saved
with Session() as session:
    saved = session.query(Course).filter_by(id=course_data['id']).first()
    print("\n✅ Saved in DB:")
    print("ID:", saved.id)
    print("Title:", saved.title)
    print("Credits:", saved.credits)
    print("Offered by:", saved.offered_by)
