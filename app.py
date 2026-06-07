import dash
from dash import dcc, html, dash_table, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import hashlib
from datetime import datetime
import os
from dotenv import load_dotenv

# Import helper functions
from db_setup import hash_password
from query_engine import translate_and_execute, execute_query, DB_SCHEMA_INFO, DATABASE_PATH

# Load env variables (if any)
load_dotenv()

# Initialize Dash application with Cyborg theme as background base for bootstrap
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    suppress_callback_exceptions=True,
    title="GenAI HR Analytics Assistant"
)

# App server for production deployment (if needed)
server = app.server
application = server

# Custom styling configurations for plotly figures to match dark dashboard aesthetic
PLOTLY_TEMPLATE = "plotly_dark"
THEME_COLORS = {
    'bg_card': '#111827',
    'accent': '#6366f1',
    'accent_hover': '#4f46e5',
    'success': '#10b981',
    'warning': '#f59e0b',
    'danger': '#f43f5e',
    'grid_color': 'rgba(255, 255, 255, 0.08)',
    'text': '#f3f4f6',
    'text_muted': '#9ca3af'
}

# --- Shared UI Layout Elements ---

def make_header(username):
    return dbc.Row([
        dbc.Col([
            html.H2([
                html.Span("GenAI ", style={"color": THEME_COLORS['accent'], "fontWeight": "bold"}),
                "Workforce Analytics Assistant"
            ], className="m-0", style={"fontFamily": "Outfit"})
        ], xs=12, md=8, className="d-flex align-items-center justify-content-center justify-content-md-start mb-3 mb-md-0"),
        dbc.Col([
            html.Div([
                html.Span(f"Welcome, ", style={"color": THEME_COLORS['text_muted']}),
                html.Span(username, style={"color": THEME_COLORS['text'], "fontWeight": "bold", "marginRight": "15px"}),
                dbc.Button("Logout", id="logout-btn", color="danger", size="sm", className="custom-btn-secondary px-3 py-1", style={"borderRadius": "6px"})
            ], className="d-flex align-items-center justify-content-center justify-content-md-end")
        ], xs=12, md=4)
    ], className="mb-4 pb-3 border-bottom", style={"borderColor": "rgba(255,255,255,0.06)"})

# --- Tab Layout Generative Functions ---

def layout_chat_assistant():
    sample_queries = [
        "What is the average salary by department?",
        "Show me headcount by state",
        "Who is James?",
        "Show the highest paid employees in Engineering",
        "What is the turnover rate by department?",
        "Show the hiring trend by year",
        "Show all pending leave requests"
    ]
    
    return html.Div([
        dbc.Row([
            # Sidebar suggestion box
            dbc.Col([
                html.Div([
                    html.H5("Sample Prompts", className="mb-3", style={"fontWeight": "600"}),
                    html.P("Click on a prompt below to run it immediately:", style={"fontSize": "14px", "color": THEME_COLORS['text_muted']}),
                    html.Div([
                        dbc.Button(q, id={"type": "sample-query-btn", "index": i}, color="link", 
                                   className="text-start p-0 mb-3 w-100 text-decoration-none", 
                                   style={"color": THEME_COLORS['text'], "fontSize": "13.5px", "transition": "color 0.2s"})
                        for i, q in enumerate(sample_queries)
                    ], className="d-flex flex-column align-items-start")
                ], className="glass-panel h-100")
            ], xs=12, md=4, className="mb-4 mb-md-0"),
            
            # Chat Interface
            dbc.Col([
                html.Div([
                    html.H5("Ask HR Assistant", className="mb-3", style={"fontWeight": "600"}),
                    dbc.InputGroup([
                        dbc.Input(id="chat-input", placeholder="e.g. What is the average salary of active employees by department?", type="text", className="custom-input"),
                        dbc.Button("Ask", id="ask-btn", className="custom-btn-primary px-4")
                    ], className="mb-3"),
                    
                    # Status Indicator
                    html.Div(id="assistant-status", className="mb-3 small", style={"color": THEME_COLORS['text_muted']}),
                    
                    # Output details
                    dcc.Loading(
                        id="loading-assistant",
                        type="default",
                        color=THEME_COLORS['accent'],
                        children=[
                            html.Div(id="assistant-output-container", style={"display": "none"}, children=[
                                # Generated SQL
                                html.Div([
                                    html.Label("Generated SQL Query", className="small text-muted mb-1"),
                                    html.Pre(id="generated-sql-display", className="sql-panel")
                                ], className="mb-3"),
                                
                                # Visualization (chart)
                                html.Div([
                                    html.Label("Visualization", className="small text-muted mb-1"),
                                    dcc.Graph(id="assistant-chart", config={"displayModeBar": False})
                                ], className="mb-4", id="assistant-chart-container"),
                                
                                # Results Table
                                html.Div([
                                    html.Label("Query Results", className="small text-muted mb-1"),
                                    html.Div(id="assistant-table-container")
                                ])
                            ])
                        ]
                    )
                ], className="glass-panel h-100")
            ], xs=12, md=8)
        ])
    ])

