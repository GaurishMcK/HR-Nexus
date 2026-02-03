import streamlit as st
import pandas as pd
import time
import os

# --- LOCAL MODULES ---
from config import Config
from modules.database import (
    fetch_user, 
    create_ticket, 
    update_ticket_status, 
    log_hr_response, 
    get_all_tickets,
    fetch_chat_history,
    save_chat_message
)
from modules.agent import HRAgent
from modules.auth import assign_hr_round_robin
from modules.watchdog import PolicyWatchdog

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="HR Sentinel", 
    layout="wide", 
    page_icon="🛡️",
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL BLUE THEME CSS ---
st.markdown("""
    <style>
    /* Global Font */
    html, body, [class*="css"] {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: #334155;
    }
    
    /* Corporate Header Styling */
    .main-header {
        font-weight: 700;
        color: #0f172a; /* Slate 900 */
        font-size: 2.2rem;
        padding-bottom: 10px;
        border-bottom: 3px solid #2563eb; /* Corporate Blue */
        margin-bottom: 20px;
        letter-spacing: -0.5px;
    }
    
    /* Sub-headers */
    h1, h2, h3 {
        color: #1e293b;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #f8fafc; /* Slate 50 */
        border-right: 1px solid #e2e8f0;
    }
    
    /* Metrics Box Styling */
    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #e2e8f0;
        border-left: 5px solid #2563eb; /* Blue Accent */
        padding: 15px;
        border-radius: 6px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    /* Chat Message Bubbles */
    .stChatMessage {
        background-color: transparent;
        border-bottom: 1px solid #f1f5f9;
    }
    
    /* Button Overrides for Professional Look */
    div.stButton > button {
        border-radius: 4px;
        font-weight: 500;
        border: 1px solid #cbd5e1;
        background-color: white;
        color: #334155;
    }
    div.stButton > button:hover {
        border-color: #2563eb;
        color: #2563eb;
        background-color: #eff6ff;
    }
    /* Primary Button Override */
    div.stButton > button[kind="primary"] {
        background-color: #2563eb;
        color: white;
        border: none;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #1d4ed8;
        color: white;
    }
    
    /* Toast/Status styling */
    div[data-testid="stToast"] {
        background-color: #eff6ff;
        border: 1px solid #bfdbfe;
        color: #1e40af;
    }
    </style>
""", unsafe_allow_html=True)

# --- CLOUD/FIRST-RUN INITIALIZATION ---
if not os.path.exists(Config.DB_PATH):
    # This runs only if the DB is missing (first run or cloud restart)
    if 'has_run_setup' not in st.session_state:
        st.info("⚙️ System Initialization: Building Database & Index...")
        try:
            import setup_env 
            agent_temp = HRAgent()
            res = agent_temp.rebuild_knowledge_base()
            st.session_state['has_run_setup'] = True
            st.success(f"Setup Complete: {res}")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Setup Failed: {e}")

# --- SESSION STATE INITIALIZATION ---
if 'agent' not in st.session_state:
    st.session_state.agent = HRAgent()

if 'user' not in st.session_state:
    st.session_state.user = None

# ====================================================
# LOGIN SCREEN
# ====================================================
if not st.session_state.user:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<div style='text-align: center; margin-top: 60px; color: #1e3a8a;'><h1>HR SENTINEL</h1></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center; color: #64748b; margin-bottom: 40px; font-size: 0.9rem;'>ENTERPRISE COMPLIANCE SYSTEM</div>", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.markdown("#### Authorization")
            with st.form("login_form"):
                uid = st.text_input("Employee ID", placeholder="Enter ID (e.g., HR_ADMIN, EMP001)")
                submitted = st.form_submit_button("Authenticate", type="primary", use_container_width=True)
                
                if submitted:
                    user = fetch_user(uid)
                    if user:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Authentication Failed. Invalid Credentials.")

# ====================================================
# MAIN APPLICATION
# ====================================================
else:
    user = st.session_state.user
    agent = st.session_state.agent
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown(f"### {user['name']}")
        st.markdown(f"**ID:** `{user['id']}`")
        st.markdown(f"**Role:** `{user['role']}`")
        st.markdown(f"**Region:** `{user['region']}`")
        st.divider()
        
        st.caption("Session Status")
        st.info("● Active")
        
        st.divider()
        if st.button("Sign Out", use_container_width=True):
            st.session_state.user = None
            st.session_state.messages = []
            st.rerun()

    # ====================================================
    # VIEW 1: EMPLOYEE
    # ====================================================
    if user['role'] == 'EMP':
        st.markdown('<div class="main-header">Employee Support Portal</div>', unsafe_allow_html=True)

        # Load History
        if "messages" not in st.session_state or not st.session_state.messages:
            db_history = fetch_chat_history(user['id'])
            st.session_state.messages = db_history if db_history else []

        # Chat Interface Container
        chat_container = st.container(height=500, border=True)
        with chat_container:
            for msg in st.session_state.messages:
                # Use standard avatars instead of emojis
                avatar = "user" if msg["role"] == "user" else "assistant"
                st.chat_message(msg["role"], avatar=avatar).write(msg["content"])

        # Input Area
        if question := st.chat_input("Type your inquiry here..."):
            # 1. User Message
            st.session_state.messages.append({"role": "user", "content": question})
            with chat_container:
                st.chat_message("user", avatar="user").write(question)
            save_chat_message(user['id'], "user", question)

            # 2. Agent Logic
            with st.spinner("Processing..."):
                analysis = agent.calculate_score(question)
                score = analysis['final_score']
                metrics = analysis['metrics']

            # 3. Decision Logic
            if score > 2.7:
                assigned_to = assign_hr_round_robin()
                t_id = create_ticket(user['id'], question, score, assigned_to)
                response_text = f"ESCALATION NOTICE\nTicket #{t_id} has been created and assigned to {assigned_to} for immediate review."
            else:
                response_text = agent.get_rag_answer(question, user['region'])

            # 4. Assistant Reply
            st.session_state.messages.append({"role": "assistant", "content": response_text})
            with chat_container:
                st.chat_message("assistant", avatar="assistant").write(response_text)
            save_chat_message(user['id'], "assistant", response_text)

    # ====================================================
    # VIEW 2: HR DASHBOARD
    # ====================================================
    elif user['role'] in ['HR', 'ADMIN']:
        
        header_title = "System Administration" if user['role'] == 'ADMIN' else "Agent Dashboard"
        st.markdown(f'<div class="main-header">{header_title}</div>', unsafe_allow_html=True)

        df_tickets = get_all_tickets()
        if user['role'] == 'HR':
            df_tickets = df_tickets[df_tickets['assigned_to'] == user['id']]

        # Tabs
        tabs = ["Ticket Management"]
        if user['role'] == 'ADMIN':
            tabs += ["Knowledge Base", "Compliance Monitor"]
        
        active_tab = st.tabs(tabs)

        # TAB 1: TICKETS
        with active_tab[0]:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Volume", len(df_tickets))
            m2.metric("Pending", len(df_tickets[df_tickets['status'] == 'Open']))
            m3.metric("High Risk", len(df_tickets[df_tickets['score'] >= 3.0]))
            m4.metric("Resolved", len(df_tickets[df_tickets['status'] == 'Resolved']))
            
            st.divider()
            
            c_grid, c_detail = st.columns([1.5, 1])

            with c_grid:
                st.subheader("Active Queue")
                edited_df = st.data_editor(
                    df_tickets,
                    column_config={
                        "status": st.column_config.SelectboxColumn("Status", options=["Open", "In Progress", "Resolved"], required=True),
                        "score": st.column_config.NumberColumn("Risk Index", format="%.2f"),
                        "ticket_id": st.column_config.NumberColumn("ID"),
                        "question": st.column_config.TextColumn("Subject"),
                    },
                    disabled=["ticket_id", "emp_id", "question", "score", "assigned_to"],
                    hide_index=True,
                    use_container_width=True,
                    key="ticket_editor",
                    height=400
                )
                
                if "ticket_editor" in st.session_state and st.session_state["ticket_editor"]["edited_rows"]:
                    for index, changes in st.session_state["ticket_editor"]["edited_rows"].items():
                        if "status" in changes:
                            t_id = int(df_tickets.iloc[index]['ticket_id'])
                            update_ticket_status(t_id, changes['status'])
                            st.rerun()

            with c_detail:
                st.subheader("Action Console")
                open_tickets = df_tickets[df_tickets['status'] != 'Resolved']

                if not open_tickets.empty:
                    with st.container(border=True):
                        selected_t_id = st.selectbox("Select Item", open_tickets['ticket_id'], format_func=lambda x: f"Ticket #{x}")
                        ticket_row = open_tickets[open_tickets['ticket_id'] == selected_t_id].iloc[0]
                        
                        st.markdown(f"**Inquiry:** {ticket_row['question']}")
                        st.caption(f"User: {ticket_row['emp_id']} | Risk: {ticket_row['score']}")
                        st.divider()

                        with st.form("reply_form"):
                            if st.form_submit_button("Generate Response Draft"):
                                with st.spinner("Analyzing..."):
                                    t_data = ticket_row.to_dict()
                                    if 'region' not in t_data: t_data['region'] = 'India' # Fallback for demo
                                    
                                    # Call the dynamic drafter tool
                                    draft_text = agent.draft_ticket_resolution(t_data)
                                    st.session_state['draft_reply'] = draft_text
                                    st.rerun()

                            default_text = st.session_state.get('draft_reply', "")
                            reply_text = st.text_area("Draft Content", value=default_text, height=150)

                            c1, c2 = st.columns(2)
                            with c1:
                                btn_resolve = st.form_submit_button("Send & Close", type="primary", use_container_width=True)
                            with c2:
                                btn_progress = st.form_submit_button("Send & Update", use_container_width=True)

                            if btn_resolve and reply_text:
                                log_hr_response(selected_t_id, reply_text)
                                update_ticket_status(selected_t_id, "Resolved")
                                if 'draft_reply' in st.session_state: del st.session_state['draft_reply']
                                st.success("Case Closed.")
                                time.sleep(1)
                                st.rerun()
                            elif btn_progress and reply_text:
                                log_hr_response(selected_t_id, reply_text)
                                update_ticket_status(selected_t_id, "In Progress")
                                if 'draft_reply' in st.session_state: del st.session_state['draft_reply']
                                st.success("Updated.")
                                time.sleep(1)
                                st.rerun()
                else:
                    st.info("No pending items.")

        # TAB 2: KNOWLEDGE BASE
        if user['role'] == 'ADMIN' and len(tabs) > 1:
            with active_tab[1]:
                st.subheader("Repository Management")
                c1, c2 = st.columns(2)
                with c1:
                    with st.container(border=True):
                        st.markdown("##### Upload Document")
                        uploaded_file = st.file_uploader("Select PDF", type="pdf")
                        if uploaded_file:
                            save_path = os.path.join(Config.POLICIES_DIR, uploaded_file.name)
                            with open(save_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            st.success(f"Stored: {uploaded_file.name}")
                with c2:
                    with st.container(border=True):
                        st.markdown("##### System Indexing")
                        if st.button("Rebuild Vector Index", type="primary"):
                            with st.status("Indexing...", expanded=True):
                                res = agent.rebuild_knowledge_base()
                                st.success(res)

        # TAB 3: WATCHDOG
        if user['role'] == 'ADMIN' and len(tabs) > 2:
            with active_tab[2]:
                watchdog = PolicyWatchdog(agent)
                st.subheader("Regulatory Monitor")
                
                if st.button("Initiate Scan", type="primary"):
                    with st.spinner("Connecting to sources..."):
                        res = watchdog.check_for_updates()
                        if res['status'] == 'success':
                            st.session_state['scraped_data'] = res
                            st.info("Update Detected")
                        else:
                            st.error(res['content'])

                if 'scraped_data' in st.session_state:
                    data = st.session_state['scraped_data']
                    st.divider()
                    
                    c_left, c_right = st.columns(2)
                    with c_left:
                        st.markdown(f"##### {data['title']}")
                        st.text_area("Regulation Text", value=data['body'], height=200, disabled=True)
                    
                    with c_right:
                        st.markdown("##### Analysis Tools")
                        if st.button("Run Impact Analysis"):
                            with st.status("Analyzing...", expanded=True):
                                analysis = watchdog.analyze_impact(data['body'])
                                st.session_state['analysis_res'] = analysis
                        
                        if 'analysis_res' in st.session_state:
                            res = st.session_state['analysis_res']
                            with st.expander("Show Comparison Table"):
                                st.markdown(res['comparison_analysis'])
                            
                            email_draft = watchdog.draft_legal_email(res['comparison_analysis'])
                            st.text_area("Legal Briefing Draft", value=email_draft, height=200)
                            
                            if st.button("Dispatch to Legal", type="primary"):
                                st.success("Sent successfully.")
