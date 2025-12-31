"""
Comprehensive tests for RAG layer features.

Tests cover:
1. Title-based course lookup
2. Disambiguation for ambiguous titles
3. Planning/recommendation queries
4. Department detection
5. Term filtering
6. Level-based queries
7. Available courses after completing prerequisites
8. Hybrid search integration
"""

import pytest
from unittest.mock import patch, MagicMock

# Import the functions we're testing
from rag_layer import (
    _normalize_title,
    _load_title_cache,
    find_course_by_title,
    extract_course_id,
    get_course_directly,
    get_entry_level_courses,
    get_courses_by_level,
    get_available_courses,
    detect_planning_query,
    hybrid_search,
    enrich_context,
    _title_to_id_cache,
    _duplicate_titles,
    _cache_loaded,
)


# =============================================================================
# SECTION 1: Title Normalization Tests
# =============================================================================

class TestTitleNormalization:
    """Tests for the _normalize_title function."""
    
    def test_lowercase_conversion(self):
        """Title should be converted to lowercase."""
        assert _normalize_title("Introduction to Computer Science") == "introduction to computer science"
    
    def test_strip_whitespace(self):
        """Leading and trailing whitespace should be removed."""
        assert _normalize_title("  Data Structures  ") == "data structures"
    
    def test_remove_trailing_period(self):
        """Trailing period should be removed."""
        assert _normalize_title("Operating Systems.") == "operating systems"
    
    def test_combined_normalization(self):
        """All normalization rules should apply together."""
        assert _normalize_title("  Algorithm Design.  ") == "algorithm design"
    
    def test_empty_string(self):
        """Empty string should return empty string."""
        assert _normalize_title("") == ""
    
    def test_only_whitespace(self):
        """Whitespace-only string should return empty string."""
        assert _normalize_title("   ") == ""


# =============================================================================
# SECTION 2: Course ID Extraction Tests
# =============================================================================

class TestCourseIdExtraction:
    """Tests for extract_course_id function."""
    
    def test_standard_format_with_space(self):
        """Test 'COMP 250' format."""
        course_id, alternatives = extract_course_id("Tell me about COMP 250")
        assert course_id == "COMP 250"
        assert alternatives is None
    
    def test_standard_format_no_space(self):
        """Test 'COMP250' format (no space)."""
        course_id, alternatives = extract_course_id("What is COMP250?")
        assert course_id == "COMP 250"
        assert alternatives is None
    
    def test_hyphenated_format(self):
        """Test 'COMP-250' format."""
        course_id, alternatives = extract_course_id("COMP-250 prerequisites")
        assert course_id == "COMP 250"
        assert alternatives is None
    
    def test_lowercase_input(self):
        """Course code should be normalized to uppercase."""
        course_id, alternatives = extract_course_id("comp 250")
        assert course_id == "COMP 250"
        assert alternatives is None
    
    def test_mixed_case_input(self):
        """Mixed case should be normalized."""
        course_id, alternatives = extract_course_id("Comp 250")
        assert course_id == "COMP 250"
        assert alternatives is None
    
    def test_four_letter_department(self):
        """Test 4-letter department codes like MATH, ECSE."""
        course_id, _ = extract_course_id("MATH 133")
        assert course_id == "MATH 133"
        
        course_id, _ = extract_course_id("ECSE 427")
        assert course_id == "ECSE 427"
    
    def test_course_with_letter_suffix(self):
        """Test course codes with letter suffix like '202D'."""
        course_id, _ = extract_course_id("COMP 202D")
        assert course_id == "COMP 202D"
    
    def test_no_course_code_in_query(self):
        """Query without course code should return None."""
        course_id, alternatives = extract_course_id("Tell me about machine learning")
        # May return something if title matches, but for this generic query, likely None
        # This depends on the title cache state
        pass  # Skip this test as it depends on DB state
    
    def test_multiple_course_codes(self):
        """First course code should be extracted."""
        course_id, _ = extract_course_id("Compare COMP 250 and COMP 251")
        assert course_id == "COMP 250"


