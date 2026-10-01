import streamlit as st
import openai
import json
import pandas as pd
import time

# 1. API CONFIGURATION
openai.api_key = "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" 

# 2. REGISTERED AGENTS DATABASE
agents_data = [
    {"Agent ID": "Agent A (GPT-X)", "Specialty": "Full-Stack / Backend", "Coding": 90, "Reasoning": 85, "Context": 95},
    {"Agent ID": "Agent B (Model-Y)", "Specialty": "Architecture / Logic", "Coding": 75, "Reasoning": 95, "Context": 70},
    {"Agent ID": "Agent C (Model-Z)", "Specialty": "Frontend / UI", "Coding": 95, "Reasoning": 70, "Context": 80}
]
df_agents = pd.DataFrame(agents_data)

# MUST BE THE FIRST STREAMLIT COMMAND
st.set_page_config(page_title="Master Agent Pro", page_icon="🧿", layout="wide")

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
def decompose_task(user_requirement):
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
    
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_requirement}
        ],
        temperature=0.2
    )
    
    return response.choices[0].message.content

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

with col_main:
    st.markdown("### 📥 System Requirement Input")
    requirement_input = st.text_area(
        "Enter requirement:", 
        height=120, 
        label_visibility="collapsed", 
        placeholder="e.g., Develop an online library management system..."
    )

    if st.button("⚡ Analyze & Decompose Requirements", use_container_width=True):
        if requirement_input:
            # --- UI UPGRADE: ANIMATED PROGRESS BAR ---
            progress_text = "Master Agent is analyzing requirements and routing tasks..."
            my_bar = st.progress(0, text=progress_text)
            
            for percent_complete in range(100):
                time.sleep(0.01) # Fake loading animation for better UX
                my_bar.progress(percent_complete + 1, text=progress_text)
                
            try:
                raw_result = decompose_task(requirement_input)
                tasks = json.loads(raw_result)
                
                my_bar.empty()
                st.success("✅ Task Decomposition Completed Successfully!")
                
                st.markdown("### 🧩 Assigned Sub-Tasks")
                for phase, details in tasks.items():
                    # Görev kutularını varsayılan olarak açık getirme
                    with st.expander(f"🔹 {phase.replace('_', ' ').title()}", expanded=True):
                        st.write(f"**Description:** {details.get('description', 'N/A')}")
                        
                        # İç detayları renkli info/success kutularına alma
                        c1, c2 = st.columns(2)
                        c1.info(f"**Complexity:** {details.get('complexity', 'N/A')}")
                        c2.success(f"**Target Agent Profile:** {details.get('suggested_agent_profile', 'N/A')}")
                        
            except Exception as e:
                my_bar.empty()
                st.error(f"An unexpected error occurred: {e}")
        else:
            st.warning("Please enter a software requirement to analyze.")

with col_sidebar:
    st.markdown("### 📋 Agent Roster")
    st.info("Available agents in the distributed network[cite: 3].")
    st.dataframe(df_agents, use_container_width=True, hide_index=True)