from db_setup import Base, Course
from db_connection import engine

print("Dropping all tables...")
# This will drop the 'courses' and 'prereq_edge' tables
Base.metadata.drop_all(engine)
print("Tables dropped.")

print("Creating all tables...")
# This will re-create them with the correct schema
Base.metadata.create_all(engine)
print("Tables created.")