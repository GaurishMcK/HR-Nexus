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
    initial_sidebar_state="expanded"
)

# --- STRICT PROFESSIONAL BLUE THEME CSS ---
st.markdown("""
    <style>
    /* VARIABLES */
    :root {
        --brand-blue: #0f4c81;       /* Classic Navy */
        --brand-bright: #2563eb;     /* Action Blue */
        --brand-bg: #f1f5f9;         /* Slate Light */
        --text-dark: #1e293b;        /* Slate Dark */
    }

    /* GLOBAL RESET */
    html, body, [class*="css"] {
        font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
        color: var(--text-dark);
    }

    /* REMOVE RED ALERTS (Streamlit override) */
    .stAlert {
        background-color: #eff6ff !important;
        border: 1px solid #bfdbfe !important;
        color: #1e40af !important;
    }

    /* HEADERS */
    .main-header {
        font-weight: 700;
        color: var(--brand-blue);
        font-size: 2rem;
        padding-bottom: 15px;
        border-bottom: 3px solid var(--brand-bright);
        margin-bottom: 30px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* SIDEBAR */
    section[data-testid="stSidebar"] {
        background-color: white;
        border-right: 1px solid #cbd5e1;
    }

    /* METRICS CONTAINERS */
    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #cbd5e1;
        border-left: 5px solid var(--brand-bright);
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }

    /* --- BUTTON STYLING (ALL BLUE) --- */
    
    /* Secondary/Outline Buttons */
    div.stButton > button {
        background-color: white;
        color: var(--brand-bright);
        border: 2px solid var(--brand-bright);
        border-radius: 4px;
        font-weight: 600;
        transition: all 0.2s;
    }
    div.stButton > button:hover {
        background-color: #eff6ff;
        color: var(--brand-blue);
        border-color: var(--brand-blue);
    }
    div.stButton > button:active {
        background-color: #dbeafe;
    }

    /* Primary/Solid Buttons */
    div.stButton > button[kind="primary"] {
        background-color: var(--brand-bright);
        color: white;
        border: 2px solid var(--brand-bright);
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: var(--brand-blue);
        border-color: var(--brand-blue);
    }

    /* TABS */
    .stTabs [aria-selected="true"] {
        border-bottom-color: var(--brand-bright) !important;
        color: var(--brand-bright) !important;
        font-weight: bold;
    }

    /* INPUT FIELDS */
    div[data-baseweb="input"] {
        border-radius: 4px;
    }
    div[data-baseweb="input"]:focus-within {
        border-color: var(--brand-bright) !important;
        box-shadow: 0 0 0 1px var(--brand-bright) !important;
    }

    /* CHAT BUBBLES */
    .stChatMessage {
        background-color: transparent;
        border-bottom: 1px solid #f1f5f9;
    }
    /* Hide default avatars to remove emoji reliance */
    .stChatMessage .st-emotion-cache-1p1m4ay, .stChatMessage .st-emotion-cache-10trblm {
        display: none;
    }
    </style>
""", unsafe_allow_html=True)

