# gov_app.py
import streamlit as st
import os
import datetime

st.set_page_config(page_title="Gov Regulatory Portal", page_icon="🏛️", layout="centered")

st.title("### Government Regulatory Portal")
st.caption("Simulator: Publish new labor laws here.")

# Input Form
with st.form("gov_form"):
    title = st.text_input("Regulation Title", "New Remote Work Mandate 2026")
    effective_date = st.date_input("Effective Date")
    body = st.text_area("Regulation Text", height=300, 
                        value="Effective immediately, all employees are entitled to a 'Right to Disconnect' after 6 PM. Any work communication sent after hours will incur a penalty.")
    
    submitted = st.form_submit_button("## Publish Update")

if submitted:
    # We simulate a "Live Website" by writing a raw HTML file
    html_content = f"""
    <html>
    <body>
        <div id="regulation">
            <h1 class="reg-title">{title}</h1>
            <p class="meta">Published: {datetime.date.today()} | Effective: {effective_date}</p>
            <hr>
            <div class="reg-body">
                {body}
            </div>
        </div>
    </body>
    </html>
    """
    
    # Save to a generic "internet" folder
    os.makedirs("simulated_internet", exist_ok=True)
    with open("simulated_internet/gov_page.html", "w") as f:
        f.write(html_content)
        
    st.success("Regulation Published to 'www.gov-labor-news.com' (Simulated)")
    st.info(f"Content written to: {os.path.abspath('simulated_internet/gov_page.html')}")