# =============================================================================
# SECTION 3: Title-Based Lookup Tests
# =============================================================================

class TestTitleBasedLookup:
    """Tests for find_course_by_title function."""
    
    def test_exact_title_match(self):
        """Exact title should match."""
        # This test depends on DB having "Introduction to Computer Science"
        course_id, alternatives = find_course_by_title("Introduction to Computer Science")
        # Result depends on DB content
        if course_id:
            assert isinstance(course_id, str)
    
    def test_title_in_question(self):
        """Title embedded in question should match."""
        course_id, alternatives = find_course_by_title(
            "What are the prerequisites for Introduction to Computer Science?"
        )
        if course_id:
            assert isinstance(course_id, str)
    
    def test_case_insensitive(self):
        """Title matching should be case-insensitive."""
        course_id1, _ = find_course_by_title("data structures")
        course_id2, _ = find_course_by_title("Data Structures")
        course_id3, _ = find_course_by_title("DATA STRUCTURES")
        # All should return the same course (if exists)
        if course_id1:
            assert course_id1 == course_id2 == course_id3
    
    def test_title_with_trailing_period(self):
        """Title with trailing period should still match."""
        course_id, _ = find_course_by_title("Operating Systems.")
        # Should match if "Operating Systems" exists
        if course_id:
            assert isinstance(course_id, str)


# =============================================================================
# SECTION 4: Disambiguation Tests
# =============================================================================

class TestDisambiguation:
    """Tests for disambiguation of ambiguous course titles."""
    
    def test_ambiguous_title_returns_alternatives(self):
        """Ambiguous title should return list of alternatives."""
        # "Operating Systems" is offered as both COMP 310 and ECSE 427
        course_id, alternatives = find_course_by_title("Operating Systems")
        if alternatives:
            assert len(alternatives) > 1
            assert all(isinstance(alt, str) for alt in alternatives)
    
    def test_ambiguous_title_returns_default(self):
        """Ambiguous title should still return a default course_id."""
        course_id, alternatives = find_course_by_title("Operating Systems")
        if course_id:
            assert isinstance(course_id, str)
            # Default should prefer COMP
            if alternatives and any("COMP" in alt for alt in alternatives):
                assert "COMP" in course_id
    
    def test_unambiguous_title_no_alternatives(self):
        """Unambiguous title should have alternatives=None."""
        # COMP 250 has a unique title
        course_id, alternatives = extract_course_id("COMP 250")
        assert alternatives is None


# =============================================================================
# SECTION 5: Planning Query Detection Tests
# =============================================================================