def layout_dashboard():
    return html.Div([
        # KPI Row
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H6("Total Active Employees", className="text-uppercase small text-muted mb-0"),
                    html.Div(id="kpi-headcount", className="kpi-val")
                ], className="glass-panel kpi-card")
            ], xs=12, sm=6, md=3, className="mb-3 mb-md-0"),
            
            dbc.Col([
                html.Div([
                    html.H6("Average Annual Salary", className="text-uppercase small text-muted mb-0"),
                    html.Div(id="kpi-salary", className="kpi-val success")
                ], className="glass-panel kpi-card success")
            ], xs=12, sm=6, md=3, className="mb-3 mb-md-0"),
            
            dbc.Col([
                html.Div([
                    html.H6("Average Performance Score", className="text-uppercase small text-muted mb-0"),
                    html.Div(id="kpi-performance", className="kpi-val")
                ], className="glass-panel kpi-card")
            ], xs=12, sm=6, md=3, className="mb-3 mb-md-0"),
            
            dbc.Col([
                html.Div([
                    html.H6("Company Turnover Rate", className="text-uppercase small text-muted mb-0"),
                    html.Div(id="kpi-turnover", className="kpi-val")
                ], className="glass-panel kpi-card")
            ], xs=12, sm=6, md=3, className="mb-3 mb-md-0")
        ], className="mb-4"),
        
        # Dashboard Analytics Charts
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H6("Headcount by Department", className="mb-3"),
                    dcc.Graph(id="chart-dept-headcount", config={"displayModeBar": False})
                ], className="glass-panel")
            ], xs=12, md=6, className="mb-4"),
            
            dbc.Col([
                html.Div([
                    html.H6("Average Salary & Budget comparison", className="mb-3"),
                    dcc.Graph(id="chart-dept-salaries", config={"displayModeBar": False})
                ], className="glass-panel")
            ], xs=12, md=6, className="mb-4")
        ]),
        
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H6("Hiring Trend Over Time", className="mb-3"),
                    dcc.Graph(id="chart-hiring-trend", config={"displayModeBar": False})
                ], className="glass-panel")
            ], xs=12, md=8, className="mb-4 mb-md-0"),
            
            dbc.Col([
                html.Div([
                    html.H6("Performance Distribution", className="mb-3"),
                    dcc.Graph(id="chart-perf-dist", config={"displayModeBar": False})
                ], className="glass-panel")
            ], xs=12, md=4)
        ])
    ])

def layout_schema_explorer():
    # Schema metadata presentation helper
    schema_details = {
        "departments": [
            {"Column": "id", "Type": "INTEGER", "Constraint": "PRIMARY KEY", "Description": "Unique department identifier"},
            {"Column": "name", "Type": "TEXT", "Constraint": "UNIQUE NOT NULL", "Description": "Department name"},
            {"Column": "budget", "Type": "REAL", "Constraint": "NOT NULL", "Description": "Annual department budget ($)"},
            {"Column": "manager_id", "Type": "INTEGER", "Constraint": "FOREIGN KEY (employees.id)", "Description": "Reference to department head"}
        ],
        "employees": [
            {"Column": "id", "Type": "INTEGER", "Constraint": "PRIMARY KEY", "Description": "Unique employee identifier"},
            {"Column": "first_name", "Type": "TEXT", "Constraint": "NOT NULL", "Description": "Employee's first name"},
            {"Column": "last_name", "Type": "TEXT", "Constraint": "NOT NULL", "Description": "Employee's last name"},
            {"Column": "email", "Type": "TEXT", "Constraint": "UNIQUE NOT NULL", "Description": "Official email address"},
            {"Column": "department", "Type": "TEXT", "Constraint": "FOREIGN KEY (departments.name)", "Description": "Assigned department"},
            {"Column": "job_title", "Type": "TEXT", "Constraint": "NOT NULL", "Description": "Official job title / designation"},
            {"Column": "salary", "Type": "REAL", "Constraint": "NOT NULL", "Description": "Annual base salary ($)"},
            {"Column": "hire_date", "Type": "TEXT", "Constraint": "NOT NULL", "Description": "Hiring date (YYYY-MM-DD)"},
            {"Column": "performance_score", "Type": "INTEGER", "Constraint": "NOT NULL", "Description": "Performance score scale (1 to 5)"},
            {"Column": "manager_id", "Type": "INTEGER", "Constraint": "FOREIGN KEY (employees.id)", "Description": "Direct reporting manager ID"},
            {"Column": "gender", "Type": "TEXT", "Constraint": "NOT NULL", "Description": "Employee's gender identity"},
            {"Column": "age", "Type": "INTEGER", "Constraint": "NOT NULL", "Description": "Current age"},
            {"Column": "state", "Type": "TEXT", "Constraint": "NOT NULL", "Description": "State of residence (2-letter code)"},
            {"Column": "status", "Type": "TEXT", "Constraint": "NOT NULL", "Description": "'Active' or 'Terminated' employment status"}
        ],
        "performance_reviews": [
            {"Column": "id", "Type": "INTEGER", "Constraint": "PRIMARY KEY", "Description": "Unique review record ID"},
            {"Column": "employee_id", "Type": "INTEGER", "Constraint": "FOREIGN KEY (employees.id)", "Description": "Reference to employee reviewed"},
            {"Column": "review_date", "Type": "TEXT", "Constraint": "NOT NULL", "Description": "Review completion date"},
            {"Column": "rating", "Type": "INTEGER", "Constraint": "NOT NULL", "Description": "Review rating score (1 to 5)"},
            {"Column": "comments", "Type": "TEXT", "Constraint": "-", "Description": "Manager's written feedback comments"}
        ],
        "leave_requests": [
            {"Column": "id", "Type": "INTEGER", "Constraint": "PRIMARY KEY", "Description": "Unique leave request ID"},
            {"Column": "employee_id", "Type": "INTEGER", "Constraint": "FOREIGN KEY (employees.id)", "Description": "Reference to applicant"},
            {"Column": "leave_type", "Type": "TEXT", "Constraint": "NOT NULL", "Description": "Leave type: Vacation, Sick, Personal, Maternity..."},
            {"Column": "start_date", "Type": "TEXT", "Constraint": "NOT NULL", "Description": "Start date of absence"},
            {"Column": "end_date", "Type": "TEXT", "Constraint": "NOT NULL", "Description": "End date of absence"},
            {"Column": "status", "Type": "TEXT", "Constraint": "NOT NULL", "Description": "'Approved', 'Pending', or 'Rejected'"}
        ]
    }

    tables_cards = []
    for table_name, columns in schema_details.items():
        df_cols = pd.DataFrame(columns)
        table_el = dash_table.DataTable(
            columns=[{"name": i, "id": i} for i in df_cols.columns],
            data=df_cols.to_dict('records'),
            style_header={
                'backgroundColor': 'rgba(17, 24, 39, 0.95)',
                'color': THEME_COLORS['text'],
                'fontWeight': 'bold',
                'border': '1px solid rgba(255,255,255,0.06)'
            },
            style_cell={
                'backgroundColor': 'rgba(31, 41, 55, 0.2)',
                'color': THEME_COLORS['text_muted'],
                'textAlign': 'left',
                'padding': '10px',
                'border': '1px solid rgba(255,255,255,0.04)',
                'fontFamily': 'Outfit',
                'fontSize': '13.5px'
            },
            style_data_conditional=[
                {
                    'if': {'column_id': 'Column'},
                    'color': THEME_COLORS['accent'],
                    'fontWeight': 'bold',
                    'fontFamily': 'Space Grotesk'
                }
            ],
            style_as_list_view=True
        )
        
        tables_cards.append(
            dbc.Card([
                dbc.CardHeader(html.H5(table_name, className="m-0 font-monospace text-info", style={"fontWeight": "bold"})),
                dbc.CardBody(table_el, className="p-0")
            ], className="glass-panel border-0 mb-4", style={"overflow": "hidden"})
        )

    return html.Div(tables_cards)

