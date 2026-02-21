# file that defines your database tables in Postgresql using SQLAlchemy ORM
from sqlalchemy import (
    String, Boolean, Text, DECIMAL, ForeignKey, DateTime, Integer, UUID
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
import uuid


# 1) Base class for all our database tables
class Base(DeclarativeBase):
    pass

# 2) Table for courses
class Course(Base):
    __tablename__ = "courses"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g., 'COMP-250'
    title: Mapped[str] = mapped_column(String, nullable=False) # course title
    description: Mapped[str] = mapped_column(Text, nullable=False) # long description
    credits: Mapped[float] = mapped_column(DECIMAL(3, 1)) # e.g., 3.0
    offered_by: Mapped[str] = mapped_column(String)     # e.g., COMP

    offered_fall: Mapped[bool] = mapped_column(Boolean, default=False)
    offered_winter: Mapped[bool] = mapped_column(Boolean, default=False)
    offered_summer: Mapped[bool] = mapped_column(Boolean, default=False)

    # Store entire corequisite and prerequisite sentence, not just course IDs
    prereq_text: Mapped[str] = mapped_column(Text, default="")
    coreq_text: Mapped[str] = mapped_column(Text, default="")


# 3) Table for prerequisites (edges between courses)
class PrereqEdge(Base):
    __tablename__ = "prereq_edge"

    src_course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), primary_key=True)
    dst_course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String, primary_key=True)  # "prereq", "coreq", etc.


# ──────────────────────────────────────────────────────────────
# USER TABLES (linked to Supabase Auth via user_id = auth.users.id)
# ──────────────────────────────────────────────────────────────

# 4) User profile — one row per user, stores academic identity
# Created after first sign-in or when onboarding completes
# user_id comes from Supabase Auth (auth.users.id), which is a UUID
class UserProfile(Base):
    __tablename__ = "user_profiles"

    # Primary key = the Supabase Auth user UUID (not auto-generated, we set it)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)

    # Academic identity
    year_standing: Mapped[str | None] = mapped_column(String, nullable=True)   # U0, U1, U2, U3
    program: Mapped[str | None] = mapped_column(String, nullable=True)         # e.g., "B.Sc."
    major: Mapped[str | None] = mapped_column(String, nullable=True)           # e.g., "Computer Science"
    minor: Mapped[str | None] = mapped_column(String, nullable=True)           # e.g., "Mathematics"

    # Free-text fields for things that don't fit in structured columns
    interests: Mapped[str | None] = mapped_column(Text, nullable=True)         # e.g., "AI, systems programming"
    constraints: Mapped[str | None] = mapped_column(Text, nullable=True)       # e.g., "no 8:30am classes"
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)             # catch-all for anything else

    # Tracks whether the user has completed the onboarding chat
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# 5) User courses — every course a user has taken, is taking, or plans to take
# This is the MERGED table (academic_history + course_plans in one)
# status field distinguishes: "completed", "in_progress", "planned"
class UserCourse(Base):
    __tablename__ = "user_courses"

    # Auto-generated integer primary key (each row is one user-course relationship)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Which user this belongs to (FK to Supabase Auth)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)

    # Which course (FK to our courses table, e.g., "COMP-250")
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), nullable=False)

    # "completed", "in_progress", or "planned"
    status: Mapped[str] = mapped_column(String, nullable=False)

    # When they took/plan to take it
    term: Mapped[str | None] = mapped_column(String, nullable=True)            # "fall", "winter", "summer"
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)           # e.g., 2025

    # Only relevant for completed courses
    grade: Mapped[str | None] = mapped_column(String, nullable=True)           # e.g., "A-", "B+", "pass"

    # Where did this info come from?
    source: Mapped[str] = mapped_column(String, default="manual")              # "manual" or "extracted" (from chat)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# 6) Chat messages — conversation log between user and assistant
# Stored so users can see their chat history when they come back
# Also used to display conversation in the UI
class ChatMessage(Base):
    __tablename__ = "chat_messages"

    # Auto-generated integer primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Which user sent/received this message
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)

    # Groups messages into conversations (user might have multiple chat sessions)
    session_id: Mapped[str] = mapped_column(String, nullable=False)

    # "user" or "assistant"
    role: Mapped[str] = mapped_column(String, nullable=False)

    # The actual message text
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