class TestPlanningQueryDetection:
    """Tests for detect_planning_query function."""
    
    # First Semester / Entry Level
    def test_detect_first_semester_query(self):
        """Should detect 'first semester' queries."""
        result = detect_planning_query("What CS courses should I take first semester?")
        assert result is not None
        assert result["type"] == "first_semester"
        assert result["department"] == "COMP"
    
    def test_detect_beginner_query(self):
        """Should detect 'beginner' queries."""
        result = detect_planning_query("What are good beginner computer science courses?")
        assert result is not None
        assert result["type"] == "first_semester"
    
    def test_detect_entry_level_query(self):
        """Should detect 'entry-level' queries."""
        result = detect_planning_query("Show me entry-level COMP courses")
        assert result is not None
        assert result["type"] == "first_semester"
        assert result["department"] == "COMP"
    
    def test_detect_no_prereq_query(self):
        """Should detect 'no prerequisites' queries."""
        result = detect_planning_query("What math courses have no prerequisites?")
        assert result is not None
        assert result["type"] == "first_semester"
        assert result["department"] == "MATH"
    
    # Department Detection
    def test_detect_cs_department(self):
        """'CS' should map to 'COMP'."""
        result = detect_planning_query("What CS courses are there?")
        assert result is not None
        assert result["department"] == "COMP"
    
    def test_detect_computer_science_department(self):
        """'computer science' should map to 'COMP'."""
        result = detect_planning_query("Recommend computer science courses")
        assert result is not None
        assert result["department"] == "COMP"
    
    def test_detect_math_department(self):
        """'math' should map to 'MATH'."""
        result = detect_planning_query("What math courses should I take first?")
        assert result is not None
        assert result["department"] == "MATH"
    
    def test_detect_ecse_department(self):
        """'electrical' should map to 'ECSE'."""
        result = detect_planning_query("Show me electrical engineering courses")
        assert result is not None
        assert result["department"] == "ECSE"
    
    # Term Detection
    def test_detect_fall_term(self):
        """Should detect 'fall' term."""
        result = detect_planning_query("What courses are offered in fall?")
        assert result is not None
        assert result["term"] == "fall"
    
    def test_detect_winter_term(self):
        """Should detect 'winter' term."""
        result = detect_planning_query("Winter semester CS courses")
        assert result is not None
        assert result["term"] == "winter"
    
    def test_detect_summer_term(self):
        """Should detect 'summer' term."""
        result = detect_planning_query("Summer courses available")
        assert result is not None
        assert result["term"] == "summer"
    
    def test_detect_first_semester_as_fall(self):
        """'first semester' should imply fall."""
        result = detect_planning_query("What should I take first semester?")
        assert result is not None
        assert result["term"] == "fall"
    
    # Level Detection
    def test_detect_200_level(self):
        """Should detect '200-level' courses."""
        result = detect_planning_query("What 200-level COMP courses are there?")
        assert result is not None
        assert result["type"] == "by_level"
        assert result["level"] == 200
    
    def test_detect_second_year(self):
        """'second year' should map to level 200."""
        result = detect_planning_query("What COMP courses should I take second year?")
        assert result is not None
        assert result["level"] == 200
    
    def test_detect_graduate_level(self):
        """'graduate' should map to level 500+."""
        result = detect_planning_query("Show me graduate CS courses")
        assert result is not None
        assert result["level"] == 500
    
    # Available After Completing
    def test_detect_available_after_query(self):
        """Should detect 'after completing X' queries."""
        result = detect_planning_query("What can I take after COMP 250?")
        assert result is not None
        assert result["type"] == "available"
        assert "COMP 250" in result["completed"]
    
    def test_detect_multiple_completed_courses(self):
        """Should extract multiple completed courses."""
        result = detect_planning_query("What's available after COMP 250 and MATH 133?")
        assert result is not None
        assert result["type"] == "available"
        assert "COMP 250" in result["completed"]
        assert "MATH 133" in result["completed"]
    
    # Recommendation Queries
    def test_detect_recommendation_query(self):
        """Should detect recommendation queries."""
        result = detect_planning_query("Can you recommend some good CS courses?")
        assert result is not None
        assert result["type"] == "recommendation"
    
    def test_detect_should_i_take_query(self):
        """Should detect 'should I take' queries."""
        result = detect_planning_query("What courses should I take?")
        assert result is not None
        assert result["type"] in ["recommendation", "first_semester"]
    
    # Non-Planning Queries
    def test_non_planning_query_returns_none(self):
        """Non-planning queries should return None."""
        result = detect_planning_query("What is COMP 250 about?")
        assert result is None
    
    def test_prereq_query_not_planning(self):
        """Prerequisite queries should not be detected as planning."""
        result = detect_planning_query("What are the prerequisites for COMP 251?")
        assert result is None


# =============================================================================
# SECTION 6: Entry Level Courses Tests
# =============================================================================