def layout_settings():
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H5("Configuration Settings", className="mb-3", style={"fontWeight": "600"}),
                    
                    # OpenAI API Key Input
                    html.Div([
                        html.Label("OpenAI API Key", className="form-label", style={"color": THEME_COLORS['text']}),
                        dbc.Input(id="settings-api-key", placeholder="sk-proj-...", type="password", className="custom-input mb-2"),
                        html.Div("If provided, natural language questions will be converted using OpenAI's model. Otherwise, the app falls back to local semantic mapping.", className="form-text small", style={"color": THEME_COLORS['text_muted']})
                    ], className="mb-4"),
                    
                    # DB Operations
                    html.Div([
                        html.Label("Database Status", className="form-label", style={"color": THEME_COLORS['text']}),
                        html.Div([
                            dbc.Button("Re-seed Database", id="reseed-btn", color="warning", className="custom-btn-secondary me-2"),
                            html.Span(id="reseed-status", className="small ms-2", style={"color": THEME_COLORS['text_muted']})
                        ], className="d-flex align-items-center mt-2")
                    ], className="mb-4"),
                    
                    # User feedback config
                    dbc.Button("Save Settings", id="save-settings-btn", className="custom-btn-primary px-4"),
                    html.Div(id="settings-save-alert", className="mt-3")
                ], className="glass-panel")
            ], xs=12, md=6)
        ])
    ])

