# GenAI Workforce Analytics Assistant

A premium, responsive workforce analytics web application built with **Python**, **Plotly Dash**, **SQLite**, and **OpenAI APIs**. The application translates natural-language queries into SQL commands, executes them against a local database, and visualizes the results dynamically.

## 🚀 Features

- **Interactive Login & Auth System**: Multi-user session authentication backed by a hashed SQLite credentials table.
- **AI-Powered Query Assistant**: Converts natural language prompts (e.g. *"What is the average salary by department?"*) into SQLite queries using OpenAI's `gpt-4o-mini` model.
- **Local Fallback Engine**: If no OpenAI API Key is provided, the assistant uses a local regex-based semantic parser mapping common workforce questions so that the app works fully offline out-of-the-box.
- **Auto-Chart Generation**: Inspects query results dataframes and plots appropriate visual charts (Pie, Bar, Line, or Scatter plots) dynamically.
- **Interactive Schema Explorer**: Lists metadata tables and column descriptions to guide user prompting.
- **HR Dashboard tab**: Renders preset KPI cards (Headcount, Average Salary, Turnover Rate) and workforce distribution graphs.

---

## 🛠️ Tech Stack

- **Core**: Python, sqlite3, Pandas
- **UI Framework**: Plotly Dash, Dash Bootstrap Components
- **Styling**: Custom CSS (Glassmorphism theme)
- **AI Integration**: OpenAI Client Library

---

## 📦 Installation & Setup

1. **Clone the Repository**
   ```bash
   git clone <your-repository-url>
   cd hr_analytics_assistant
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize the Database**
   Runs schema creations and seeds the database with coherent, randomized employee, review, and leave request tables.
   ```bash
   python db_setup.py
   ```

4. **Run the Application**
   ```bash
   python app.py
   ```
   Open your browser and navigate to **http://127.0.0.1:8050**.

---

## 🔐 Login Credentials

Use the default seeded admin account for initial testing:
- **Username**: `admin`
- **Password**: `admin123`

*(Note: You can also use the registration form on the login screen to create a new user profile)*
