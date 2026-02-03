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
    update_language_pref, 
    get_all_tickets,
    fetch_chat_history,
    save_chat_message
)
from modules.agent import HRAgent
from modules.auth import assign_hr_round_robin
from modules.watchdog import PolicyWatchdog

# --- PAGE CONFIG ---
st.set_page_config(page_title="Enterprise HR System", layout="wide", page_icon="🏢")

# --- INITIALIZATION ---
if 'agent' not in st.session_state:
    st.session_state.agent = HRAgent()

if 'user' not in st.session_state:
    st.session_state.user = None

# --- LOGIN SCREEN ---
if not st.session_state.user:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🔐 Enterprise Login")
        with st.form("login_form"):
            uid = st.text_input("Employee ID", placeholder="e.g. EMP001, HR_ADMIN, HR001")
            if st.form_submit_button("Sign In", type="primary"):
                user = fetch_user(uid)
                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Invalid ID. Try 'HR_ADMIN' or 'EMP001'.")

# --- MAIN APPLICATION ---
else:
    user = st.session_state.user
    agent = st.session_state.agent
    
    # --- SIDEBAR (LOGOUT & INFO) ---
    with st.sidebar:
        st.header(f"👤 {user['name']}")
        st.caption(f"Role: {user['role']} | Region: {user['region']}")
        st.divider()
        
        if st.button("🚪 Logout", type="primary"):
            st.session_state.user = None
            st.session_state.messages = []
            st.rerun()

    # ====================================================
    # VIEW 1: EMPLOYEE (Chatbot Interface)
    # ====================================================
    if user['role'] == 'EMP':
        st.subheader("🤖 HR Assistant")

        # 1. LOAD HISTORY FROM DB (If session is empty)
        if "messages" not in st.session_state or not st.session_state.messages:
            db_history = fetch_chat_history(user['id'])
            if db_history:
                st.session_state.messages = db_history
            else:
                st.session_state.messages = []

        # 2. DISPLAY CHAT
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])

        # 3. HANDLE INPUT
        if question := st.chat_input("Ask about policies..."):
            # A. Show & Save USER message
            st.session_state.messages.append({"role": "user", "content": question})
            st.chat_message("user").write(question)
            save_chat_message(user['id'], "user", question) # <--- SAVE TO DB

            # B. Analyze & Respond
            with st.spinner("Supervisor Agent analyzing..."):
                analysis = agent.calculate_score(question)
                score = analysis['final_score']
                metrics = analysis['metrics']

                with st.expander("🧠 Agent Thought Process"):
                    st.write(f"**Intent:** `{metrics.get('intent')}`")
                    st.write(f"**Complexity:** `{metrics.get('type')}`")
                    st.write(f"**Tone Level:** `{metrics.get('tone')}/4`")
                    if score > 2.7:
                        st.error(f"Decision: **ESCALATE** (Score: {score})")
                    else:
                        st.success(f"Decision: **RESEARCH** (Score: {score})")

            if score > Config.SCORING_THRESHOLD:
                # TRIAGE
                assigned_to = assign_hr_round_robin()
                t_id = create_ticket(user['id'], question, score, assigned_to)
                
                response_text = f"⚠️ **Escalation Required** (Ticket #{t_id})\nAssigned to: {assigned_to}."
                st.chat_message("assistant").error(response_text)
                
                # Save ASSISTANT message (Escalation)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
                save_chat_message(user['id'], "assistant", response_text) # <--- SAVE TO DB
            
            else:
                # RAG ANSWER
                response_text = agent.get_rag_answer(question, user['region'])
                st.chat_message("assistant").write(response_text)
                
                # Save ASSISTANT message (Answer)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
                save_chat_message(user['id'], "assistant", response_text) # <--- SAVE TO DB

    # ====================================================
    # VIEW 2: HR DASHBOARD (Admin & Agents)
    # ====================================================
    elif user['role'] in ['HR', 'ADMIN']:
        
        # Header Context
        if user['role'] == 'ADMIN':
            st.title("🛡️ HR Super Admin")
            access_level = "Full"
        else:
            st.title(f"👋 HR Dashboard: {user['name']}")
            access_level = "Restricted"

        # Fetch Tickets
        df_tickets = get_all_tickets()
        
        # Filter for Regular HR (Can only see THEIR assigned tickets)
        if user['role'] == 'HR':
            df_tickets = df_tickets[df_tickets['assigned_to'] == user['id']]

        # --- TABS SETUP ---
        # Admin gets 3 tabs, Agent gets 1 tab
        if user['role'] == 'ADMIN':
            tab_tickets, tab_kb, tab_watchdog = st.tabs(["📋 Ticket Queue", "📚 Knowledge Base", "⚖️ Policy Watchdog"])
        else:
            tab_tickets, = st.tabs(["📋 My Ticket Queue"])

        # ------------------------------------------------
        # TAB 1: TICKET MANAGEMENT (Shared)
        # ------------------------------------------------
        with tab_tickets:
            # Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Queued", len(df_tickets))
            c2.metric("Critical Pending", len(df_tickets[(df_tickets['score'] > 2.7) & (df_tickets['status'] != 'Resolved')]))
            c3.metric("Resolved", len(df_tickets[df_tickets['status'] == 'Resolved']))
            
            st.divider()
            
            if not df_tickets.empty:
                st.subheader("Ticket Actions")
                
                # A. EDITABLE GRID
                edited_df = st.data_editor(
                    df_tickets,
                    column_config={
                        "status": st.column_config.SelectboxColumn("Status", options=["Open", "In Progress", "Resolved"], required=True),
                        "ticket_id": st.column_config.NumberColumn("ID", disabled=True),
                        "score": st.column_config.NumberColumn("Risk", format="%.2f", disabled=True),
                    },
                    disabled=["ticket_id", "emp_id", "question", "score", "assigned_to"],
                    hide_index=True,
                    key="ticket_editor"
                )

                # B. SYNC LOGIC
                if "ticket_editor" in st.session_state and st.session_state["ticket_editor"]["edited_rows"]:
                    updates_made = False
                    for index, changes in st.session_state["ticket_editor"]["edited_rows"].items():
                        if "status" in changes:
                            try:
                                # Safe ID lookup
                                t_id = int(df_tickets.iloc[index]['ticket_id'])
                                update_ticket_status(t_id, changes['status'])
                                updates_made = True
                            except Exception as e:
                                st.error(f"Update failed: {e}")
                    
                    if updates_made:
                        st.toast("✅ Database Updated")
                        time.sleep(1)
                        st.rerun()

                st.divider()

                # C. EMAIL REPLY STATION
                st.subheader("✉️ Reply to Employee")
                open_tickets = df_tickets[df_tickets['status'] != 'Resolved']
                
                if not open_tickets.empty:
                    col_sel, col_form = st.columns([1, 2])
                    
                    with col_sel:
                        selected_t_id = st.selectbox(
                            "Select Ticket", 
                            open_tickets['ticket_id'], 
                            format_func=lambda x: f"#{x}"
                        )
                        ticket_row = open_tickets[open_tickets['ticket_id'] == selected_t_id].iloc[0]
                        st.info(f"**Question:** {ticket_row['question']}")
                        st.caption(f"User: {ticket_row['emp_id']} | Region: {ticket_row.get('region', 'N/A')}")

                    with col_form:
                        with st.form("reply_form"):
                            # 1. AI Resolution Button
                            if st.form_submit_button("🤖 Auto-Draft Resolution (Using Policy)"):
                                # Fetch Context & Calculate
                                policy_context = agent.researcher.search("overtime rate calculation", "India") # Defaulting to India for test
                                math_explanation = agent.researcher.calculate_payroll_adjustment(ticket_row['emp_id'], policy_context or "")
                                
                                if 'region' not in ticket_row:
                                        u = fetch_user(ticket_row['emp_id'])
                                        ticket_row['region'] = u['region'] if u else 'General'

                                draft_text = agent.draft_ticket_resolution(ticket_row)

                                st.session_state['draft_reply'] = draft_text
                                st.rerun()

                            # 2. Text Input
                            default_text = st.session_state.get('draft_reply', "")
                            reply_text = st.text_area("Draft Response", value=default_text, height=150)
                            
                            st.divider()
                            
                            # 3. Two Action Buttons
                            c1, c2 = st.columns(2)
                            with c1:
                                # Primary Action: Close Ticket
                                btn_resolve = st.form_submit_button("✅ Send & Resolve", type="primary")
                            with c2:
                                # Secondary Action: Ask more info / update
                                btn_progress = st.form_submit_button("🔄 Send")

                            # --- HANDLING THE CLICKS ---
                            if btn_resolve and reply_text:
                                log_hr_response(selected_t_id, reply_text)
                                update_ticket_status(selected_t_id, "Resolved")
                                
                                # Clear draft and refresh
                                if 'draft_reply' in st.session_state: del st.session_state['draft_reply']
                                st.success(f"Ticket #{selected_t_id} Resolved!")
                                time.sleep(1)
                                st.rerun()

                            elif btn_progress and reply_text:
                                log_hr_response(selected_t_id, reply_text)
                                update_ticket_status(selected_t_id, "In Progress")
                                
                                # Clear draft and refresh
                                if 'draft_reply' in st.session_state: del st.session_state['draft_reply']
                                st.toast(f"Reply sent! Ticket #{selected_t_id} marked 'In Progress'.")
                                time.sleep(1)
                                st.rerun()

                else:
                    st.success("🎉 No pending tickets!")
            else:
                st.info("No tickets found for your queue.")

        # ------------------------------------------------
        # TAB 2: KNOWLEDGE BASE (Admin Only)
        # ------------------------------------------------
        if user['role'] == 'ADMIN':
            with tab_kb:
                st.subheader("📚 Knowledge Base Management")
                
                col_up, col_act = st.columns(2)
                
                with col_up:
                    st.write("#### 1. Upload Policy")
                    uploaded_file = st.file_uploader("Upload PDF", type="pdf")
                    if uploaded_file:
                        save_path = os.path.join(Config.POLICIES_DIR, uploaded_file.name)
                        with open(save_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        st.success(f"Saved: {uploaded_file.name}")

                with col_act:
                    st.write("#### 2. Rebuild Brain")
                    if st.button("🔄 Rebuild Index", type="primary"):
                        with st.status("Processing...", expanded=True) as status:
                            res = agent.rebuild_knowledge_base()
                            status.update(label="Complete!", state="complete", expanded=False)
                            st.success(res)

        # ------------------------------------------------
        # TAB 3: POLICY WATCHDOG (Admin Only)
        # ------------------------------------------------
        if user['role'] == 'ADMIN':
            with tab_watchdog:
                watchdog = PolicyWatchdog(agent)
                st.subheader("🌐 Regulatory Monitor")
                
                if st.button("📡 Scan External Portal"):
                    with st.spinner("Scraping government simulator..."):
                        res = watchdog.check_for_updates()
                        if res['status'] == 'success':
                            st.session_state['scraped_data'] = res
                            st.success("New Regulation Found!")
                        else:
                            st.error(res['content'])

                if 'scraped_data' in st.session_state:
                    data = st.session_state['scraped_data']
                    st.info(f"**Found:** {data['title']}")
                    with st.expander("Read Raw Text"):
                        st.write(data['body'])

                    if st.button("🧠 Analyze Impact"):
                        with st.spinner("Comparing against internal PDFs..."):
                            analysis = watchdog.analyze_impact(data['body'])
                            st.session_state['analysis_res'] = analysis
                    
                    if 'analysis_res' in st.session_state:
                        res = st.session_state['analysis_res']
                        st.markdown("### Analysis Report")
                        st.markdown(res['comparison_analysis'])
                        
                        st.divider()
                        email_draft = watchdog.draft_legal_email(res['comparison_analysis'])
                        st.text_area("Draft Email to Legal", value=email_draft, height=200)
                        if st.button("🚀 Send to Legal"):
                            st.toast("Email Dispatched!")