def layout_data_entry():
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H5("Add New Employee Record", className="mb-4", style={"fontWeight": "600"}),
                    
                    dbc.Form([
                        dbc.Row([
                            dbc.Col([
                                html.Label("First Name", className="small text-muted mb-1"),
                                dbc.Input(id="entry-first-name", placeholder="John", type="text", className="custom-input mb-3")
                            ], width=6),
                            dbc.Col([
                                html.Label("Last Name", className="small text-muted mb-1"),
                                dbc.Input(id="entry-last-name", placeholder="Doe", type="text", className="custom-input mb-3")
                            ], width=6),
                        ]),
                        
                        dbc.Row([
                            dbc.Col([
                                html.Label("Email (Optional)", className="small text-muted mb-1"),
                                dbc.Input(id="entry-email", placeholder="john.doe@company.com", type="email", className="custom-input mb-3")
                            ], width=6),
                            dbc.Col([
                                html.Label("Age", className="small text-muted mb-1"),
                                dbc.Input(id="entry-age", placeholder="30", type="number", min=18, max=70, className="custom-input mb-3")
                            ], width=6),
                        ]),
                        
                        dbc.Row([
                            dbc.Col([
                                html.Label("Department", className="small text-muted mb-1"),
                                dcc.Dropdown(
                                    id="entry-department",
                                    options=[{"label": d, "value": d} for d in ["Engineering", "Sales", "Marketing", "Human Resources", "Finance"]],
                                    value="Engineering",
                                    clearable=False,
                                    style={"backgroundColor": "#1f2937", "color": "#000", "borderRadius": "8px", "marginBottom": "15px"}
                                )
                            ], width=6),
                            dbc.Col([
                                html.Label("Job Title", className="small text-muted mb-1"),
                                dbc.Input(id="entry-job-title", placeholder="Software Engineer II", type="text", className="custom-input mb-3")
                            ], width=6),
                        ]),
                        
                        dbc.Row([
                            dbc.Col([
                                html.Label("Salary ($/yr)", className="small text-muted mb-1"),
                                dbc.Input(id="entry-salary", placeholder="85000", type="number", min=0, className="custom-input mb-3")
                            ], width=6),
                            dbc.Col([
                                html.Label("Hire Date", className="small text-muted mb-1"),
                                dbc.Input(id="entry-hire-date", placeholder="YYYY-MM-DD", value=datetime.now().strftime("%Y-%m-%d"), type="text", className="custom-input mb-3")
                            ], width=6),
                        ]),
                        
                        dbc.Row([
                            dbc.Col([
                                html.Label("Gender", className="small text-muted mb-1"),
                                dcc.Dropdown(
                                    id="entry-gender",
                                    options=[{"label": g, "value": g} for g in ["Male", "Female", "Non-binary"]],
                                    value="Male",
                                    clearable=False,
                                    style={"backgroundColor": "#1f2937", "color": "#000", "borderRadius": "8px", "marginBottom": "15px"}
                                )
                            ], width=4),
                            dbc.Col([
                                html.Label("State", className="small text-muted mb-1"),
                                dbc.Input(id="entry-state", placeholder="CA", maxLength=2, type="text", className="custom-input mb-3")
                            ], width=4),
                            dbc.Col([
                                html.Label("Performance Score", className="small text-muted mb-1"),
                                dcc.Dropdown(
                                    id="entry-perf",
                                    options=[{"label": str(i), "value": i} for i in range(1, 6)],
                                    value=3,
                                    clearable=False,
                                    style={"backgroundColor": "#1f2937", "color": "#000", "borderRadius": "8px", "marginBottom": "15px"}
                                )
                            ], width=4),
                        ]),
                        
                        dbc.Row([
                            dbc.Col([
                                html.Label("Reporting Manager", className="small text-muted mb-1"),
                                dcc.Dropdown(
                                    id="entry-manager",
                                    placeholder="Select reporting manager",
                                    clearable=True,
                                    style={"backgroundColor": "#1f2937", "color": "#000", "borderRadius": "8px", "marginBottom": "15px"}
                                )
                            ], width=8),
                            dbc.Col([
                                html.Label("Status", className="small text-muted mb-1"),
                                dcc.Dropdown(
                                    id="entry-status",
                                    options=[{"label": s, "value": s} for s in ["Active", "Terminated"]],
                                    value="Active",
                                    clearable=False,
                                    style={"backgroundColor": "#1f2937", "color": "#000", "borderRadius": "8px", "marginBottom": "15px"}
                                )
                            ], width=4),
                        ]),
                        
                        html.Div(id="entry-submit-output", className="mb-3"),
                        
                        dbc.Button("Add Employee", id="entry-submit-btn", className="custom-btn-primary px-4")
                    ])
                ], className="glass-panel")
            ], xs=12, md=8, className="mx-auto")
        ])
    ])

# --- Login & Registration Layout ---

def layout_login_page(register_mode=False):
    card_title = "Create New Account" if register_mode else "HR Assistant Login"
    submit_btn_text = "Register" if register_mode else "Sign In"
    switch_prompt = "Already have an account? Sign in" if register_mode else "Need an account? Register"
    
    return html.Div([
        html.Div([
            html.Div([
                # Logo icon / Title
                html.Div([
                    html.Div("AI", className="d-inline-flex justify-content-center align-items-center mb-3", style={
                        "backgroundColor": THEME_COLORS['accent'],
                        "color": "white",
                        "width": "50px",
                        "height": "50px",
                        "borderRadius": "12px",
                        "fontWeight": "bold",
                        "fontSize": "22px",
                        "boxShadow": f"0 4px 15px {THEME_COLORS['accent']}"
                    }),
                    html.H3("Workforce Analytics", className="mb-1", style={"fontFamily": "Outfit", "fontWeight": "bold"}),
                    html.P("Empowered by Generative AI", className="small text-muted mb-4")
                ], className="text-center"),
                
                html.H5(card_title, className="mb-3 text-center", style={"fontWeight": "600"}),
                
                # Fields
                html.Div([
                    html.Label("Username", className="small text-muted mb-1"),
                    dbc.Input(id="auth-username", placeholder="Enter username", type="text", className="custom-input mb-3")
                ]),
                html.Div([
                    html.Label("Password", className="small text-muted mb-1"),
                    dbc.Input(id="auth-password", placeholder="Enter password", type="password", className="custom-input mb-4")
                ]),
                
                # Register Mode Role Select
                html.Div([
                    html.Label("Role", className="small text-muted mb-1"),
                    dcc.Dropdown(
                        id="auth-role",
                        options=[{"label": "User", "value": "User"}, {"label": "Admin", "value": "Admin"}],
                        value="User",
                        clearable=False,
                        style={"backgroundColor": "#1f2937", "color": "#000", "borderRadius": "8px", "marginBottom": "20px"}
                    )
                ], style={"display": "block" if register_mode else "none"}),
                
                # Error alert space
                html.Div(id="auth-error-output", className="mb-3"),
                
                # Actions
                dbc.Button(submit_btn_text, id="auth-submit-btn", className="custom-btn-primary w-100 mb-3"),
                
                # Switch link
                html.Div([
                    dbc.Button(switch_prompt, id="auth-switch-mode-btn", color="link", className="p-0 text-decoration-none small", style={"color": THEME_COLORS['text_muted']})
                ], className="text-center")
            ], className="login-card")
        ], className="login-container")
    ], id="auth-page-root")