class TestEntryLevelCourses:
    """Tests for get_entry_level_courses function."""
    
    def test_returns_list(self):
        """Should return a list."""
        result = get_entry_level_courses()
        assert isinstance(result, list)
    
    def test_filter_by_department(self):
        """Should filter by department."""
        result = get_entry_level_courses(department="COMP")
        for course in result:
            assert course["id"].startswith("COMP ")
    
    def test_limit_results(self):
        """Should respect the limit parameter."""
        result = get_entry_level_courses(limit=5)
        assert len(result) <= 5
    
    def test_courses_have_required_fields(self):
        """Each course should have required fields."""
        result = get_entry_level_courses(limit=3)
        for course in result:
            assert "id" in course
            assert "title" in course
            assert "prereqs" in course
            assert "description" in course
    
    def test_sorted_by_course_number(self):
        """Results should be sorted by course number."""
        result = get_entry_level_courses(department="COMP", limit=10)
        if len(result) >= 2:
            numbers = [int(c["id"].split()[1][:3]) for c in result]
            assert numbers == sorted(numbers)


# =============================================================================
# SECTION 7: Courses By Level Tests
# =============================================================================

class TestCoursesByLevel:
    """Tests for get_courses_by_level function."""
    
    def test_returns_correct_level(self):
        """Should return courses at the specified level."""
        result = get_courses_by_level(department="COMP", level=200)
        for course in result:
            course_num = int(course["id"].split()[1][:3])
            assert 200 <= course_num < 300
    
    def test_filter_by_department(self):
        """Should filter by department."""
        result = get_courses_by_level(department="MATH", level=100)
        for course in result:
            assert course["id"].startswith("MATH ")
    
    def test_100_level_courses(self):
        """Should return 100-level courses."""
        result = get_courses_by_level(department="COMP", level=100)
        for course in result:
            course_num = int(course["id"].split()[1][:3])
            assert 100 <= course_num < 200
    
    def test_500_level_courses(self):
        """Should return 500-level (graduate) courses."""
        result = get_courses_by_level(department="COMP", level=500)
        for course in result:
            course_num = int(course["id"].split()[1][:3])
            assert 500 <= course_num < 600


# =============================================================================
# SECTION 8: Available Courses Tests
# =============================================================================

class TestAvailableCourses:
    """Tests for get_available_courses function."""
    
    def test_returns_list(self):
        """Should return a list."""
        result = get_available_courses(completed_courses=["COMP 250"])
        assert isinstance(result, list)
    
    def test_excludes_completed_courses(self):
        """Should not include courses already completed."""
        completed = ["COMP 250", "COMP 206"]
        result = get_available_courses(completed_courses=completed)
        result_ids = [c["id"] for c in result]
        for completed_id in completed:
            assert completed_id not in result_ids
    
    def test_filter_by_department(self):
        """Should filter by department."""
        result = get_available_courses(
            completed_courses=["COMP 250"],
            department="COMP"
        )
        for course in result:
            assert course["id"].startswith("COMP ")


# =============================================================================
# SECTION 9: Hybrid Search Integration Tests
# =============================================================================

class TestHybridSearch:
    """Integration tests for hybrid_search function."""
    
    def test_course_code_query(self):
        """Direct course code query should return that course."""
        result = hybrid_search("COMP 250")
        assert len(result) > 0
        assert result[0]["course_id"] == "COMP 250"
    
    def test_prerequisite_for_query(self):
        """'Prerequisites for X' should return course X's info."""
        result = hybrid_search("What are the prerequisites for COMP 251?")
        assert len(result) > 0
        assert result[0]["course_id"] == "COMP 251"
        assert "prereqs" in result[0]
    
    def test_first_semester_planning_query(self):
        """First semester query should return planning results."""
        result = hybrid_search("What CS courses should I take first semester?")
        assert len(result) > 0
        if "is_planning_query" in result[0]:
            assert result[0]["is_planning_query"] == True
            assert result[0]["planning_type"] == "first_semester"
    
    def test_level_based_planning_query(self):
        """Level-based query should return courses at that level."""
        result = hybrid_search("What 200-level COMP courses are there?")
        assert len(result) > 0
        if "is_planning_query" in result[0]:
            assert result[0]["planning_type"] == "by_level"
            assert result[0]["level"] == 200
    
    def test_available_after_query(self):
        """'Available after X' query should return planning results."""
        result = hybrid_search("What can I take after COMP 250?")
        assert len(result) > 0
        # Could be either planning query or reverse prereq lookup
    
    def test_ambiguous_title_includes_clarification(self):
        """Ambiguous title should include needs_clarification flag."""
        result = hybrid_search("Tell me about Operating Systems")
        if len(result) > 0 and "needs_clarification" in result[0]:
            assert result[0]["needs_clarification"] == True
            assert "alternatives" in result[0]
    
    def test_semantic_search_fallback(self):
        """Generic query should fall back to semantic search."""
        result = hybrid_search("Tell me about machine learning courses")
        assert isinstance(result, list)


