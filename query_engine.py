import sqlite3
import re
import pandas as pd
import os
import shutil
from openai import OpenAI

# Handle Vercel read-only filesystem by copying or seeding database in writeable /tmp
if os.environ.get("VERCEL"):
    DATABASE_PATH = "/tmp/hr_database.db"
    if not os.path.exists(DATABASE_PATH):
        try:
            from db_setup import create_database, seed_database
            create_database(DATABASE_PATH)
            seed_database(DATABASE_PATH)
        except Exception as e:
            pass
else:
    DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hr_database.db")

# Schema description for the database (passed to OpenAI LLM)
DB_SCHEMA_INFO = """
Table: departments
Columns: id (INTEGER PRIMARY KEY), name (TEXT), budget (REAL), manager_id (INTEGER)

Table: employees
Columns: id (INTEGER PRIMARY KEY), first_name (TEXT), last_name (TEXT), email (TEXT), department (TEXT), job_title (TEXT), salary (REAL), hire_date (TEXT), performance_score (INTEGER), manager_id (INTEGER), gender (TEXT), age (INTEGER), state (TEXT), status (TEXT)
Note: department refers to departments.name. status is 'Active' or 'Terminated'. manager_id refers to employees.id.

Table: performance_reviews
Columns: id (INTEGER PRIMARY KEY), employee_id (INTEGER), review_date (TEXT), rating (INTEGER), comments (TEXT)

Table: leave_requests
Columns: id (INTEGER PRIMARY KEY), employee_id (INTEGER), leave_type (TEXT), start_date (TEXT), end_date (TEXT), status (TEXT)
Note: status is 'Approved', 'Pending', 'Rejected'.

Table: users
Columns: username (TEXT PRIMARY KEY), password_hash (TEXT), role (TEXT), created_at (TEXT)
"""

def execute_query(sql_query, db_path=DATABASE_PATH):
    """
    Executes a SQL query on the SQLite database and returns the result as a Pandas DataFrame.
    """
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(sql_query, conn)
        return df, None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()

def generate_sql_local_fallback(prompt):
    """
    Offline semantic/regex fallback matching to allow query parsing without an OpenAI API key.
    Checks for key phrases and generates the corresponding SQL query.
    """
    p = prompt.lower().strip()

    # Headcount queries
    if "headcount" in p or "number of employees" in p or "how many employees" in p:
        if "by department" in p or "department-wise" in p:
            return "SELECT department, COUNT(*) as headcount FROM employees WHERE status = 'Active' GROUP BY department ORDER BY headcount DESC"
        if "by state" in p or "state-wise" in p:
            return "SELECT state, COUNT(*) as headcount FROM employees WHERE status = 'Active' GROUP BY state ORDER BY headcount DESC"
        if "by gender" in p or "gender distribution" in p:
            return "SELECT gender, COUNT(*) as headcount FROM employees WHERE status = 'Active' GROUP BY gender"
        if "by status" in p or "active and terminated" in p:
            return "SELECT status, COUNT(*) as headcount FROM employees GROUP BY status"
        if "terminated" in p or "fired" in p:
            return "SELECT COUNT(*) as terminated_headcount FROM employees WHERE status = 'Terminated'"
        return "SELECT COUNT(*) as total_active_headcount FROM employees WHERE status = 'Active'"

    # Salary queries
    if "salary" in p or "salaries" in p or "earn" in p or "paid" in p:
        if "average" in p or "avg" in p or "mean" in p:
            if "by department" in p or "department-wise" in p:
                return "SELECT department, ROUND(AVG(salary), 2) as avg_salary FROM employees WHERE status = 'Active' GROUP BY department ORDER BY avg_salary DESC"
            if "by job title" in p or "by role" in p:
                return "SELECT job_title, ROUND(AVG(salary), 2) as avg_salary FROM employees WHERE status = 'Active' GROUP BY job_title ORDER BY avg_salary DESC"
            if "by gender" in p:
                return "SELECT gender, ROUND(AVG(salary), 2) as avg_salary FROM employees WHERE status = 'Active' GROUP BY gender"
            return "SELECT ROUND(AVG(salary), 2) as overall_avg_salary FROM employees WHERE status = 'Active'"
            
        if "highest" in p or "top" in p or "max" in p or "most" in p:
            if "engineering" in p:
                return "SELECT first_name, last_name, job_title, salary FROM employees WHERE status = 'Active' AND department = 'Engineering' ORDER BY salary DESC LIMIT 5"
            if "sales" in p:
                return "SELECT first_name, last_name, job_title, salary FROM employees WHERE status = 'Active' AND department = 'Sales' ORDER BY salary DESC LIMIT 5"
            return "SELECT first_name, last_name, department, job_title, salary FROM employees WHERE status = 'Active' ORDER BY salary DESC LIMIT 5"

        if "lowest" in p or "min" in p or "least" in p:
            return "SELECT first_name, last_name, department, job_title, salary FROM employees WHERE status = 'Active' ORDER BY salary ASC LIMIT 5"
            
        if "total" in p or "sum" in p or "budget" in p:
            if "spend" in p or "payroll" in p or "cost" in p:
                return "SELECT SUM(salary) as total_payroll_expense FROM employees WHERE status = 'Active'"

    # Department and budget queries
    if "department" in p or "dept" in p or "budget" in p:
        if "budget" in p:
            return "SELECT name as department, budget, (SELECT first_name || ' ' || last_name FROM employees WHERE id = manager_id) as manager FROM departments ORDER BY budget DESC"
        return "SELECT name as department, (SELECT first_name || ' ' || last_name FROM employees WHERE id = manager_id) as manager FROM departments"

    # Performance reviews
    if "performance" in p or "score" in p or "rating" in p or "review" in p:
        if "average" in p or "avg" in p:
            if "by department" in p:
                return "SELECT department, ROUND(AVG(performance_score), 2) as avg_performance FROM employees WHERE status = 'Active' GROUP BY department ORDER BY avg_performance DESC"
            return "SELECT ROUND(AVG(performance_score), 2) as overall_avg_performance FROM employees WHERE status = 'Active'"
        if "top" in p or "best" in p or "highest" in p or "star" in p:
            return "SELECT first_name, last_name, department, job_title, performance_score FROM employees WHERE status = 'Active' AND performance_score = 5"
        if "worst" in p or "low" in p or "need improvement" in p or "action" in p:
            return "SELECT first_name, last_name, department, job_title, performance_score FROM employees WHERE status = 'Active' AND performance_score <= 2"
        return "SELECT rating, COUNT(*) as count FROM performance_reviews GROUP BY rating ORDER BY rating DESC"

    # Turnover / Attrition queries
    if "turnover" in p or "attrition" in p or "termination" in p or "left the company" in p:
        # Turnover rate = Terminated / Total (both active and terminated) * 100
        return """
        SELECT 
            department, 
            COUNT(CASE WHEN status = 'Terminated' THEN 1 END) as terminated_count,
            COUNT(*) as total_ever_hired,
            ROUND(CAST(COUNT(CASE WHEN status = 'Terminated' THEN 1 END) AS FLOAT) / COUNT(*) * 100, 2) as turnover_rate_percent
        FROM employees 
        GROUP BY department
        ORDER BY turnover_rate_percent DESC
        """

    # Hiring trends queries
    if "hiring" in p or "hire" in p or "trend" in p or "new" in p:
        if "year" in p or "over time" in p or "trend" in p:
            return "SELECT strftime('%Y', hire_date) as hire_year, COUNT(*) as hires_count FROM employees GROUP BY hire_year ORDER BY hire_year ASC"
        if "recent" in p or "latest" in p:
            return "SELECT first_name, last_name, department, job_title, hire_date FROM employees WHERE status = 'Active' ORDER BY hire_date DESC LIMIT 5"

    # Leave requests queries
    if "leave" in p or "vacation" in p or "sick" in p or "absent" in p:
        if "pending" in p:
            return "SELECT e.first_name, e.last_name, e.department, l.leave_type, l.start_date, l.end_date FROM leave_requests l JOIN employees e ON l.employee_id = e.id WHERE l.status = 'Pending' ORDER BY l.start_date"
        if "by type" in p or "distribution" in p:
            return "SELECT leave_type, COUNT(*) as count FROM leave_requests GROUP BY leave_type ORDER BY count DESC"
        return "SELECT e.first_name, e.last_name, e.department, l.leave_type, l.start_date, l.end_date, l.status FROM leave_requests l JOIN employees e ON l.employee_id = e.id ORDER BY l.start_date DESC LIMIT 10"

    # Specific employee queries (e.g. "show details of Matt" or search name)
    # Check if a name is searched
    name_match = re.search(r"who is ([a-zA-Z]+)", p) or re.search(r"find ([a-zA-Z]+)", p) or re.search(r"details of ([a-zA-Z]+)", p)
    if name_match:
        name_query = name_match.group(1).capitalize()
        return f"SELECT first_name, last_name, department, job_title, email, salary, hire_date, performance_score, status FROM employees WHERE first_name = '{name_query}' OR last_name = '{name_query}'"

    # Default fallback: show active employee list preview
    return "SELECT first_name, last_name, department, job_title, salary, hire_date FROM employees WHERE status = 'Active' LIMIT 10"

def generate_sql_with_openai(prompt, api_key):
    """
    Translates a natural-language prompt to an SQLite query using OpenAI's API.
    """
    try:
        client = OpenAI(api_key=api_key)
        
        system_message = (
            "You are an expert SQL translation assistant. Translate the user's natural language question into a single, syntactically correct SQLite query.\n"
            "Return ONLY the raw SQLite query. Do not wrap the output in markdown code blocks (like ```sql ... ```), do not explain the query, and do not include any text other than the SQL query itself.\n\n"
            "Here is the database schema:\n"
            f"{DB_SCHEMA_INFO}\n"
            "Important guidelines:\n"
            "1. By default, query ONLY active employees (employees WHERE status = 'Active') unless the user explicitly asks for terminated employees, all historical employees, or turnover/attrition stats.\n"
            "2. Ensure compatibility with SQLite. (e.g., use strftime('%Y', hire_date) for extracting years; SQLite does not support EXTRACT, CONCAT, or DATE_SUB. For string concatenation, use the || operator).\n"
            "3. Do not modify data (no UPDATE, INSERT, DELETE, or DROP). Only write SELECT queries.\n"
            "4. Return ONLY the raw SQL query. No explanation, no backticks, no code fence blocks."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": f"Question: {prompt}"}
            ],
            temperature=0.0
        )
        
        sql_query = response.choices[0].message.content.strip()
        
        # Clean up any potential markdown fences in case the model ignored the instructions
        sql_query = re.sub(r"```sql\s*", "", sql_query)
        sql_query = re.sub(r"```\s*", "", sql_query)
        sql_query = sql_query.strip(";")
        
        return sql_query, None
    except Exception as e:
        return None, f"OpenAI Error: {str(e)}"

def translate_and_execute(prompt, api_key=None, db_path=DATABASE_PATH):
    """
    Full pipeline: translates prompt to SQL, executes it, and returns SQL, Dataframe, and any errors/warnings.
    """
    # Initialize variables
    sql_query = None
    engine_used = "Offline Fallback"
    error = None
    
    # Attempt OpenAI generation if key is provided
    if api_key and api_key.strip():
        sql_query, error = generate_sql_with_openai(prompt, api_key)
        engine_used = "OpenAI GPT-4o-mini"
        
        # If OpenAI generation fails, fall back to local regex matching
        if error:
            warning = f"OpenAI API failed, falling back to local engine. Details: {error}"
            sql_query = generate_sql_local_fallback(prompt)
            engine_used = "Offline Fallback (API Error)"
        else:
            warning = None
    else:
        # Use local fallback directly
        sql_query = generate_sql_local_fallback(prompt)
        warning = "No OpenAI API key provided. Using offline rule-based semantic parser."
        
    if not sql_query:
        return None, None, "Could not generate SQL for the prompt.", engine_used, warning

    # Execute SQL
    df, exec_error = execute_query(sql_query, db_path)
    
    if exec_error:
        # If OpenAI generated a broken query, try running the local fallback query as a rescue
        if engine_used.startswith("OpenAI"):
            rescue_query = generate_sql_local_fallback(prompt)
            df, rescue_error = execute_query(rescue_query, db_path)
            if not rescue_error:
                return rescue_query, df, None, "Offline Fallback (OpenAI query error rescue)", f"OpenAI generated query caused an execution error: {exec_error}. Rescued with fallback query."
        return sql_query, None, f"SQL Execution Error: {exec_error}", engine_used, warning

    return sql_query, df, None, engine_used, warning

if __name__ == "__main__":
    # Quick test of the fallback engine
    test_prompts = [
        "What is the average salary by department?",
        "Show me headcount by state",
        "who is James",
        "Show latest hiring trends"
    ]
    print("Testing local query generator fallback:")
    for tp in test_prompts:
        sql = generate_sql_local_fallback(tp)
        print(f"Prompt: '{tp}'\nSQL: {sql}\n")