# --- Main App Template (Dashboard Shell) ---

def layout_dashboard_shell(username):
    return html.Div([
        dbc.Container([
            make_header(username),
            
            # Tab layout
            dcc.Tabs(id="app-tabs", value="tab-chat", children=[
                dcc.Tab(label="HR Query Assistant", value="tab-chat", children=layout_chat_assistant()),
                dcc.Tab(label="Analytics Dashboard", value="tab-dashboard", children=layout_dashboard()),
                dcc.Tab(label="Database Schema", value="tab-schema", children=layout_schema_explorer()),
                dcc.Tab(label="Data Entry", value="tab-data-entry", children=layout_data_entry()),
                dcc.Tab(label="Settings", value="tab-settings", children=layout_settings())
            ]),
            
            # Footer
            html.Div([
                html.P("© 2026 Company Workforce Analytics Assistant. All data shown is synthetically simulated.", className="text-center text-muted small mt-5 pt-3 border-top", style={"borderColor": "rgba(255,255,255,0.04)"})
            ])
        ], className="py-4")
    ])

# Base App Root containing store values and content viewport
app.layout = html.Div([
    # Session state storage components
    dcc.Store(id="session-user", storage_type="session"),
    dcc.Store(id="auth-mode", data="login", storage_type="session"), # "login" or "register"
    dcc.Store(id="cached-api-key", storage_type="session"),
    
    # Viewport containing either Auth page or Dashboard Shell
    html.Div(id="main-app-viewport")
])


# --- CALLBACK LOGIC ---

# 1. Handle Navigation Auth Routing (Toggle between Login, Registration, and Main App)
@app.callback(
    Output("main-app-viewport", "children"),
    Input("session-user", "data"),
    Input("auth-mode", "data")
)
def render_main_viewport(session_user, auth_mode):
    if session_user:
        return layout_dashboard_shell(session_user)
    else:
        if auth_mode == "register":
            return layout_login_page(register_mode=True)
        return layout_login_page(register_mode=False)


# 2. Toggle Auth Mode Store
@app.callback(
    Output("auth-mode", "data"),
    Input("auth-switch-mode-btn", "n_clicks"),
    State("auth-mode", "data"),
    prevent_initial_call=True
)
def switch_auth_mode(n_clicks, current_mode):
    if not n_clicks:
        return current_mode
    return "register" if current_mode == "login" else "login"


# 3. Handle Login/Registration submissions
@app.callback(
    Output("session-user", "data"),
    Output("auth-error-output", "children"),
    Input("auth-submit-btn", "n_clicks"),
    State("auth-username", "value"),
    State("auth-password", "value"),
    State("auth-role", "value"),
    State("auth-mode", "data"),
    prevent_initial_call=True
)
def handle_auth_submission(n_clicks, username, password, role, auth_mode):
    if not n_clicks:
        return None, None
        
    if not username or not password:
        return None, dbc.Alert("Please provide both a username and password.", color="warning")
        
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    if auth_mode == "login":
        # Hash input password
        pwd_hash = hash_password(password)
        cursor.execute("SELECT username FROM users WHERE username = ? AND password_hash = ?", (username, pwd_hash))
        user_record = cursor.fetchone()
        conn.close()
        
        if user_record:
            return user_record[0], None
        else:
            return None, dbc.Alert("Invalid username or password.", color="danger")
            
    elif auth_mode == "register":
        # Check if username exists
        cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            conn.close()
            return None, dbc.Alert("Username already exists. Please choose another one.", color="warning")
            
        # Register user
        pwd_hash = hash_password(password)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (username, pwd_hash, role, now_str))
            conn.commit()
            conn.close()
            # Log the user in directly after registration
            return username, None
        except Exception as e:
            conn.close()
            return None, dbc.Alert(f"Registration error: {str(e)}", color="danger")


# 4. Handle Logout click
@app.callback(
    Output("session-user", "data", allow_duplicate=True),
    Output("auth-mode", "data", allow_duplicate=True),
    Input("logout-btn", "n_clicks"),
    prevent_initial_call=True
)
def logout_user(n_clicks):
    if not n_clicks:
        return dash.no_update, dash.no_update
    # Clear session store and set auth page back to login mode
    return None, "login"


# 5. Populate Input Field from Clicked Sample Queries
@app.callback(
    Output("chat-input", "value"),
    Input({"type": "sample-query-btn", "index": dash.dependencies.ALL}, "n_clicks"),
    State({"type": "sample-query-btn", "index": dash.dependencies.ALL}, "children"),
    prevent_initial_call=True
)
def populate_chat_input(n_clicks_list, label_list):
    ctx = callback_context
    if not ctx.triggered:
        return ""
    
    # Identify which button index triggered the callback
    trigger_prop = ctx.triggered[0]['prop_id']
    if 'index' in trigger_prop:
        # trigger_prop is like '{"index":3,"type":"sample-query-btn"}.n_clicks'
        import json
        btn_dict = json.loads(trigger_prop.split('.n_clicks')[0])
        idx = btn_dict['index']
        # Return the label corresponding to that button index
        return label_list[idx]
        
    return ""


