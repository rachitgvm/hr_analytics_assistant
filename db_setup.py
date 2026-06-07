import sqlite3
import hashlib
import random
import os
from datetime import datetime, timedelta

def hash_password(password, salt="hr_salt_2026"):
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

def create_database(db_path="hr_database.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Drop tables if they exist to start fresh
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute("DROP TABLE IF EXISTS leave_requests")
    cursor.execute("DROP TABLE IF EXISTS performance_reviews")
    cursor.execute("DROP TABLE IF EXISTS employees")
    cursor.execute("DROP TABLE IF EXISTS departments")

    # Create users table
    cursor.execute("""
    CREATE TABLE users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # Create departments table
    cursor.execute("""
    CREATE TABLE departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        budget REAL NOT NULL,
        manager_id INTEGER
    )
    """)

    # Create employees table
    cursor.execute("""
    CREATE TABLE employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        department TEXT NOT NULL,
        job_title TEXT NOT NULL,
        salary REAL NOT NULL,
        hire_date TEXT NOT NULL,
        performance_score INTEGER NOT NULL, -- 1 to 5 scale
        manager_id INTEGER,
        gender TEXT NOT NULL,
        age INTEGER NOT NULL,
        state TEXT NOT NULL,
        status TEXT NOT NULL, -- 'Active', 'Terminated'
        FOREIGN KEY (department) REFERENCES departments(name),
        FOREIGN KEY (manager_id) REFERENCES employees(id)
    )
    """)

    # Create performance_reviews table
    cursor.execute("""
    CREATE TABLE performance_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        review_date TEXT NOT NULL,
        rating INTEGER NOT NULL,
        comments TEXT,
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    )
    """)

    # Create leave_requests table
    cursor.execute("""
    CREATE TABLE leave_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        leave_type TEXT NOT NULL, -- 'Vacation', 'Sick', 'Maternity', 'Personal'
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        status TEXT NOT NULL, -- 'Approved', 'Pending', 'Rejected'
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    )
    """)

    conn.commit()
    conn.close()
    print("Database tables created successfully.")

def seed_database(db_path="hr_database.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Seed Admin User
    admin_pass = hash_password("admin123")
    user_pass = hash_password("user123")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?)", ("admin", admin_pass, "Admin", now_str))
    cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?)", ("user", user_pass, "User", now_str))

    # Seed Departments
    depts = [
        ("Engineering", 1200000.0, None),
        ("Sales", 850000.0, None),
        ("Marketing", 450000.0, None),
        ("Human Resources", 350000.0, None),
        ("Finance", 600000.0, None)
    ]
    cursor.executemany("INSERT INTO departments (name, budget, manager_id) VALUES (?, ?, ?)", depts)
    conn.commit()

    # Get department IDs
    cursor.execute("SELECT id, name FROM departments")
    dept_map = {name: id for id, name in cursor.fetchall()}

    # Data lists for generating realistic employees
    first_names_m = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles", "Daniel", "Matthew", "Anthony", "Mark", "Donald", "Steven", "Paul", "Andrew"]
    first_names_f = ["Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen", "Lisa", "Nancy", "Betty", "Sandra", "Margaret", "Ashley", "Kimberly", "Emily"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White"]

    states = ["CA", "NY", "TX", "WA", "IL", "MA", "FL", "GA", "CO", "NC"]
    genders = ["Male", "Female", "Non-binary"]

    # Define roles and salaries within departments
    dept_roles = {
        "Engineering": [
            {"title": "Software Engineer I", "salary_range": (75000, 90000)},
            {"title": "Software Engineer II", "salary_range": (95000, 115000)},
            {"title": "Senior Software Engineer", "salary_range": (125000, 150000)},
            {"title": "QA Engineer", "salary_range": (70000, 90000)},
            {"title": "DevOps Engineer", "salary_range": (100000, 130000)},
            {"title": "Engineering Manager", "salary_range": (160000, 185000)}
        ],
        "Sales": [
            {"title": "Account Executive", "salary_range": (65000, 85000)},
            {"title": "Sales Development Rep", "salary_range": (45000, 55000)},
            {"title": "Sales Manager", "salary_range": (110000, 140000)},
            {"title": "Director of Sales", "salary_range": (150000, 180000)}
        ],
        "Marketing": [
            {"title": "Marketing Coordinator", "salary_range": (50000, 65000)},
            {"title": "Content Specialist", "salary_range": (55000, 70000)},
            {"title": "SEO Specialist", "salary_range": (60000, 80000)},
            {"title": "Marketing Manager", "salary_range": (95000, 120000)}
        ],
        "Human Resources": [
            {"title": "HR Coordinator", "salary_range": (50000, 65000)},
            {"title": "Recruiter", "salary_range": (60000, 80000)},
            {"title": "HR Manager", "salary_range": (90000, 115000)}
        ],
        "Finance": [
            {"title": "Financial Analyst", "salary_range": (65000, 85000)},
            {"title": "Senior Accountant", "salary_range": (85000, 110000)},
            {"title": "Finance Manager", "salary_range": (115000, 140000)}
        ]
    }

    # First, let's create Department Managers to be used as managers for others
    managers = []
    emp_id_counter = 1
    generated_emails = set()

    random.seed(42) # Seed random for reproducibility

    for dept_name in dept_roles.keys():
        gender = random.choice(genders)
        if gender == "Male":
            first_name = random.choice(first_names_m)
        elif gender == "Female":
            first_name = random.choice(first_names_f)
        else:
            first_name = random.choice(first_names_m + first_names_f)
        
        last_name = random.choice(last_names)
        email = f"{first_name.lower()}.{last_name.lower()}@company.com"
        counter = 1
        while email in generated_emails:
            email = f"{first_name.lower()}.{last_name.lower()}{counter}@company.com"
            counter += 1
        generated_emails.add(email)
        
        # Managers have the Manager role
        manager_role_info = [r for r in dept_roles[dept_name] if "Manager" in r["title"] or "Director" in r["title"]][0]
        salary = float(random.randint(*manager_role_info["salary_range"]))
        
        # Hiring details
        years_ago = random.randint(3, 7)
        days_ago = random.randint(0, 365)
        hire_date = (datetime.now() - timedelta(days=(years_ago*365 + days_ago))).strftime("%Y-%m-%d")
        
        performance_score = random.choice([3, 4, 5])
        age = random.randint(35, 55)
        state = random.choice(states)
        status = "Active"

        cursor.execute("""
            INSERT INTO employees (first_name, last_name, email, department, job_title, salary, hire_date, performance_score, manager_id, gender, age, state, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (first_name, last_name, email, dept_name, manager_role_info["title"], salary, hire_date, performance_score, None, gender, age, state, status))
        
        managers.append({
            "id": emp_id_counter,
            "department": dept_name,
            "name": f"{first_name} {last_name}"
        })
        
        # Update department manager_id in departments table
        cursor.execute("UPDATE departments SET manager_id = ? WHERE name = ?", (emp_id_counter, dept_name))
        emp_id_counter += 1

    conn.commit()

    # Seed Regular Employees
    total_employees = 120
    active_employees = []
    
    # We will generate employees who report to their department manager
    for _ in range(total_employees - len(managers)):
        dept_name = random.choice(list(dept_roles.keys()))
        dept_mgr = [m for m in managers if m["department"] == dept_name][0]
        
        gender = random.choice(genders)
        if gender == "Male":
            first_name = random.choice(first_names_m)
        elif gender == "Female":
            first_name = random.choice(first_names_f)
        else:
            first_name = random.choice(first_names_m + first_names_f)
            
        last_name = random.choice(last_names)
        email = f"{first_name.lower()}.{last_name.lower()}@company.com"
        counter = 1
        while email in generated_emails:
            email = f"{first_name.lower()}.{last_name.lower()}{counter}@company.com"
            counter += 1
        generated_emails.add(email)
        
        # Pick a regular role (not the manager/director roles already chosen for the department heads)
        regular_roles = [r for r in dept_roles[dept_name] if "Manager" not in r["title"] and "Director" not in r["title"]]
        role_info = random.choice(regular_roles)
        salary = float(random.randint(*role_info["salary_range"]))
        
        # Hiring details
        years_ago = random.randint(0, 4)
        days_ago = random.randint(0, 365)
        hire_date = (datetime.now() - timedelta(days=(years_ago*365 + days_ago))).strftime("%Y-%m-%d")
        
        performance_score = random.choices([1, 2, 3, 4, 5], weights=[0.05, 0.10, 0.55, 0.20, 0.10])[0]
        age = random.randint(22, 50)
        state = random.choice(states)
        
        # 8% of employees hired more than a year ago might be terminated
        status = "Active"
        if years_ago >= 1 and random.random() < 0.08:
            status = "Terminated"

        cursor.execute("""
            INSERT INTO employees (first_name, last_name, email, department, job_title, salary, hire_date, performance_score, manager_id, gender, age, state, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (first_name, last_name, email, dept_name, role_info["title"], salary, hire_date, performance_score, dept_mgr["id"], gender, age, state, status))
        
        if status == "Active":
            active_employees.append(emp_id_counter)
        emp_id_counter += 1

    conn.commit()

    # Seed Performance Reviews for active employees
    cursor.execute("SELECT id, hire_date, performance_score FROM employees WHERE status = 'Active'")
    employee_reviews = cursor.fetchall()
    
    review_comments = {
        1: ["Performance is significantly below standard. Demands immediate action plan.", "Fails to meet core job objectives. Requires substantial supervision."],
        2: ["Needs improvement in meeting deadlines and quality output.", "Inconsistent performance metrics. Shows potential but needs focus."],
        3: ["Meets all expectations. Reliable team member.", "Solid performance. Completes tasks efficiently and cooperates well with the team.", "Competent execution of tasks. Consistently achieves targets."],
        4: ["Exceeds expectations. Highly proactive and takes on additional responsibilities.", "Very strong performance. Frequently provides creative solutions to technical challenges."],
        5: ["Outstanding performer. Shows exemplary leadership capability and technical expertise.", "Exceptional performance, exceeded all quarterly and annual targets by substantial margins."]
    }

    for emp_id, hire_date_str, score in employee_reviews:
        hire_date = datetime.strptime(hire_date_str, "%Y-%m-%d")
        years_since_hire = (datetime.now() - hire_date).days // 365
        
        # Generate reviews based on hire length
        for yr in range(1, years_since_hire + 1):
            review_date = (hire_date + timedelta(days=yr*365 + random.randint(-15, 15))).strftime("%Y-%m-%d")
            # rating can vary slightly from the current score
            rating = max(1, min(5, score + random.choice([-1, 0, 1])))
            comment = random.choice(review_comments[rating])
            cursor.execute("""
                INSERT INTO performance_reviews (employee_id, review_date, rating, comments)
                VALUES (?, ?, ?, ?)
            """, (emp_id, review_date, rating, comment))
            
    conn.commit()

    # Seed Leave Requests for active employees
    leave_types = ["Vacation", "Sick", "Personal", "Maternity/Paternity"]
    statuses = ["Approved", "Pending", "Rejected"]
    
    for emp_id in active_employees:
        # Generate 1 to 4 leave requests per employee
        num_requests = random.randint(1, 4)
        for _ in range(num_requests):
            leave_type = random.choice(leave_types)
            # Make sure it's historically sensible or future pending
            days_ago = random.randint(-180, 60)
            start_date_dt = datetime.now() - timedelta(days=days_ago)
            duration = random.randint(1, 10)
            if leave_type == "Maternity/Paternity":
                duration = random.randint(30, 90)
            end_date_dt = start_date_dt + timedelta(days=duration)
            
            start_date = start_date_dt.strftime("%Y-%m-%d")
            end_date = end_date_dt.strftime("%Y-%m-%d")
            
            # Future requests can be pending or approved. Past requests are approved or rejected.
            if days_ago < 0:
                status = random.choices(["Approved", "Rejected"], weights=[0.9, 0.1])[0]
            else:
                status = random.choices(["Pending", "Approved"], weights=[0.7, 0.3])[0]
                
            cursor.execute("""
                INSERT INTO leave_requests (employee_id, leave_type, start_date, end_date, status)
                VALUES (?, ?, ?, ?, ?)
            """, (emp_id, leave_type, start_date, end_date, status))

    conn.commit()
    conn.close()
    print("Database seeded with realistic HR metrics and user authorization records.")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_file = os.path.join(base_dir, "hr_database.db")
    create_database(db_file)
    seed_database(db_file)
