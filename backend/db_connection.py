# db_connection.py
# This file sets up the database connection and session factory.
import os
import pathlib
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load environment variables from backend/.env explicitly
# override=True ensures our .env wins over any system-level DATABASE_URL
env_path = pathlib.Path(__file__).parent / ".env"
load_dotenv(env_path, override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

# Create database engine
engine = create_engine(DATABASE_URL) #This connects to your Postgres instance using your .env file’s DATABASE_URL.

# Create session factory
Session = sessionmaker(bind=engine) #this gives you a Session class that you can use in other files (like db_utils.py) to talk to the DB:
