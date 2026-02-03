# modules/watchdog.py
import os
from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage, SystemMessage
from config import Config

class PolicyWatchdog:
    def __init__(self, agent):
        self.agent = agent # We reuse the existing HRAgent instance
        self.target_url = "simulated_internet/gov_page.html" # The mock URL

    def check_for_updates(self):
        """Simulates scraping the government website."""
        if not os.path.exists(self.target_url):
            return {"status": "error", "content": "No website found. Run gov_app.py first."}
        
        # 1. SCRAPE
        with open(self.target_url, "r") as f:
            html = f.read()
            
        soup = BeautifulSoup(html, "html.parser")
        
        try:
            title = soup.find("h1", class_="reg-title").text
            body = soup.find("div", class_="reg-body").text.strip()
            return {"status": "success", "title": title, "body": body}
        except AttributeError:
            return {"status": "error", "content": "Could not parse website structure."}

    def analyze_impact(self, new_regulation_text):
        """
        1. Summarize new law.
        2. RAG Search internal DB for relevant existing policies.
        3. Compare and Diff.
        """
        # A. Summarize & Extract Keywords
        summary_prompt = f"Extract the 3 main keywords from this new law: {new_regulation_text}"
        keywords_res = self.agent.llm.invoke([HumanMessage(content=summary_prompt)])
        keywords = keywords_res.content
        
        # B. RAG Search (FIXED LINE BELOW)
        # We now access the DB through the 'researcher' worker
        # We check if the researcher has a loaded DB first
        if self.agent.researcher.vector_db:
            docs = self.agent.researcher.vector_db.similarity_search(new_regulation_text, k=4)
            current_policy_context = "\n".join([d.page_content for d in docs])
        else:
            current_policy_context = "Internal Policy Database is empty."
        
        if not current_policy_context:
            current_policy_context = "No specific internal policy found on this topic."

        # C. Comparative Analysis
        analysis_prompt = f"""
        You are a Senior Legal Analyst. Compare these two texts.
        
        NEW EXTERNAL REGULATION:
        {new_regulation_text}
        
        OUR CURRENT INTERNAL POLICY:
        {current_policy_context}
        
        Task:
        1. Identify conflicts or gaps.
        2. Create a Markdown table comparing "Current Policy" vs "New Requirement".
        3. Assign a Compliance Risk Score (High/Medium/Low).
        
        Output format: Markdown.
        """
        
        comparison = self.agent.llm.invoke([HumanMessage(content=analysis_prompt)]).content
        
        return {
            "keywords": keywords,
            "internal_context": current_policy_context,
            "comparison_analysis": comparison
        }

    def draft_legal_email(self, analysis_text, recipient="legal@company.com"):
        prompt = f"""
        Draft a formal email to Legal Counsel ({recipient}).
        Subject: URGENT: Policy Update Required - Compliance Gap Identified
        
        Body:
        - Summarize the analysis below.
        - Request approval to update our internal PDFs.
        - Tone: Professional, Direct.
        
        Analysis Data:
        {analysis_text}
        """
        email = self.agent.llm.invoke([HumanMessage(content=prompt)]).content
        return email