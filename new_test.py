from course_logic import can_take_course

# Add error handling
try:
    completed = ["COMP 202", "COMP 250", "MATH 240"]
    current = ["COMP 251"]
    
    print("Checking prerequisites for COMP 360...")
    result = can_take_course(completed, current, "COMP 360")
    print("Result:", result)
except Exception as e:
    print("Error:", str(e))
/usr/local/bin/python3 /Users/Lucas/mcgill_scraper/test.py    import traceback
    traceback.print_exc()