# 6. Settings Panel Callbacks
@app.callback(
    Output("settings-save-alert", "children"),
    Output("cached-api-key", "data"),
    Input("save-settings-btn", "n_clicks"),
    State("settings-api-key", "value"),
    prevent_initial_call=True
)
def save_settings(n_clicks, api_key):
    if not n_clicks:
        return None, dash.no_update
    
    # Store api key in session state
    return dbc.Alert("Settings saved successfully!", color="success", dismissable=True), api_key


@app.callback(
    Output("reseed-status", "children"),
    Input("reseed-btn", "n_clicks"),
    prevent_initial_call=True
)
def reseed_database_settings(n_clicks):
    if not n_clicks:
        return ""
    from db_setup import create_database, seed_database
    try:
        create_database(DATABASE_PATH)
        seed_database(DATABASE_PATH)
        return "Database successfully reset and re-seeded!"
    except Exception as e:
        return f"Error resetting database: {str(e)}"


# 7. AI Query Assistant Core Callbacks (Translate NL to SQL, Exec, Display Table, Plot Auto Chart)
@app.callback(
    Output("assistant-status", "children"),
    Output("generated-sql-display", "children"),
    Output("assistant-table-container", "children"),
    Output("assistant-chart", "figure"),
    Output("assistant-chart-container", "style"),
    Output("assistant-output-container", "style"),
    Input("ask-btn", "n_clicks"),
    Input("chat-input", "n_clicks"), # Triggers loading view updates
    State("chat-input", "value"),
    State("cached-api-key", "data"),
    prevent_initial_call=True
)
def process_chat_assistant(ask_clicks, input_clicks, prompt, api_key):
    ctx = callback_context
    trigger = ctx.triggered[0]['prop_id']
    
    if trigger == "chat-input.n_clicks" or not prompt:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        
    # Execute SQL translation pipeline
    sql_query, df, error, engine, warning = translate_and_execute(prompt, api_key)
    
    status_msg = f"Processed using: {engine}."
    if warning:
        status_msg += f" (Note: {warning})"
        
    if error:
        error_alert = dbc.Alert(error, color="danger")
        # Empty graph and hidden container on error
        empty_fig = go.Figure()
        empty_fig.update_layout(template=PLOTLY_TEMPLATE)
        return status_msg, sql_query or "No SQL generated.", error_alert, empty_fig, {"display": "none"}, {"display": "block"}
        
    if df is None or df.empty:
        empty_alert = dbc.Alert("Query returned no records.", color="info")
        empty_fig = go.Figure()
        empty_fig.update_layout(template=PLOTLY_TEMPLATE)
        return status_msg, sql_query, empty_alert, empty_fig, {"display": "none"}, {"display": "block"}
        
    # Generate interactive table
    results_table = dash_table.DataTable(
        columns=[{"name": i, "id": i} for i in df.columns],
        data=df.to_dict('records'),
        page_size=8,
        style_header={
            'backgroundColor': 'rgba(17, 24, 39, 0.95)',
            'color': THEME_COLORS['text'],
            'fontWeight': 'bold',
            'border': '1px solid rgba(255,255,255,0.06)'
        },
        style_cell={
            'backgroundColor': 'rgba(31, 41, 55, 0.2)',
            'color': THEME_COLORS['text_muted'],
            'textAlign': 'left',
            'padding': '8px 12px',
            'border': '1px solid rgba(255,255,255,0.04)',
            'fontFamily': 'Outfit',
            'fontSize': '13.5px'
        },
        style_table={'overflowX': 'auto'}
    )
    
    # Auto-generate appropriate Chart based on DataFrame structure
    chart_style = {"display": "block"}
    fig = go.Figure()
    
    cols = df.columns.tolist()
    num_cols = len(cols)
    row_count = len(df)
    
    # Rule 1: Single scalar value or 1 row with 1 column -> No chart needed, hide container
    if num_cols == 1 and row_count == 1:
        chart_style = {"display": "none"}
        
    # Rule 2: Temporal column present (year or date)
    elif any(col.lower() in ['year', 'hire_year', 'date', 'month', 'review_date', 'hire_date'] for col in cols):
        date_col = [col for col in cols if any(kw in col.lower() for kw in ['year', 'date', 'month'])][0]
        # Find numeric column for Y axis
        num_fields = df.select_dtypes(include=['number']).columns.tolist()
        y_col = num_fields[0] if num_fields else cols[0] if cols[0] != date_col else cols[1]
        
        fig = px.line(df, x=date_col, y=y_col, title=f"{y_col} trend by {date_col}", template=PLOTLY_TEMPLATE)
        fig.update_traces(line_color=THEME_COLORS['accent'], line_width=3, mode="lines+markers")
        
    # Rule 3: 1 Categorical column + 1 Numeric Column
    elif num_cols == 2:
        num_fields = df.select_dtypes(include=['number']).columns.tolist()
        cat_fields = [c for c in cols if c not in num_fields]
        
        if len(num_fields) == 1 and len(cat_fields) == 1:
            cat_col = cat_fields[0]
            num_col = num_fields[0]
            
            # If categories are small (<=4), make a Pie Chart, else a Bar Chart
            if df[cat_col].nunique() <= 4:
                fig = px.pie(df, names=cat_col, values=num_col, title=f"Distribution of {num_col} by {cat_col}", template=PLOTLY_TEMPLATE)
                fig.update_traces(textposition='inside', textinfo='percent+label')
            else:
                fig = px.bar(df, x=cat_col, y=num_col, title=f"Average/Total {num_col} by {cat_col}", template=PLOTLY_TEMPLATE)
                fig.update_traces(marker_color=THEME_COLORS['accent'])
        else:
            # Fallback bar chart
            fig = px.bar(df, x=cols[0], y=cols[1], template=PLOTLY_TEMPLATE)
            fig.update_traces(marker_color=THEME_COLORS['accent'])
            
    # Rule 4: More than 2 columns
    else:
        num_fields = df.select_dtypes(include=['number']).columns.tolist()
        if len(num_fields) >= 2:
            # Scatter plot
            fig = px.scatter(df, x=num_fields[0], y=num_fields[1], color=cols[0], template=PLOTLY_TEMPLATE)
        else:
            # Simple bar chart using the first column as X and second as Y
            fig = px.bar(df, x=cols[0], y=cols[1], template=PLOTLY_TEMPLATE)
            fig.update_traces(marker_color=THEME_COLORS['accent'])
            
    # Apply global styles to chart
    if chart_style["display"] == "block":
        fig.update_layout(
            margin=dict(l=20, r=20, t=40, b=20),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(gridcolor=THEME_COLORS['grid_color'], showline=False),
            yaxis=dict(gridcolor=THEME_COLORS['grid_color'], showline=False),
            title_font=dict(family="Outfit", size=16),
            font=dict(family="Outfit")
        )
        
    return status_msg, sql_query, results_table, fig, chart_style, {"display": "block"}


