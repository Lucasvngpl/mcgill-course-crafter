# file that defines your database tables in Postgresql using SQLAlchemy ORM
from sqlalchemy import (
    String, Boolean, Text, DECIMAL, ForeignKey
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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

# 3) Table for prerequisites (edges between courses)
class PrereqEdge(Base):
    __tablename__ = "prereq_edge"

    src_course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), primary_key=True)
    dst_course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String, primary_key=True)  # "prereq", "coreq", etc.
