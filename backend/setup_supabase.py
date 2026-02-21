# Creates ALL tables on Supabase (courses, prereq_edge, user tables)
# Run this once to set up the schema. Safe to re-run — create_all()
# only creates tables that don't already exist (won't touch existing data)
from dotenv import find_dotenv, load_dotenv
from sqlalchemy import create_engine
# Importing Base also imports all models that inherit from it
# (Course, PrereqEdge, UserProfile, UserCourse, ChatMessage)
from db_setup import Base
import os

# Load environment variables from .env file
load_dotenv(find_dotenv())

# DATABASE_URL points to Supabase pooler connection string
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

# create_all() looks at every class that inherits from Base
# and runs CREATE TABLE for each one (only if it doesn't already exist)
Base.metadata.create_all(engine)

print("Tables created successfully on Supabase!")
