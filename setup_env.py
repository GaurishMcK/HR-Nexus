# setup_env.py
import os
import sqlite3
from fpdf import FPDF
from config import Config

# Ensure data directories exist
os.makedirs(os.path.dirname(Config.DB_PATH), exist_ok=True)
os.makedirs(Config.POLICIES_DIR, exist_ok=True)

# --- 1. GENERATE POLICIES (Same as before) ---
# ... (Keep your existing PDF generation code here if you want, or comment it out to save time) ...

# --- 2. GENERATE SQLITE DATABASE ---
print(f"Initializing Database at: {Config.DB_PATH}")
conn = sqlite3.connect(Config.DB_PATH)
c = conn.cursor()

# Table: Users
c.execute('''CREATE TABLE IF NOT EXISTS users 
             (id TEXT PRIMARY KEY, name TEXT, role TEXT, region TEXT, language TEXT)''')

# Table: Tickets
c.execute('''CREATE TABLE IF NOT EXISTS tickets 
             (ticket_id INTEGER PRIMARY KEY AUTOINCREMENT, emp_id TEXT, 
              question TEXT, score REAL, assigned_to TEXT, status TEXT)''')

# NEW TABLE: Chat History
c.execute('''CREATE TABLE IF NOT EXISTS chat_history 
             (msg_id INTEGER PRIMARY KEY AUTOINCREMENT, 
              user_id TEXT, 
              role TEXT, 
              content TEXT, 
              timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

# --- DATA SEEDING ---
# (Keep your existing user list here)
users = [
    ('EMP001', 'John Doe', 'EMP', 'US', 'English'),
    ('EMP002', 'Rahul Sharma', 'EMP', 'India', 'Hindi'),
    ('HR_ADMIN', 'System Admin', 'ADMIN', 'US', 'English'),
    ('HR001', 'Alice (HR)', 'HR', 'US', 'English'),
    ('HR002', 'Bob (HR)', 'HR', 'India', 'English')
]

c.executemany("INSERT OR REPLACE INTO users VALUES (?,?,?,?,?)", users)
conn.commit()
conn.close()

print("\n✅ Database Updated! 'chat_history' table created.")