# --- CLOUD/FIRST-RUN INITIALIZATION ---
if not os.path.exists(Config.DB_PATH):
    if 'has_run_setup' not in st.session_state:
        # Replaced warning icon with blue info box
        st.info("System Initialization: Building Database & Index...")
        try:
            import setup_env 
            agent_temp = HRAgent()
            res = agent_temp.rebuild_knowledge_base()
            st.session_state['has_run_setup'] = True
            st.success(f"Setup Complete: {res}")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.code(f"Setup Failed: {e}") # Using code block to avoid red text

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
        st.markdown("<div style='text-align: center; margin-top: 80px; color: #0f4c81;'><h1>HR SENTINEL</h1></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center; color: #64748b; margin-bottom: 40px; letter-spacing: 1px; font-size: 0.9rem;'>ENTERPRISE COMPLIANCE SYSTEM</div>", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.markdown("### Authorization")
            with st.form("login_form"):
                uid = st.text_input("Employee ID", placeholder="Enter Credentials")
                submitted = st.form_submit_button("AUTHENTICATE ACCESS", type="primary", use_container_width=True)
                
                if submitted:
                    user = fetch_user(uid)
                    if user:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        # Custom styled error box (Blue/Grey) instead of Red
                        st.markdown("""
                            <div style="padding: 10px; background-color: #f1f5f9; border-left: 5px solid #334155; color: #334155; margin-top: 10px;">
                                <b>Access Denied:</b> ID not found in directory.
                            </div>
                        """, unsafe_allow_html=True)

# ====================================================
# MAIN APPLICATION
# ====================================================
else:
    user = st.session_state.user
    agent = st.session_state.agent
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown(f"### {user['name']}")
        st.markdown(f"**ID:** {user['id']}")
        st.markdown(f"**ROLE:** {user['role']}")
        st.markdown(f"**REGION:** {user['region']}")
        st.divider()
        
        st.caption("CONNECTION")
        st.markdown("**Secure**")
        
        st.divider()
        if st.button("SIGN OUT", use_container_width=True):
            # 1. Clear specific keys to ensure a fresh state
            keys_to_clear = ['user', 'messages', 'scraped_data', 'analysis_res', 'draft_reply']
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    # ====================================================
    # VIEW 1: EMPLOYEE
    # ====================================================
    if user['role'] == 'EMP':
        st.markdown('<div class="main-header">EMPLOYEE SUPPORT PORTAL</div>', unsafe_allow_html=True)

        # Load History
        if "messages" not in st.session_state or not st.session_state.messages:
            db_history = fetch_chat_history(user['id'])
            st.session_state.messages = db_history if db_history else []

        # Chat Interface
        chat_container = st.container(height=500, border=True)
        with chat_container:
            for msg in st.session_state.messages:
                # Custom HTML bubbles to avoid emojis
                bg_color = "#f1f5f9" if msg["role"] == "user" else "#eff6ff"
                align = "right" if msg["role"] == "user" else "left"
                border = "#e2e8f0" if msg["role"] == "user" else "#bfdbfe"
                
                st.markdown(f"""
                    <div style="text-align: {align}; margin-bottom: 10px;">
                        <div style="display: inline-block; padding: 10px 15px; background-color: {bg_color}; border: 1px solid {border}; border-radius: 8px; max-width: 80%;">
                            {msg['content']}
                        </div>
                    </div>
                """, unsafe_allow_html=True)

        # Input Area
        if question := st.chat_input("Type your inquiry here..."):
            st.session_state.messages.append({"role": "user", "content": question})
            with chat_container:
                st.markdown(f"<div style='text-align: right; margin-bottom: 10px;'><div style='display: inline-block; padding: 10px 15px; background-color: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 8px;'>{question}</div></div>", unsafe_allow_html=True)
            save_chat_message(user['id'], "user", question)

            # Agent Logic
            with st.spinner("Processing request..."):
                analysis = agent.calculate_score(question)
                score = analysis['final_score']
                metrics = analysis['metrics']

            if score > 2.7:
                assigned_to = assign_hr_round_robin()
                t_id = create_ticket(user['id'], question, score, assigned_to)
                
                # Custom Blue Escalation Box (No Red)
                response_text = f"**ESCALATION PROTOCOL INITIATED**\n\nTicket #{t_id} has been generated. Specialist {assigned_to} has been notified for immediate review."
                final_html = f"<div style='text-align: left; margin-bottom: 10px;'><div style='display: inline-block; padding: 10px 15px; background-color: #eff6ff; border: 1px solid #2563eb; color: #1e40af; border-radius: 8px;'>{response_text}</div></div>"
            else:
                response_text = agent.get_rag_answer(question, user['region'])
                final_html = f"<div style='text-align: left; margin-bottom: 10px;'><div style='display: inline-block; padding: 10px 15px; background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px;'>{response_text}</div></div>"

            st.session_state.messages.append({"role": "assistant", "content": response_text})
            with chat_container:
                st.markdown(final_html, unsafe_allow_html=True)
            save_chat_message(user['id'], "assistant", response_text)

    # ====================================================
    # VIEW 2: HR DASHBOARD
    # ====================================================
    elif user['role'] in ['HR', 'ADMIN']:
        
        header_title = "SYSTEM ADMINISTRATION" if user['role'] == 'ADMIN' else "AGENT DASHBOARD"
        st.markdown(f'<div class="main-header">{header_title}</div>', unsafe_allow_html=True)

        df_tickets = get_all_tickets()
        if user['role'] == 'HR':
            df_tickets = df_tickets[df_tickets['assigned_to'] == user['id']]

        # Tabs
        tabs = ["TICKET MANAGEMENT"]
        if user['role'] == 'ADMIN':
            tabs += ["KNOWLEDGE BASE", "COMPLIANCE MONITOR"]
        
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
                with st.container(border=True):
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
                st.subheader("Resolution Console")
                open_tickets = df_tickets[df_tickets['status'] != 'Resolved']

                if not open_tickets.empty:
                    with st.container(border=True):
                        selected_t_id = st.selectbox("Select Case File", open_tickets['ticket_id'], format_func=lambda x: f"Case #{x}")
                        ticket_row = open_tickets[open_tickets['ticket_id'] == selected_t_id].iloc[0]
                        
                        st.markdown(f"**Subject:** {ticket_row['question']}")
                        st.caption(f"User: {ticket_row['emp_id']} | Score: {ticket_row['score']}")
                        st.divider()

                        with st.form("reply_form"):
                            # Primary Blue Button
                            if st.form_submit_button("GENERATE AI DRAFT", type="primary", use_container_width=True):
                                with st.spinner("Analyzing..."):
                                    t_data = ticket_row.to_dict()
                                    if 'region' not in t_data: t_data['region'] = 'India'
                                    draft_text = agent.draft_ticket_resolution(t_data)
                                    st.session_state['draft_reply'] = draft_text
                                    st.rerun()

                            default_text = st.session_state.get('draft_reply', "")
                            reply_text = st.text_area("Draft Body", value=default_text, height=150)

                            c1, c2 = st.columns(2)
                            with c1:
                                btn_resolve = st.form_submit_button("SEND & RESOLVE", type="primary", use_container_width=True)
                            with c2:
                                btn_progress = st.form_submit_button("SEND & UPDATE", use_container_width=True)

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
                                st.info("Status Updated.")
                                time.sleep(1)
                                st.rerun()
                else:
                    st.info("Queue empty.")

        # TAB 2: KNOWLEDGE BASE
        if user['role'] == 'ADMIN' and len(tabs) > 1:
            with active_tab[1]:
                st.subheader("Repository Management")
                c1, c2 = st.columns(2)
                with c1:
                    with st.container(border=True):
                        st.markdown("##### Upload Document")
                        uploaded_file = st.file_uploader("Select PDF File", type="pdf")
                        if uploaded_file:
                            save_path = os.path.join(Config.POLICIES_DIR, uploaded_file.name)
                            with open(save_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            st.success(f"File Stored: {uploaded_file.name}")
                with c2:
                    with st.container(border=True):
                        st.markdown("##### System Indexing")
                        st.caption("Synchronize vector database with updated documents.")
                        if st.button("REBUILD INDEX", type="primary"):
                            with st.status("Indexing...", expanded=True):
                                res = agent.rebuild_knowledge_base()
                                st.success(res)

        # TAB 3: WATCHDOG
        if user['role'] == 'ADMIN' and len(tabs) > 2:
            with active_tab[2]:
                watchdog = PolicyWatchdog(agent)
                st.subheader("Regulatory Monitor")
                
                if st.button("INITIATE EXTERNAL SCAN", type="primary"):
                    with st.spinner("Connecting to sources..."):
                        res = watchdog.check_for_updates()
                        if res['status'] == 'success':
                            st.session_state['scraped_data'] = res
                            st.info("Update Detected")
                        else:
                            st.markdown(f"<div style='color: #475569;'>{res['content']}</div>", unsafe_allow_html=True)

                if 'scraped_data' in st.session_state:
                    data = st.session_state['scraped_data']
                    st.divider()
                    
                    c_left, c_right = st.columns(2)
                    with c_left:
                        with st.container(border=True):
                            st.markdown(f"##### {data['title']}")
                            st.markdown("---")
                            st.markdown(data['body'])
                    
                    with c_right:
                        st.markdown("##### Analysis Tools")
                        if st.button("RUN IMPACT ANALYSIS", type="primary", use_container_width=True):
                            with st.status("Analyzing...", expanded=True):
                                analysis = watchdog.analyze_impact(data['body'])
                                st.session_state['analysis_res'] = analysis
                        
                        if 'analysis_res' in st.session_state:
                            res = st.session_state['analysis_res']
                            with st.expander("View Comparison Matrix"):
                                st.markdown(res['comparison_analysis'])
                            
                            email_draft = watchdog.draft_legal_email(res['comparison_analysis'])
                            st.text_area("Legal Briefing Draft", value=email_draft, height=200)
                            
                            if st.button("DISPATCH TO LEGAL", type="primary", use_container_width=True):
                                st.success("Briefing dispatched.")
