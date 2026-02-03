import sqlite3
import pandas as pd
from config import Config

def get_connection():
    return sqlite3.connect(Config.DB_PATH)

def get_employee_salary_details(emp_id):
    mock_db = {
        "EMP001": {"base_hourly": 50, "currency": "USD", "pending_ot_hours": 10}, # John
        "EMP002": {"base_hourly": 1153, "currency": "Rs", "pending_ot_hours": 30}, # Rahul (Approx 2L/month)
    }
    return mock_db.get(emp_id, None)

def fetch_user(user_id):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if user:
        return {'id': user[0], 'name': user[1], 'role': user[2], 'region': user[3], 'lang': user[4]}
    return None

def create_ticket(emp_id, question, score, assigned_hr):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tickets (emp_id, question, score, assigned_to, status) VALUES (?, ?, ?, ?, ?)",
        (emp_id, question, score, assigned_hr, "Open")
    )
    t_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return t_id

def get_hr_list():
    conn = get_connection()
    res = conn.execute("SELECT id FROM users WHERE role='HR'").fetchall()
    conn.close()
    return [r[0] for r in res]

def update_language_pref(emp_id, lang):
    conn = get_connection()
    conn.execute("UPDATE users SET language=? WHERE id=?", (lang, emp_id))
    conn.commit()
    conn.close()

def get_all_tickets():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM tickets", conn)
    conn.close()
    return df

def update_ticket_status(ticket_id, new_status):
    conn = get_connection()
    try:
        conn.execute("UPDATE tickets SET status=? WHERE ticket_id=?", (new_status, ticket_id))
        conn.commit()
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        conn.close()

def log_hr_response(ticket_id, response_text):
    # Optional: You could create a new table for 'responses' if you wanted to keep a history
    # For now, we will just print it to the console to simulate sending an email
    print(f"📧 SENDING EMAIL FOR TICKET #{ticket_id}")
    print(f"📄 CONTENT: {response_text}")
    # In a real app, you would use smtplib here to send the actual email
    return True

def fetch_chat_history(user_id):
    """Loads previous chat messages for a specific user."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content FROM chat_history WHERE user_id=? ORDER BY msg_id ASC", 
        (user_id,)
    ).fetchall()
    conn.close()
    # Convert to list of dicts for Streamlit
    return [{"role": r[0], "content": r[1]} for r in rows]

def save_chat_message(user_id, role, content):
    """Saves a single message to the DB."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)",
        (user_id, role, content)
    )
    conn.commit()
    conn.close()

def log_hr_response(ticket_id, response_text):
    """
    1. Finds which employee owns the ticket.
    2. Inserts the HR response into THAT employee's chat history.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Get Employee ID from the Ticket
    res = cursor.execute("SELECT emp_id FROM tickets WHERE ticket_id=?", (ticket_id,)).fetchone()
    
    if res:
        emp_id = res[0]
        formatted_reply = f"📩 **HR RESPONSE (Ticket #{ticket_id}):**\n{response_text}"
        
        # 2. Save to Chat History as an 'assistant' message
        cursor.execute(
            "INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)",
            (emp_id, 'assistant', formatted_reply)
        )
        conn.commit()
        print(f"✅ Reply saved to chat history for {emp_id}")
    else:
        print("❌ Error: Ticket not found.")
        
    conn.close()