# 8. Load Pre-defined KPI Cards & Dashboard Charts on demand when dashboard tab loaded
@app.callback(
    Output("kpi-headcount", "children"),
    Output("kpi-salary", "children"),
    Output("kpi-performance", "children"),
    Output("kpi-turnover", "children"),
    Output("chart-dept-headcount", "figure"),
    Output("chart-dept-salaries", "figure"),
    Output("chart-hiring-trend", "figure"),
    Output("chart-perf-dist", "figure"),
    Input("app-tabs", "value")
)
def populate_hr_dashboard(active_tab):
    # Only load query when Dashboard tab is open
    if active_tab != "tab-dashboard":
        return dash.no_update
        
    # Query KPIs
    df_headcount, _ = execute_query("SELECT COUNT(*) as val FROM employees WHERE status = 'Active'")
    df_salary, _ = execute_query("SELECT ROUND(AVG(salary), 2) as val FROM employees WHERE status = 'Active'")
    df_perf, _ = execute_query("SELECT ROUND(AVG(performance_score), 2) as val FROM employees WHERE status = 'Active'")
    
    # Calculate Attrition/Turnover Rate: Terminated / Total ever hired
    df_turnover, _ = execute_query("""
        SELECT ROUND(CAST(COUNT(CASE WHEN status = 'Terminated' THEN 1 END) AS FLOAT) / COUNT(*) * 100, 2) as val
        FROM employees
    """)
    
    hc_val = int(df_headcount['val'].iloc[0]) if not df_headcount.empty else 0
    sal_val = f"${df_salary['val'].iloc[0]:,.0f}" if not df_salary.empty else "$0"
    perf_val = f"{df_perf['val'].iloc[0]:.2f}/5" if not df_perf.empty else "0/5"
    turnover_val = f"{df_turnover['val'].iloc[0]:.1f}%" if not df_turnover.empty else "0%"
    
    # 1. Chart: Headcount by Department
    df_dept_hc, _ = execute_query("SELECT department, COUNT(*) as headcount FROM employees WHERE status = 'Active' GROUP BY department ORDER BY headcount DESC")
    fig_dept_hc = px.bar(df_dept_hc, x="department", y="headcount", text="headcount", template=PLOTLY_TEMPLATE)
    fig_dept_hc.update_traces(marker_color=THEME_COLORS['accent'], textposition="outside")
    fig_dept_hc.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showline=False),
        yaxis=dict(gridcolor=THEME_COLORS['grid_color'], showline=False)
    )
    
    # 2. Chart: Average Salary & Budget comparison by Department
    df_dept_sal_bud, _ = execute_query("""
        SELECT d.name as department, ROUND(AVG(e.salary), 2) as avg_salary, d.budget
        FROM departments d
        LEFT JOIN employees e ON d.name = e.department AND e.status = 'Active'
        GROUP BY d.name
    """)
    
    fig_dept_sal_bud = go.Figure()
    fig_dept_sal_bud.add_trace(go.Bar(
        x=df_dept_sal_bud["department"],
        y=df_dept_sal_bud["avg_salary"],
        name="Avg Salary ($)",
        marker_color=THEME_COLORS['accent']
    ))
    fig_dept_sal_bud.add_trace(go.Scatter(
        x=df_dept_sal_bud["department"],
        y=df_dept_sal_bud["budget"] / 10, # Scaled down for dual axis comparison or simple correlation
        name="Dept Budget / 10 ($)",
        mode="lines+markers",
        line=dict(color=THEME_COLORS['success'], width=3),
        marker=dict(size=8)
    ))
    fig_dept_sal_bud.update_layout(
        template=PLOTLY_TEMPLATE,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showline=False),
        yaxis=dict(gridcolor=THEME_COLORS['grid_color'], showline=False)
    )
    
    # 3. Chart: Hiring Trend Over Time (By Year)
    df_hire_trend, _ = execute_query("SELECT strftime('%Y', hire_date) as year, COUNT(*) as count FROM employees GROUP BY year ORDER BY year")
    fig_hire_trend = px.line(df_hire_trend, x="year", y="count", template=PLOTLY_TEMPLATE)
    fig_hire_trend.update_traces(line_color=THEME_COLORS['accent'], line_width=3, mode="lines+markers")
    fig_hire_trend.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(gridcolor=THEME_COLORS['grid_color'], showline=False),
        yaxis=dict(gridcolor=THEME_COLORS['grid_color'], showline=False)
    )
    
    # 4. Chart: Performance Distribution
    df_perf_dist, _ = execute_query("SELECT performance_score, COUNT(*) as count FROM employees WHERE status = 'Active' GROUP BY performance_score ORDER BY performance_score")
    fig_perf_dist = px.pie(df_perf_dist, names="performance_score", values="count", hole=0.4, template=PLOTLY_TEMPLATE)
    fig_perf_dist.update_traces(textposition='inside', textinfo='percent')
    fig_perf_dist.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    
    return hc_val, sal_val, perf_val, turnover_val, fig_dept_hc, fig_dept_sal_bud, fig_hire_trend, fig_perf_dist


