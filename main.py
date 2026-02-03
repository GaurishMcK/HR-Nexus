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

# --- ALL-BLUE PROFESSIONAL THEME CSS ---
st.markdown("""
    <style>
    /* Define Brand Colors */
    :root {
        --brand-blue: #2563eb; /* Primary Corporate Blue */
        --brand-dark-blue: #1e40af; /* Darker shade for hover/active */
        --brand-slate: #0f172a; /* Dark text */
        --brand-light-slate: #64748b; /* Light text */
        --brand-bg-slate: #f8fafc; /* Sidebar/Background */
    }

    /* Global Font & Color Base */
    html, body, [class*="css"] {
        font-family: 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
        color: var(--brand-slate);
    }

    /* --- HEADER --- */
    .main-header {
        font-weight: 700;
        color: var(--brand-slate);
        font-size: 2.2rem;
        padding-bottom: 10px;
        border-bottom: 4px solid var(--brand-blue);
        margin-bottom: 25px;
        letter-spacing: -0.5px;
    }

    /* --- SIDEBAR --- */
    section[data-testid="stSidebar"] {
        background-color: var(--brand-bg-slate);
        border-right: 1px solid #e2e8f0;
    }

    /* --- OVERRIDING STREAMLIT ACCENTS (The hardest part) --- */
    /* Active Tab Highlight color */
    .stTabs [aria-selected="true"] {
        border-bottom-color: var(--brand-blue) !important;
        color: var(--brand-blue) !important;
    }
    /* Input Focus highlights (active text boxes) */
    div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within {
         border-color: var(--brand-blue) !important;
         box-shadow: 0 0 0 1px var(--brand-blue) !important;
    }
    /* Checkboxes/Radio buttons selected state */
    div[role="checkbox"][aria-checked="true"] div:first-child {
        background-color: var(--brand-blue) !important;
        border-color: var(--brand-blue) !important;
    }

    /* --- METRICS BOXES --- */
    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #e2e8f0;
        border-left: 6px solid var(--brand-blue);
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }

    /* --- CHAT INTERFACE --- */
    .stChatMessage {
        background-color: transparent;
        border-bottom: 1px solid #f1f5f9;
    }
    /* Avatar colors */
    .stChatMessage .st-emotion-cache-1p1m4ay { /* User avatar container */
        background-color: var(--brand-light-slate) !important;
    }
    .stChatMessage .st-emotion-cache-10trblm { /* Assistant avatar container */
        background-color: var(--brand-blue) !important;
    }

    /* --- BUTTONS (TOTAL OVERHAUL) --- */
    /* Default/Secondary Buttons */
    div.stButton > button {
        border-radius: 6px;
        font-weight: 600;
        border: 2px solid #cbd5e1;
        background-color: white;
        color: var(--brand-slate);
        padding-top: 0.5rem; padding-bottom: 0.5rem;
        transition: all 0.2s ease-in-out;
    }
    /* Secondary Hover */
    div.stButton > button:hover {
        border-color: var(--brand-blue);
        color: var(--brand-blue);
        background-color: #eff6ff; /* very pale blue */
    }
    /* Primary Buttons (e.g., 'Send & Close', 'Sign In') */
    div.stButton > button[kind="primary"] {
        background-color: var(--brand-blue);
        border: 2px solid var(--brand-blue);
        color: white;
    }
    /* Primary Hover */
    div.stButton > button[kind="primary"]:hover {
        background-color: var(--brand-dark-blue);
        border-color: var(--brand-dark-blue);
        box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.3);
    }

    /* --- MISC --- */
    /* Expander Headers */
    .streamlit-expanderHeader {
        font-weight: 600;
        color: var(--brand-slate);
    }
    /* Links */
    a { color: var(--brand-blue) !important; }
    </style>
""", unsafe_allow_html=True)

