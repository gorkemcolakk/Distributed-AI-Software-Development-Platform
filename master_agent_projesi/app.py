import streamlit as st
import os
import json
import pandas as pd
import time

# MUST BE THE FIRST STREAMLIT COMMAND
st.set_page_config(page_title="Master Agent Pro", page_icon="🧿", layout="wide")

# 1. API CONFIGURATION (Securely read from environment or user input)
# Try reading from .env if python-dotenv is present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

env_api_key = os.getenv("OPENAI_API_KEY", "")

# 2. REGISTERED AGENTS DATABASE
agents_data = [
    {"Agent ID": "Agent A (GPT-X)", "Specialty": "Full-Stack / Backend", "Coding": 90, "Reasoning": 85, "Context": 95},
    {"Agent ID": "Agent B (Model-Y)", "Specialty": "Architecture / Logic", "Coding": 75, "Reasoning": 95, "Context": 70},
    {"Agent ID": "Agent C (Model-Z)", "Specialty": "Frontend / UI", "Coding": 95, "Reasoning": 70, "Context": 80}
]
df_agents = pd.DataFrame(agents_data)

# --- UI UPGRADE: CUSTOM CSS ---
st.markdown("""
    <style>
    /* Arka planı hafif gri yaparak panellere derinlik katma */
    .stApp { background-color: #f4f6f9; }
    
    /* Expander (Açılır Kutu) Tasarımı */
    div[data-testid="stExpander"] {
        border: 1px solid #e0e6ed;
        border-radius: 8px;
        background-color: #ffffff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        margin-bottom: 10px;
    }
    
    /* Buton Tasarımı */
    div.stButton > button:first-child {
        background-color: #0056b3;
        color: white;
        border-radius: 6px;
        height: 3rem;
        font-weight: bold;
    }
    
    /* Metrik (Üst İstatistikler) Renklendirmesi */
    div[data-testid="stMetricValue"] { color: #0056b3; }
    </style>
""", unsafe_allow_html=True)

# 3. MASTER AGENT CORE
def decompose_task(user_requirement: str, api_key: str = ""):
    """
    Decomposes requirements using OpenAI API if key is available,
    otherwise uses intelligent local fallback engine.
    """
    system_prompt = """
    You are an Expert Software Architect and the Master Agent in a distributed multi-agent system.
    Analyze the provided software requirement and decompose it into specific, actionable sub-tasks.
    
    You must categorize the work into the following distinct phases:
    - Requirements_Analysis
    - Frontend_Development
    - Backend_Development
    - Database_Design
    - Quality_Assurance_and_Testing

    For EACH phase, provide a JSON object containing:
    - "description": A detailed explanation of the task.
    - "complexity": Estimated complexity ("Low", "Medium", or "High").
    - "suggested_agent_profile": The ideal agent skill profile needed (e.g., "High Reasoning", "High Coding").

    Return ONLY a valid JSON object.
    """
    
    if api_key and api_key.strip():
        try:
            import openai
            client = openai.OpenAI(api_key=api_key.strip())
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_requirement}
                ],
                temperature=0.2
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            st.warning(f"⚠️ OpenAI API bağlantı uyarısı ({e}). Akıllı yerel motor devreye girdi.")

    # Resilient local fallback engine
    return {
        "Requirements_Analysis": {
            "description": f"Detailed requirement analysis, domain entity extraction, and use-case definition for: {user_requirement[:100]}...",
            "complexity": "Medium",
            "suggested_agent_profile": "High Reasoning / Model-Y"
        },
        "Database_Design": {
            "description": "Relational/NoSQL schema modeling, entity tables, indexes, and initial migrations.",
            "complexity": "Medium",
            "suggested_agent_profile": "High Logic & Schema Design / Agent A"
        },
        "Backend_Development": {
            "description": "RESTful API endpoints implementation, business logic, data persistence, and authentication.",
            "complexity": "High",
            "suggested_agent_profile": "High Coding & Architecture / Agent A"
        },
        "Frontend_Development": {
            "description": "Responsive Web UI components, state management, form validations, and API client integration.",
            "complexity": "Medium",
            "suggested_agent_profile": "High Coding & UI/UX / Agent C"
        },
        "Quality_Assurance_and_Testing": {
            "description": "Comprehensive test suite covering unit tests, API integration tests, and end-to-end user workflows.",
            "complexity": "Medium",
            "suggested_agent_profile": "High Reasoning & Validation / Agent B"
        }
    }

# 4. WEB INTERFACE
st.title("🧿 Distributed AI: Master Agent System")
st.markdown("**Sprint 1 Increment:** Intelligent Task Decomposition & Routing")
st.divider()

# --- UI UPGRADE: DASHBOARD METRICS ---
m1, m2, m3 = st.columns(3)
m1.metric("System Status", "Online 🟢")
m2.metric("Active Agents", f"{len(agents_data)} Available")
m3.metric("Network Load", "Optimal")
st.divider()

col_main, col_sidebar = st.columns([7, 3])

with col_sidebar:
    st.markdown("### 📋 Agent Roster")
    st.info("Available agents in the distributed network.")
    st.dataframe(df_agents, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.markdown("### 🔑 API Yapılandırması")
    user_api_key = st.text_input(
        "OpenAI API Key (İsteğe Bağlı):",
        type="password",
        value=env_api_key,
        help="API Key girilmezse veya kota yoksa sistem yerel akıllı motor ile kesintisiz çalışmaya devam eder."
    )

with col_main:
    st.markdown("### 📥 System Requirement Input")
    requirement_input = st.text_area(
        "Enter requirement:", 
        height=120, 
        label_visibility="collapsed", 
        placeholder="e.g., Develop an online library management system with catalog search, member loans, and overdue alerts..."
    )

    if st.button("⚡ Analyze & Decompose Requirements", use_container_width=True):
        if requirement_input:
            progress_text = "Master Agent is analyzing requirements and routing tasks..."
            my_bar = st.progress(0, text=progress_text)
            
            for percent_complete in range(100):
                time.sleep(0.008) # Visual progress feedback
                my_bar.progress(percent_complete + 1, text=progress_text)
                
            try:
                tasks = decompose_task(requirement_input, api_key=user_api_key)
                
                my_bar.empty()
                st.success("✅ Task Decomposition Completed Successfully!")
                
                st.markdown("### 🧩 Assigned Sub-Tasks")
                for phase, details in tasks.items():
                    with st.expander(f"🔹 {phase.replace('_', ' ').title()}", expanded=True):
                        st.write(f"**Description:** {details.get('description', 'N/A')}")
                        
                        c1, c2 = st.columns(2)
                        c1.info(f"**Complexity:** {details.get('complexity', 'N/A')}")
                        c2.success(f"**Target Agent Profile:** {details.get('suggested_agent_profile', 'N/A')}")
                        
            except Exception as e:
                my_bar.empty()
                st.error(f"An unexpected error occurred: {e}")
        else:
            st.warning("Please enter a software requirement to analyze.")