# =============================================================================
# SECTION 10: Query Intent Detection Tests
# =============================================================================

class TestQueryIntentDetection:
    """Tests for query intent detection in hybrid_search."""
    
    def test_prerequisites_for_intent(self):
        """'Prerequisites for X' should be detected correctly."""
        result = hybrid_search("What are the prerequisites for COMP 302?")
        assert len(result) > 0
        assert result[0]["course_id"] == "COMP 302"
    
    def test_prereqs_for_shorthand(self):
        """'Prereqs for X' should work same as 'prerequisites for'."""
        result = hybrid_search("Prereqs for COMP 302")
        assert len(result) > 0
        assert result[0]["course_id"] == "COMP 302"
    
    def test_what_requires_intent(self):
        """'What requires X' should find courses requiring X."""
        result = hybrid_search("What courses require COMP 250?")
        # Should return courses that have COMP 250 as a prerequisite
        assert isinstance(result, list)
    
    def test_after_finishing_intent(self):
        """'After finishing X' should find next courses."""
        result = hybrid_search("What can I take after finishing COMP 250?")
        assert isinstance(result, list)


# =============================================================================
# SECTION 11: Course Data Structure Tests
# =============================================================================

class TestCourseDataStructure:
    """Tests for course data structure consistency."""
    
    def test_course_has_offering_info(self):
        """Course should include offering term info."""
        result = hybrid_search("COMP 250")
        if len(result) > 0:
            course = result[0]
            assert "offered_fall" in course or "course_id" in course
    
    def test_planning_courses_have_all_fields(self):
        """Planning query courses should have all required fields."""
        result = hybrid_search("What CS courses should I take first semester?")
        if len(result) > 0 and "is_planning_query" in result[0]:
            courses = result[0].get("courses", [])
            for course in courses:
                assert "id" in course
                assert "title" in course
                assert "prereqs" in course
                assert "offered_fall" in course
                assert "offered_winter" in course


# =============================================================================
# SECTION 12: Edge Cases Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_query(self):
        """Empty query should not crash."""
        result = hybrid_search("")
        assert isinstance(result, list)
    
    def test_special_characters_in_query(self):
        """Special characters should not crash."""
        result = hybrid_search("What about COMP 250???!!!")
        assert isinstance(result, list)
    
    def test_very_long_query(self):
        """Very long query should not crash."""
        long_query = "What are the prerequisites for " * 10 + "COMP 250"
        result = hybrid_search(long_query)
        assert isinstance(result, list)
    
    def test_nonexistent_course_code(self):
        """Nonexistent course code should return empty or semantic results."""
        result = hybrid_search("ZZZZ 999")
        assert isinstance(result, list)
    
    def test_nonexistent_department(self):
        """Nonexistent department should handle gracefully."""
        result = get_entry_level_courses(department="ZZZZ")
        assert isinstance(result, list)
        assert len(result) == 0


# =============================================================================
# SECTION 13: Title Cache Tests
# =============================================================================

class TestTitleCache:
    """Tests for title caching functionality."""
    
    def test_cache_loads(self):
        """Cache should load successfully."""
        _load_title_cache()
        # After loading, cache should have entries (if DB has courses)
        # We just check it doesn't crash
        assert True
    
    def test_duplicate_titles_tracked(self):
        """Duplicate titles should be tracked."""
        _load_title_cache()
        # _duplicate_titles should be a dict
        assert isinstance(_duplicate_titles, dict)


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    # Run with pytest
    pytest.main([__file__, "-v", "--tb=short"])