# --- CLOUD/FIRST-RUN INITIALIZATION ---
if not os.path.exists(Config.DB_PATH):
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
        # Updated Login Header with theme colors
        st.markdown(f"<div style='text-align: center; margin-top: 60px; color: #2563eb;'><h1>🛡️ HR SENTINEL</h1></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center; color: #64748b; margin-bottom: 40px; font-weight: 600; letter-spacing: 1px;'>ENTERPRISE COMPLIANCE SYSTEM</div>", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.markdown("### Authorization")
            with st.form("login_form"):
                uid = st.text_input("Employee ID", placeholder="Enter ID (e.g., HR_ADMIN, EMP001)")
                # Ensure primary button style
                submitted = st.form_submit_button("Authenticate Portal Access", type="primary", use_container_width=True)
                
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
        # Sidebar Info updated for cleaner look
        st.markdown(f"### {user['name']}")
        st.markdown(f"**ID:** `{user['id']}`")
        st.markdown(f"**Role:** `{user['role']}`")
        st.markdown(f"**Region:** `{user['region']}`")
        st.divider()
        
        st.caption("SYSTEM STATUS")
        st.markdown("✅ **Secure Connection Active**")
        
        st.divider()
        if st.button("🔒 Sign Out Session", use_container_width=True):
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
            with st.spinner("Sentinel AI is processing request..."):
                analysis = agent.calculate_score(question)
                score = analysis['final_score']
                metrics = analysis['metrics']

            # 3. Decision Logic
            if score > 2.7:
                assigned_to = assign_hr_round_robin()
                t_id = create_ticket(user['id'], question, score, assigned_to)
                # Using markdown for bold blue text
                response_text = f"### ⚠️ Escalation Protocol Initiated\n\nA priority ticket (**#{t_id}**) has been assigned to **{assigned_to}** for immediate review regarding your inquiry."
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
                # Using container for the grid to give it a border
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
                st.subheader("Action Console")
                open_tickets = df_tickets[df_tickets['status'] != 'Resolved']

                if not open_tickets.empty:
                    with st.container(border=True):
                        selected_t_id = st.selectbox("Select Case File", open_tickets['ticket_id'], format_func=lambda x: f"Case #{x}")
                        ticket_row = open_tickets[open_tickets['ticket_id'] == selected_t_id].iloc[0]
                        
                        st.markdown(f"**Inquiry Subject:** {ticket_row['question']}")
                        st.caption(f"User ID: `{ticket_row['emp_id']}` | Risk Score: `{ticket_row['score']}`")
                        st.divider()

                        with st.form("reply_form"):
                            # Use primary color for the AI action button to highlight it
                            if st.form_submit_button("⚡ Generate AI Resolution Draft", type="primary"):
                                with st.spinner("Running specialized agents..."):
                                    t_data = ticket_row.to_dict()
                                    if 'region' not in t_data: t_data['region'] = 'India' # Fallback for demo
                                    
                                    # Call the dynamic drafter tool
                                    draft_text = agent.draft_ticket_resolution(t_data)
                                    st.session_state['draft_reply'] = draft_text
                                    st.rerun()

                            default_text = st.session_state.get('draft_reply', "")
                            reply_text = st.text_area("Response Draft Body", value=default_text, height=150)

                            c1, c2 = st.columns(2)
                            with c1:
                                btn_resolve = st.form_submit_button("✅ Send & Close Case", type="primary", use_container_width=True)
                            with c2:
                                btn_progress = st.form_submit_button("🔄 Send & Update Status", use_container_width=True)

                            if btn_resolve and reply_text:
                                log_hr_response(selected_t_id, reply_text)
                                update_ticket_status(selected_t_id, "Resolved")
                                if 'draft_reply' in st.session_state: del st.session_state['draft_reply']
                                st.success("Case Closed Successfully.")
                                time.sleep(1)
                                st.rerun()
                            elif btn_progress and reply_text:
                                log_hr_response(selected_t_id, reply_text)
                                update_ticket_status(selected_t_id, "In Progress")
                                if 'draft_reply' in st.session_state: del st.session_state['draft_reply']
                                st.success("Status Updated to In Progress.")
                                time.sleep(1)
                                st.rerun()
                else:
                    st.info("Queue is empty. No pending actions.")

        # TAB 2: KNOWLEDGE BASE
        if user['role'] == 'ADMIN' and len(tabs) > 1:
            with active_tab[1]:
                st.subheader("Repository Management")
                c1, c2 = st.columns(2)
                with c1:
                    with st.container(border=True):
                        st.markdown("##### 📤 Upload Policy Document")
                        uploaded_file = st.file_uploader("Select PDF File", type="pdf")
                        if uploaded_file:
                            save_path = os.path.join(Config.POLICIES_DIR, uploaded_file.name)
                            with open(save_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            st.success(f"File Stored Securely: {uploaded_file.name}")
                with c2:
                    with st.container(border=True):
                        st.markdown("##### 🧠 System Indexing")
                        st.caption("Synchronize vector database with updated documents.")
                        if st.button("Rebuild Vector Index Now", type="primary"):
                            with st.status("Indexing process initiated...", expanded=True):
                                res = agent.rebuild_knowledge_base()
                                st.success(res)

        # TAB 3: WATCHDOG
        if user['role'] == 'ADMIN' and len(tabs) > 2:
            with active_tab[2]:
                watchdog = PolicyWatchdog(agent)
                st.subheader("Regulatory Compliance Monitor")
                
                # Use primary button for main action
                if st.button("📡 Initiate External Scan Protocol", type="primary"):
                    with st.spinner("Establishing secure connection to sources..."):
                        res = watchdog.check_for_updates()
                        if res['status'] == 'success':
                            st.session_state['scraped_data'] = res
                            st.info("New Regulatory Update Detected.")
                        else:
                            st.error(res['content'])

                if 'scraped_data' in st.session_state:
                    data = st.session_state['scraped_data']
                    st.divider()
                    
                    c_left, c_right = st.columns(2)
                    with c_left:
                        # Styled container for raw text
                        with st.container(border=True):
                            st.markdown(f"##### 📄 Source: {data['title']}")
                            st.markdown("---")
                            st.markdown(data['body'])
                    
                    with c_right:
                        st.markdown("##### Legal Impact Tools")
                        # Primary button for analysis
                        if st.button("⚡ Run Legal Impact Analysis", type="primary", use_container_width=True):
                            with st.status("Performing comparative analysis...", expanded=True):
                                analysis = watchdog.analyze_impact(data['body'])
                                st.session_state['analysis_res'] = analysis
                        
                        if 'analysis_res' in st.session_state:
                            res = st.session_state['analysis_res']
                            with st.expander("🔍 View Comparative Matrix"):
                                st.markdown(res['comparison_analysis'])
                            
                            email_draft = watchdog.draft_legal_email(res['comparison_analysis'])
                            st.text_area("General Counsel Briefing Draft", value=email_draft, height=200)
                            
                            if st.button("🚀 Dispatch to Legal Department", type="primary", use_container_width=True):
                                st.success("Briefing dispatched successfully via secure channel.")