# 9. Populate Data Entry managers list when tab selected
@app.callback(
    Output("entry-manager", "options"),
    Input("app-tabs", "value")
)
def populate_entry_managers_list(active_tab):
    if active_tab != "tab-data-entry":
        return dash.no_update
    
    # Query active employees to serve as reporting manager
    query = """
        SELECT id, first_name || ' ' || last_name || ' (' || job_title || ')' as name 
        FROM employees 
        WHERE status = 'Active' 
        ORDER BY name
    """
    df, error = execute_query(query)
    
    if error or df is None or df.empty:
        return []
        
    return [{"label": row["name"], "value": int(row["id"])} for _, row in df.iterrows()]


# 10. Handle Data Entry form submission
@app.callback(
    Output("entry-submit-output", "children"),
    Output("entry-first-name", "value"),
    Output("entry-last-name", "value"),
    Output("entry-email", "value"),
    Output("entry-age", "value"),
    Output("entry-job-title", "value"),
    Output("entry-salary", "value"),
    Output("entry-state", "value"),
    Input("entry-submit-btn", "n_clicks"),
    State("entry-first-name", "value"),
    State("entry-last-name", "value"),
    State("entry-email", "value"),
    State("entry-age", "value"),
    State("entry-department", "value"),
    State("entry-job-title", "value"),
    State("entry-salary", "value"),
    State("entry-hire-date", "value"),
    State("entry-gender", "value"),
    State("entry-state", "value"),
    State("entry-perf", "value"),
    State("entry-manager", "value"),
    State("entry-status", "value"),
    prevent_initial_call=True
)
def handle_data_entry_submit(n_clicks, first_name, last_name, email, age, dept, job_title, salary, hire_date, gender, state, perf, manager_id, status):
    if not n_clicks:
        return dash.no_update
        
    # Validation
    if not all([first_name, last_name, age, dept, job_title, salary, hire_date, gender, state, status]):
        return dbc.Alert("Please fill in all required fields.", color="warning"), first_name, last_name, email, age, job_title, salary, state
        
    # Auto-generate email if empty
    if not email or not email.strip():
        # Clean names
        f_clean = first_name.strip().lower()
        l_clean = last_name.strip().lower()
        email = f"{f_clean}.{l_clean}@company.com"
        
        # Check uniqueness and resolve conflicts
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM employees WHERE email = ?", (email,))
        count = cursor.fetchone()[0]
        counter = 1
        while count > 0:
            email = f"{f_clean}.{l_clean}{counter}@company.com"
            cursor.execute("SELECT COUNT(*) FROM employees WHERE email = ?", (email,))
            count = cursor.fetchone()[0]
            counter += 1
        conn.close()
    
    # Cast variables
    try:
        age = int(age)
        salary = float(salary)
        perf = int(perf)
        manager_id = int(manager_id) if manager_id is not None else None
    except ValueError:
        return dbc.Alert("Invalid number format for Age or Salary.", color="danger"), first_name, last_name, email, age, job_title, salary, state

    # Insert into database
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO employees (first_name, last_name, email, department, job_title, salary, hire_date, performance_score, manager_id, gender, age, state, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (first_name.strip(), last_name.strip(), email.strip(), dept, job_title.strip(), salary, hire_date.strip(), perf, manager_id, gender, age, state.strip().upper(), status))
        conn.commit()
        success_msg = f"Successfully added employee: {first_name.strip()} {last_name.strip()} ({email.strip()})"
        return dbc.Alert(success_msg, color="success"), "", "", "", "", "", "", ""
    except Exception as e:
        return dbc.Alert(f"Database error: {str(e)}", color="danger"), first_name, last_name, email, age, job_title, salary, state
    finally:
        conn.close()


# Expose Flask server as app on Vercel to bypass Dash instance WSGI call mismatch
if os.environ.get("VERCEL"):
    app = app.server

# Run local web server
if __name__ == '__main__':
    app.run(debug=True, port=8050)
