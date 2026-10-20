import os
import json
import time
import html
import urllib.request
import re
import streamlit as st
import pandas as pd
import streamlit.components.v1 as components

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(dotenv_path=_env_path)
except ImportError:
    pass

# ==========================================
# 1. LOCAL OLLAMA CONFIGURATION (Yerel & Özel)
# ==========================================
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))

def call_local_ollama(prompt: str, model: str = OLLAMA_MODEL, host: str = OLLAMA_HOST, timeout: int = OLLAMA_TIMEOUT) -> str:
    """Yerel Ollama sunucusuna HTTP isteği gönderir ve yanıtı döndürür."""
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "seed": 42}
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("response", "")

# ==========================================
# 2. AGENTS DATABASE (5 Model & Uzman Ajanımız)
# ==========================================
agents_data = [
    {
        "Agent ID": "Integration Agent (Phi-4 Mini 3.8B)",
        "short_name": "Phi-4 Mini 3.8B",
        "Role": "Integration & Review",
        "Specialty": "Integration",
        "Member": "Elif Yılmaz",
        "badge": "INT",
        "Model": "Phi-4 Mini 3.8B",
        "Coding": 78,
        "Reasoning": 95,
        "Context": 90,
        "color": "#38BDF8"
    },
    {
        "Agent ID": "Frontend Agent (Qwen2.5-Coder 3B)",
        "short_name": "Qwen-Coder 3B",
        "Role": "Frontend UI/UX",
        "Specialty": "Frontend",
        "Member": "Kübra Hepcan",
        "badge": "FE",
        "Model": "Qwen2.5-Coder 3B",
        "Coding": 95,
        "Reasoning": 78,
        "Context": 85,
        "color": "#FBBF24"
    },
    {
        "Agent ID": "Backend Agent (Qwen2.5-Coder 7B)",
        "short_name": "Qwen-Coder 7B",
        "Role": "Backend & API",
        "Specialty": "Backend",
        "Member": "İrem Yılmaz",
        "badge": "BE",
        "Model": "Qwen2.5-Coder 7B",
        "Coding": 96,
        "Reasoning": 88,
        "Context": 84,
        "color": "#A78BFA"
    },
    {
        "Agent ID": "Database Agent (Llama 3.2 3B)",
        "short_name": "Llama 3.2 3B",
        "Role": "Database & Schema",
        "Specialty": "Database",
        "Member": "Mahmut Karaalioğlu",
        "badge": "DB",
        "Model": "Llama 3.2 3B",
        "Coding": 78,
        "Reasoning": 82,
        "Context": 95,
        "color": "#34D399"
    },
    {
        "Agent ID": "Testing Agent (DeepSeek-Coder 6.7B)",
        "short_name": "DeepSeek 6.7B",
        "Role": "Testing & QA",
        "Specialty": "Testing",
        "Member": "Berat İnan",
        "badge": "QA",
        "Model": "DeepSeek-Coder 6.7B",
        "Coding": 88,
        "Reasoning": 95,
        "Context": 82,
        "color": "#F87171"
    },
]

PHASE_ICONS = {
    "Requirements_Analysis": "📋",
    "Frontend_Development": "🎨",
    "Backend_Development": "⚙️",
    "Database_Design": "🗄️",
    "Quality_Assurance_and_Testing": "🧪",
}
COMPLEXITY_COLORS = {"High": "#F87171", "Medium": "#FBBF24", "Low": "#34D399"}

st.set_page_config(page_title="Nexus | AI Command Center", page_icon="🧿", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 3. TASARIM (CSS)
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&display=swap');

    html, body, .stApp { font-family: 'Inter', 'Segoe UI', sans-serif; }
    .stApp { background-color: #0B0F19; color: #E5E7EB; }
    /* Kayan ızgara */
    .stApp::before { content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
        background-image: linear-gradient(rgba(79,172,254,.07) 1px, transparent 1px), linear-gradient(90deg, rgba(79,172,254,.07) 1px, transparent 1px);
        background-size: 52px 52px; animation: gridmove 16s linear infinite;
        -webkit-mask-image: radial-gradient(ellipse at 50% 25%, #000 15%, transparent 75%); mask-image: radial-gradient(ellipse at 50% 25%, #000 15%, transparent 75%); }
    /* Süzülen ışık küreleri */
    .stApp::after { content: ""; position: fixed; inset: -20%; z-index: 0; pointer-events: none;
        background: radial-gradient(38vmax 38vmax at 22% 25%, rgba(0,242,254,.14), transparent 70%),
                    radial-gradient(34vmax 34vmax at 78% 68%, rgba(167,139,250,.14), transparent 70%),
                    radial-gradient(26vmax 26vmax at 60% 15%, rgba(251,191,36,.07), transparent 70%);
        animation: drift 22s ease-in-out infinite alternate; }
    #MainMenu, footer { visibility: hidden; height: 0; }
    header[data-testid="stHeader"] { background: transparent !important; z-index: 99999 !important; }
    .stDeployButton, [data-testid="stAppDeployButton"], [data-testid="stToolbarActions"] { display: none !important; }
    button[data-testid="stSidebarCollapseButton"], button[data-testid="collapsedControl"], [data-testid="stSidebarHeader"] button {
        display: flex !important; visibility: visible !important; color: #4FACFE !important; background: #121828 !important; border: 1px solid #1F2937 !important; border-radius: 8px !important;
    }
    .block-container { padding-top: 2rem; max-width: 1200px; }

    section[data-testid="stSidebar"] { background-color: #0A0E17; border-right: 1px solid #1F2937; }

    .main-header { font-size: 2.8rem; font-weight: 800; letter-spacing: -0.02em;
        background: linear-gradient(45deg, #00F2FE, #4FACFE); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.2rem; }
    .sub-header { color: #8B949E; font-size: 1.05rem; margin-bottom: 1.8rem; }
    .section-title { font-size: 1.15rem; font-weight: 600; color: #F3F4F6; margin: 1.6rem 0 0.8rem 0; }

    div[data-testid="stMetric"] { background-color: #121828; border: 1px solid #1F2937; border-radius: 12px; padding: 16px 20px; }
    div[data-testid="stMetricValue"] { color: #4FACFE; font-weight: 700; font-size: 1.45rem !important; overflow: visible !important; white-space: nowrap !important; }
    div[data-testid="stMetricValue"] > div { overflow: visible !important; text-overflow: clip !important; white-space: nowrap !important; }

    div.stButton > button:first-child { background: linear-gradient(90deg, #0052D4, #4364F7 55%, #6FB1FC); color: white; border: none;
        border-radius: 10px; height: 3.2rem; font-size: 1.05rem; font-weight: 600; transition: transform .2s, box-shadow .2s; }
    div.stButton > button:first-child:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(67,100,247,.5); }

    .stTextArea textarea { background-color: #121828 !important; color: #FFFFFF !important; border: 1px solid #2A3550 !important; border-radius: 10px !important; }
    .stTextArea textarea:focus { border-color: #4FACFE !important; box-shadow: 0 0 0 1px #4FACFE !important; }

    /* Ajan kartları (sidebar) */
    .agent-card { background: #121828; border: 1px solid #1F2937; border-left: 4px solid var(--c); border-radius: 10px; padding: 14px; margin-bottom: 14px; }
    .agent-name { color: var(--c); font-weight: 800; font-size: 1.05em; }
    .agent-spec { color: #9CA3AF; font-size: .85em; margin: 2px 0 10px 0; }
    .bar-row { display: flex; align-items: center; gap: 8px; margin-top: 6px; font-size: .8em; color: #CBD5E1; }
    .bar-label { width: 70px; }
    .bar-track { flex: 1; height: 6px; background: #1F2937; border-radius: 4px; overflow: hidden; }
    .bar-fill { height: 100%; background: var(--c); border-radius: 4px; }
    .bar-val { width: 24px; text-align: right; font-weight: 600; }

    /* Görev kartları: sol şerit = atanan ajanın rengi */
    .task-card { background: #121828; border: 1px solid #1F2937; border-left: 5px solid var(--c); border-radius: 12px; padding: 20px 22px; margin-bottom: 16px; }
    .task-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
    .task-title { font-size: 1.15rem; font-weight: 700; color: #F9FAFB; }
    .task-desc { color: #B6BFCC; font-size: .95rem; line-height: 1.65; margin: 12px 0 16px 0; max-width: 75ch; }
    .task-foot { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; border-top: 1px solid #1F2937; padding-top: 14px; }
    .chip { padding: 4px 10px; border-radius: 6px; font-size: .85em; font-weight: 600; background: rgba(99,102,241,.18); color: #A5B4FC; }
    .chip-cx { background: color-mix(in srgb, var(--c) 18%, transparent); color: var(--c); }
    .assign { margin-left: auto; padding: 6px 12px; border-radius: 8px; font-weight: 700; font-size: .92em;
        color: var(--c); border: 1px solid var(--c); background: color-mix(in srgb, var(--c) 10%, transparent); }
    .assign small { color: #9CA3AF; font-weight: 500; margin-left: 6px; }

    /* Yük dağılımı */
    .load-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
    .load-name { width: 150px; color: #E5E7EB; font-weight: 600; font-size: .9em; }
    .load-track { flex: 1; height: 10px; background: #1F2937; border-radius: 6px; overflow: hidden; }
    .load-fill { height: 100%; background: var(--c); border-radius: 6px; }
    .load-pts { width: 70px; text-align: right; color: #CBD5E1; font-size: .9em; }

    .prog { height: 4px; background: #1F2937; border-radius: 3px; margin-top: 12px; overflow: hidden; }
    .prog div { height: 100%; border-radius: 3px; transition: width .4s; }
    [class*="st-key-adv_"] button { height: 2.4rem !important; font-size: .95rem !important; }
    div[data-baseweb="select"] > div { background-color: #121828 !important; border-color: #2A3550 !important; }

    .title-row { display: flex; align-items: center; gap: 14px; }
    .title-row .emo { font-size: 2.4rem; line-height: 1; }

    /* Hareket */
    @keyframes gridmove { to { background-position: 52px 52px; } }
    @keyframes drift { from { transform: translate3d(-3%, -2%, 0) rotate(0deg); } to { transform: translate3d(4%, 3%, 0) rotate(8deg); } }
    @keyframes shine { to { background-position: 200% center; } }
    @keyframes rise { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: none; } }
    @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: .35; } }
    .main-header { background: linear-gradient(90deg, #00F2FE, #4FACFE, #A78BFA, #00F2FE) !important; background-size: 200% auto !important;
        -webkit-background-clip: text !important; animation: shine 9s linear infinite; }
    .task-card.fresh { animation: rise .6s cubic-bezier(.2,.8,.2,1) both; }
    .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--c); margin-right: 8px; box-shadow: 0 0 8px var(--c); animation: blink 2.2s ease-in-out infinite; }
    div[data-testid="stMetric"] { transition: border-color .25s, box-shadow .25s; }
    div[data-testid="stMetric"]:hover { border-color: #4FACFE; box-shadow: 0 0 20px rgba(79,172,254,.25); }
    @media (prefers-reduced-motion: reduce) { .stApp::before, .stApp::after, .main-header, .task-card, .dot { animation: none !important; } }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 4. YARDIMCI FONKSİYONLAR & FITSCORE ALGORİTMASI
# ==========================================
PHASE_WEIGHTS = {
    "Requirements_Analysis": {"Reasoning": 0.60, "Context": 0.30, "Coding": 0.10, "specialty": "Integration"},
    "Frontend_Development":  {"Coding": 0.55, "Context": 0.25, "Reasoning": 0.20, "specialty": "Frontend"},
    "Backend_Development":   {"Coding": 0.50, "Reasoning": 0.35, "Context": 0.15, "specialty": "Backend"},
    "Database_Design":      {"Context": 0.55, "Reasoning": 0.30, "Coding": 0.15, "specialty": "Database"},
    "Quality_Assurance_and_Testing": {"Reasoning": 0.45, "Coding": 0.40, "Context": 0.15, "specialty": "Testing"}
}

def assign_best_agent(phase_or_skill: str = "Requirements_Analysis", primary_skill: str = None, current_load: dict = None):
    """
    Sprint 2 Yetenek Değerlendirme & FitScore Algoritması:
    Görev türüne göre yetenek ağırlıkları (Coding, Reasoning, Context) ve uzmanlık eşleşmesiyle en uygun ajanı seçer.
    """
    if phase_or_skill in PHASE_WEIGHTS:
        weights = PHASE_WEIGHTS[phase_or_skill]
    else:
        skill = str(primary_skill or phase_or_skill).capitalize()
        if skill == "Coding":
            weights = {"Coding": 0.70, "Reasoning": 0.20, "Context": 0.10, "specialty": ""}
        elif skill == "Context":
            weights = {"Context": 0.70, "Reasoning": 0.20, "Coding": 0.10, "specialty": ""}
        else:
            weights = {"Reasoning": 0.70, "Coding": 0.20, "Context": 0.10, "specialty": ""}

    best_agent = None
    best_score = -1.0
    dominant_skill = max(["Coding", "Reasoning", "Context"], key=lambda s: weights.get(s, 0))

    for a in agents_data:
        # Ağırlıklı Yetenek Uygunluk Skoru (FitScore: 0 - 100)
        score = (
            a["Coding"] * weights.get("Coding", 0) +
            a["Reasoning"] * weights.get("Reasoning", 0) +
            a["Context"] * weights.get("Context", 0)
        )
        # Uzmanlık Bonusu (+5 puan)
        spec = weights.get("specialty", "")
        if spec and spec.lower() in a["Specialty"].lower():
            score = min(100.0, score + 5.0)

        # Yük dengeleme (Load Balancing) cezası
        if current_load and a["Agent ID"] in current_load:
            load_pts = current_load[a["Agent ID"]]
            score = max(0.0, score - (load_pts * 0.8))

        if score > best_score:
            best_score = score
            best_agent = a

    if not best_agent:
        best_agent = agents_data[0]

    return best_agent, dominant_skill, round(best_score, 1)

def get_fallback_json(requirement=""):
    """Demo modu: sabit şablon, ama girdiye göre konu ve puanlar değişir."""
    topic = " ".join(requirement.split())[:120] or "verilen gereksinim"
    big = len(requirement) > 200
    data = {
        "Requirements_Analysis": {
            "description": f"\"{topic}\" gereksiniminin ana modülleri, kullanıcı rolleri ve teknik kısıtları çıkarılmalıdır. Kabul kriterleri yazılmalı ve öncelikli kullanıcı hikayeleri belirlenmelidir. Bu aşamada temel teknolojiler ve veri akışı taslak olarak dokümante edilmelidir.",
            "complexity": "Medium", "primary_skill_required": "Reasoning", "story_points": 3},
        "Frontend_Development": {
            "description": "Duyarlı ve erişilebilir kullanıcı arayüzü bileşen tabanlı bir mimariyle kodlanmalıdır. API istekleri için servis katmanı kurulmalı, form doğrulama ve hata yönetimi eklenmelidir. Arayüz farklı ekran boyutlarında test edilmelidir.",
            "complexity": "Medium", "primary_skill_required": "Coding", "story_points": 5},
        "Backend_Development": {
            "description": "İş mantığı, kimlik doğrulama ve RESTful API uç noktaları geliştirilmelidir. Veritabanı bağlantıları ORM ile yapılandırılmalı ve dış servis entegrasyonları sağlanmalıdır. Yoğun trafik için önbellekleme ve loglama düşünülmelidir.",
            "complexity": "High", "primary_skill_required": "Coding", "story_points": 8},
        "Database_Design": {
            "description": "Varlıklar ve ilişkiler belirlenerek normalize edilmiş bir şema tasarlanmalıdır. Sık kullanılan sorgular için indeksler tanımlanmalı, yedekleme ve geçiş (migration) stratejisi planlanmalıdır. Örnek veriyle şema doğrulanmalıdır.",
            "complexity": "Medium", "primary_skill_required": "Context", "story_points": 5 if big else 3},
        "Quality_Assurance_and_Testing": {
            "description": "Birim, entegrasyon ve uçtan uca test senaryoları yazılmalıdır. Kritik akışlar için otomatik test hattı kurulmalı ve hata raporları takip edilmelidir. Yayın öncesi performans ve güvenlik kontrolleri yapılmalıdır.",
            "complexity": "Low", "primary_skill_required": "Reasoning", "story_points": 3 if big else 2},
    }
    return json.dumps(data, ensure_ascii=False)

def decompose_task(user_requirement):
    """(json_metni, demo_modu_mu) döndürür."""
    system_prompt = """
    You are an Expert Software Architect and the Master Agent in a distributed multi-agent system.
    Analyze the provided software requirement and decompose it into the following 5 specific sub-tasks:
    - Requirements_Analysis
    - Frontend_Development
    - Backend_Development
    - Database_Design
    - Quality_Assurance_and_Testing

    CRITICAL: You MUST respond with ONLY a valid JSON object matching this exact schema:
    {
      "Requirements_Analysis": {
        "description": "Detailed explanation of requirements and architecture.",
        "complexity": "Medium",
        "primary_skill_required": "Reasoning",
        "story_points": 3
      },
      "Frontend_Development": {
        "description": "Detailed explanation of UI layout and components.",
        "complexity": "Medium",
        "primary_skill_required": "Coding",
        "story_points": 5
      },
      "Backend_Development": {
        "description": "Detailed explanation of REST APIs and business logic.",
        "complexity": "High",
        "primary_skill_required": "Coding",
        "story_points": 8
      },
      "Database_Design": {
        "description": "Detailed explanation of SQL schema and relationships.",
        "complexity": "Medium",
        "primary_skill_required": "Context",
        "story_points": 5
      },
      "Quality_Assurance_and_Testing": {
        "description": "Detailed explanation of unit and integration test suites.",
        "complexity": "Low",
        "primary_skill_required": "Reasoning",
        "story_points": 3
      }
    }
    Do not add extra keys or markdown outside the JSON.
    """
    try:
        prompt = f"{system_prompt}\n\nUser Requirement:\n{user_requirement}\n\nJSON output:"
        raw_response = call_local_ollama(prompt, model=OLLAMA_MODEL)
        
        # JSON bloğunu temizle ve ayıkla
        match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        if match:
            text = match.group(0).strip()
        else:
            text = raw_response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            
        # JSON geçerliliğini doğrula
        json.loads(text)
        st.toast("Yerel Qwen 2.5 (3B) modeli görevi başarıyla ayrıştırdı! 🚀", icon="🧠")
        return text, False
    except Exception:
        st.toast("Yerel Ollama çevrimdışı. Güvenli yedek demo modu devrede.", icon="🛡️")
        return get_fallback_json(user_requirement), True

def normalize_tasks(parsed_data, requirement=""):
    """Model ne tür bir JSON dönerse dönsün, UI'ın beklediği 5 aşamalı standart formata dönüştürür."""
    standard_phases = [
        "Requirements_Analysis",
        "Frontend_Development",
        "Backend_Development",
        "Database_Design",
        "Quality_Assurance_and_Testing"
    ]
    fallback_dict = json.loads(get_fallback_json(requirement))
    if not isinstance(parsed_data, dict):
        return fallback_dict

    # Model tek bir sarmalayıcı anahtar kullandıysa aç
    for wrap_key in ["tasks", "phases", "subtasks", "decomposition", "Requirement_Decomposition", "sub_tasks", "requirement"]:
        if wrap_key in parsed_data and isinstance(parsed_data[wrap_key], dict):
            # Eğer alt sözlük standart aşamalardan en az birini içeriyorsa veya sözlükse
            sub = parsed_data[wrap_key]
            if any(k in sub for k in standard_phases) or not any(k in parsed_data for k in standard_phases):
                parsed_data = sub
                break

    def clean_key(k):
        return re.sub(r"[^a-zA-Z0-9]", "", str(k).lower())

    lookup = {clean_key(k): (k, v) for k, v in parsed_data.items()}

    default_skills = {
        "Requirements_Analysis": "Reasoning",
        "Frontend_Development": "Coding",
        "Backend_Development": "Coding",
        "Database_Design": "Context",
        "Quality_Assurance_and_Testing": "Reasoning"
    }

    result = {}
    for phase in standard_phases:
        fb = fallback_dict.get(phase, {})
        val = None
        if phase in parsed_data:
            val = parsed_data[phase]
        else:
            c_phase = clean_key(phase)
            for lk_k, (orig_k, orig_v) in lookup.items():
                if c_phase in lk_k or lk_k in c_phase:
                    val = orig_v
                    break

        if isinstance(val, dict):
            skill = str(val.get("primary_skill_required", fb.get("primary_skill_required", default_skills[phase]))).capitalize()
            if skill not in ["Coding", "Reasoning", "Context"]:
                skill = default_skills[phase]
            try:
                pts = int(val.get("story_points", fb.get("story_points", 3)))
            except (ValueError, TypeError):
                pts = fb.get("story_points", 3)

            result[phase] = {
                "description": str(val.get("description", fb.get("description", ""))),
                "complexity": str(val.get("complexity", fb.get("complexity", "Medium"))),
                "primary_skill_required": skill,
                "story_points": pts
            }
        elif isinstance(val, str) and val.strip():
            result[phase] = {
                "description": val.strip(),
                "complexity": fb.get("complexity", "Medium"),
                "primary_skill_required": default_skills[phase],
                "story_points": fb.get("story_points", 3)
            }
        elif isinstance(val, list) and val:
            desc = "; ".join(str(item) for item in val if item)
            result[phase] = {
                "description": desc or fb.get("description", ""),
                "complexity": fb.get("complexity", "Medium"),
                "primary_skill_required": default_skills[phase],
                "story_points": fb.get("story_points", 3)
            }
        else:
            result[phase] = fb
    return result


def network_html(load=None):
    """Master -> 5 Model/Ajan bağlantılarını gösteren canlı SVG. load verilirse çizgi kalınlığı ve akış hızı iş yüküne göre değişir."""
    # 5 model için 800px genişlik üzerinde simetrik ve dengeli konumlar
    pos = [(90, 225), (245, 225), (400, 225), (555, 225), (710, 225)]
    peak = max(load.values()) if load and max(load.values()) else 1
    out = []
    for i, a in enumerate(agents_data):
        x, y = pos[i]
        c = a["color"]
        pts = load.get(a["Agent ID"], 0) if load else 0
        ratio = pts / peak
        width = 1.5 + ratio * 3.5
        dur = 2.4 - ratio * 1.3 if load else 4.5
        n = 3 if pts else 1
        out.append(f'<path id="p{i}" d="M400,72 C400,150 {x},140 {x},{y-30}" fill="none" stroke="{c}" stroke-opacity=".4" stroke-width="{width}" stroke-dasharray="6 6" class="flow"/>')
        for k in range(n):
            out.append(f'<circle r="4.5" fill="{c}"><animateMotion dur="{dur}s" begin="{k * dur / n}s" repeatCount="indefinite"><mpath href="#p{i}"/></animateMotion></circle>')
        sub = f"{pts} puan" if load else a["Role"]
        badge = a.get("badge", str(i+2))
        model_label = a["short_name"]
        out.append(
            f'<circle cx="{x}" cy="{y}" r="26" fill="#121828" stroke="{c}" stroke-width="2"/>'
            f'<circle cx="{x}" cy="{y}" r="26" fill="none" stroke="{c}" class="ring"/>'
            f'<text x="{x}" y="{y+5}" text-anchor="middle" fill="{c}" font-size="12" font-weight="800">{badge}</text>'
            f'<text x="{x}" y="{y+48}" text-anchor="middle" fill="#E5E7EB" font-size="12" font-weight="600">{model_label}</text>'
            f'<text x="{x}" y="{y+64}" text-anchor="middle" fill="#9CA3AF" font-size="11">{sub}</text>')
    out.append('<circle cx="400" cy="42" r="30" fill="#121828" stroke="#818CF8" stroke-width="2.5"/>'
               '<circle cx="400" cy="42" r="30" fill="none" stroke="#818CF8" class="ring"/>'
               '<text x="400" y="47" text-anchor="middle" fill="#818CF8" font-size="13" font-weight="800">MASTER</text>'
               '<text x="400" y="86" text-anchor="middle" fill="#E5E7EB" font-size="13" font-weight="600">Qwen 2.5 (3B)</text>'
               '<text x="400" y="102" text-anchor="middle" fill="#9CA3AF" font-size="11">Master Agent / Nexus Core</text>')
    style = ("<style>body{margin:0;background:transparent;font-family:Inter,'Segoe UI',sans-serif}"
             ".flow{animation:dash 1.1s linear infinite}@keyframes dash{to{stroke-dashoffset:-12}}"
             ".ring{transform-box:fill-box;transform-origin:center;animation:pulse 2.6s ease-out infinite}"
             "@keyframes pulse{from{transform:scale(1);opacity:.8}to{transform:scale(1.7);opacity:0}}"
             "@media (prefers-reduced-motion:reduce){.flow,.ring{animation:none}}</style>")
    return style + '<svg viewBox="0 0 800 320" width="100%" style="max-width:780px;display:block;margin:0 auto" xmlns="http://www.w3.org/2000/svg">' + "".join(out) + "</svg>"

def skill_bar(label, value):
    return (f'<div class="bar-row"><span class="bar-label">{label}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{value}%"></div></div>'
            f'<span class="bar-val">{value}</span></div>')

AUTO = "Otomatik (algoritma önerisi)"
STATUS_STYLE = {"Beklemede": ("#9CA3AF", 0), "Çalışıyor": ("#FBBF24", 50), "Tamamlandı": ("#34D399", 100)}
NEXT_STATUS = {"Beklemede": "Çalışıyor", "Çalışıyor": "Tamamlandı", "Tamamlandı": "Beklemede"}
BTN_LABEL = {"Beklemede": "▶ Başlat", "Çalışıyor": "✔ Tamamla", "Tamamlandı": "↺ Sıfırla"}

def pts_of(d):
    if not isinstance(d, dict):
        return 3
    try:
        return int(d.get("story_points", 3))
    except (TypeError, ValueError):
        return 3

def resolve(phase, details):
    """(atanan ajan, yetenek, ajanın fit skoru, algoritmanın önerdiği ajan). Kullanıcı seçimi öneriyi geçersiz kılar."""
    if not isinstance(details, dict):
        details = {}
    best, skill, score = assign_best_agent(phase, details.get("primary_skill_required", "Reasoning"))
    ov = st.session_state.get(f"ov_{phase}", AUTO)
    agent = next((a for a in agents_data if a["Agent ID"] == ov), best)
    if agent["Agent ID"] != best["Agent ID"]:
        weights = PHASE_WEIGHTS.get(phase, {"Reasoning": 0.5, "Coding": 0.3, "Context": 0.2})
        user_score = (
            agent["Coding"] * weights.get("Coding", 0) +
            agent["Reasoning"] * weights.get("Reasoning", 0) +
            agent["Context"] * weights.get("Context", 0)
        )
        score = round(user_score, 1)
    return agent, skill, score, best

def advance(phase):
    ss = st.session_state
    cur = ss.status[phase]
    ss.status[phase] = NEXT_STATUS[cur]
    if ss.status[phase] == "Tamamlandı":
        ss.done_order.append(phase)
    elif cur == "Tamamlandı" and phase in ss.done_order:
        ss.done_order.remove(phase)

def task_card(phase, details, idx, agent, skill, score, best, status, fresh):
    if not isinstance(details, dict):
        details = {}
    complexity = details.get("complexity", "Medium")
    sc, pct = STATUS_STYLE[status]
    cx_color = COMPLEXITY_COLORS.get(complexity, "#FBBF24")
    title = phase.replace("_", " ").title()
    desc = html.escape(str(details.get("description", "N/A")))
    manual = agent["Agent ID"] != best["Agent ID"]
    manual_chip = (f'<span class="chip">✋ Elle atandı (önerilen: {html.escape(best["Agent ID"])})</span>' if manual else "")
    cls = "task-card fresh" if fresh else "task-card"
    return (
        f'<div class="{cls}" style="--c:{agent["color"]}; animation-delay:{idx * 0.15}s">'
        f'<div class="task-head"><span class="task-title">{PHASE_ICONS.get(phase, "🔹")} {title}</span>'
        f'<span><span class="chip chip-cx" style="--c:{sc}">● {status}</span> '
        f'<span class="chip">🎯 {pts_of(details)} puan</span></span></div>'
        f'<div class="prog"><div style="width:{pct}%;background:{sc}"></div></div>'
        f'<div class="task-desc">{desc}</div>'
        f'<div class="task-foot">'
        f'<span class="chip chip-cx" style="--c:{cx_color}">Zorluk: {complexity}</span>'
        f'<span class="chip">Gereken yetenek: {skill}</span>{manual_chip}'
        f'<span class="assign">🤖 {agent["Agent ID"]}<small>FitScore: {score}</small></span>'
        f'</div></div>'
    )

def build_log(req, tasks, demo):
    lines = [("MASTER", f"Gereksinim alındı ({len(req)} karakter)"),
             ("MASTER", "Demo verisi kullanılıyor (yedek mod)" if demo else "Yerel Qwen 2.5 modeli ile görev ayrıştırma tamamlandı"),
             ("MASTER", f"{len(tasks)} alt görev FitScore algoritmasıyla yönlendirildi")]
    for ph, d in tasks.items():
        if not isinstance(d, dict):
            d = {"primary_skill_required": "Reasoning"}
        ag, sk, sc = assign_best_agent(ph, d.get("primary_skill_required", "Reasoning"))
        lines.append(("ROUTER", f"{ph.replace('_', ' ')} → {ag['Agent ID']} (FitScore: {sc})"))
    lines.append(("SYSTEM", f"Dağıtım hazır: {sum(pts_of(d) for d in tasks.values())} story point"))
    return lines

def terminal_html(lines, animate):
    colors = {"MASTER": "#4FACFE", "ROUTER": "#A78BFA", "SYSTEM": "#34D399"}
    rows = "".join(
        f'<div class="ln" style="animation-delay:{(k * 0.6) if animate else 0}s">'
        f'<span style="color:{colors.get(tag, "#9CA3AF")}">[{tag}]</span> {html.escape(msg)}</div>'
        for k, (tag, msg) in enumerate(lines))
    style = ("<style>body{margin:0;background:transparent}"
             ".t{background:#0A0E17;border:1px solid #1F2937;border-radius:12px;padding:14px 18px;"
             "font-family:'JetBrains Mono',Consolas,monospace;font-size:13px;line-height:22px;color:#CBD5E1}"
             + (".ln{white-space:nowrap;overflow:hidden;width:0;animation:type .55s steps(50) forwards}"
                "@keyframes type{to{width:100%}}" if animate else ".ln{white-space:nowrap;overflow:hidden}")
             + ".cur{color:#00F2FE;animation:b 1s steps(2) infinite}@keyframes b{50%{opacity:0}}</style>")
    return style + f'<div class="t">{rows}<div class="cur">▌</div></div>'

def burndown_df(tasks, done_order):
    n, total = len(tasks), sum(pts_of(d) for d in tasks.values())
    ideal = [total * (1 - k / n) for k in range(n + 1)]
    actual, rem = [total], total
    for ph in done_order:
        rem -= pts_of(tasks[ph])
        actual.append(rem)
    actual += [None] * (n + 1 - len(actual))
    return pd.DataFrame({"İdeal": ideal, "Gerçek": actual}, index=pd.Index(range(n + 1), name="Tamamlanan görev"))

# ==========================================
# 5. SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("## 🌐 Nexus Core")
    st.caption("Dağıtık multi-agent orkestrasyon motoru")

    st.markdown("### Master Agent")
    st.markdown(
        f'<div class="agent-card" style="--c:#818CF8;">'
        f'<div class="agent-name"><span class="dot" style="--c:#818CF8"></span>Master Agent (Qwen 2.5 3B)</div>'
        f'<div class="agent-spec">Orkestrasyon & Mimar · <span style="color:#9CA3AF">Üye: Eren Görkem Çolak</span></div>'
        + skill_bar("Coding", 85)
        + skill_bar("Reasoning", 92)
        + skill_bar("Context", 85)
        + '</div>',
        unsafe_allow_html=True,
    )

    st.markdown("### 🤖 Alt Ajan Havuzu (5 Worker)")
    for a in agents_data:
        st.markdown(
            f'<div class="agent-card" style="--c:{a["color"]}">'
            f'<div class="agent-name"><span class="dot"></span>{a["Agent ID"]}</div>'
            f'<div class="agent-spec">{a["Role"]} · <span style="color:#9CA3AF">Üye: {a["Member"]}</span></div>'
            + skill_bar("Coding", a["Coding"])
            + skill_bar("Reasoning", a["Reasoning"])
            + skill_bar("Context", a["Context"])
            + '</div>',
            unsafe_allow_html=True,
        )

# ==========================================
# 6. ANA EKRAN
# ==========================================
state = st.session_state
for key, val in {"last_time": None, "demo_mode": False, "tasks": None, "status": {},
                 "done_order": [], "log": [], "fresh": False}.items():
    state.setdefault(key, val)

def current_load():
    load = {a["Agent ID"]: 0 for a in agents_data}
    for ph, d in (state.tasks or {}).items():
        load[resolve(ph, d)[0]["Agent ID"]] += pts_of(d)
    return load

st.markdown('<div class="title-row"><span class="emo">🧿</span><div class="main-header">Distributed AI Platform</div></div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Sprint 2: Akıllı görev parçalama ve ajan yönlendirme</div>', unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Sistem", "Çevrimiçi")
m2.metric("Aktif Ajan", "6 (1 Master + 5 Alt)")
m3.metric("Son analiz süresi", f"{state.last_time:.1f} sn" if state.last_time else "Henüz yok")
m4.metric("Model Sunucusu", "Ollama")

components.html(network_html(current_load() if state.tasks else None), height=310)

st.markdown('<div class="section-title">Gereksinim</div>', unsafe_allow_html=True)
requirement_input = st.text_area(
    "Gereksinim:", height=130, label_visibility="collapsed",
    placeholder="Örnek: Kullanıcıların hesap açabileceği, kitap arayabileceği bir kütüphane altyapısı istiyorum...",
)

if st.button("🚀 Analiz et ve ajanlara dağıt", use_container_width=True):
    if not requirement_input.strip():
        st.warning("Analiz için önce bir gereksinim metni girin.")
    else:
        with st.spinner("Master Agent görevleri analiz ediyor ve dağıtıyor..."):
            try:
                t0 = time.perf_counter()
                raw, demo = decompose_task(requirement_input)
                raw_parsed = json.loads(raw)
                parsed = normalize_tasks(raw_parsed, requirement_input)
                elapsed = time.perf_counter() - t0
            except json.JSONDecodeError:
                st.error("Model geçerli bir JSON döndürmedi. Aynı gereksinimle tekrar deneyin.")
                st.stop()
            except Exception as e:
                st.error(f"Beklenmeyen sistem hatası: {e}")
                st.stop()
        for key in [k for k in state.keys() if str(k).startswith("ov_")]:
            del state[key]
        state.tasks, state.demo_mode, state.last_time = parsed, demo, elapsed
        state.status = {ph: "Beklemede" for ph in parsed}
        state.done_order = []
        state.log = build_log(requirement_input, parsed, demo)
        state.fresh = True
        st.rerun()

if state.tasks:
    tasks = state.tasks
    total = sum(pts_of(d) for d in tasks.values())
    done = sum(pts_of(tasks[ph]) for ph in state.done_order)

    st.markdown('<div class="section-title">Master Agent günlüğü</div>', unsafe_allow_html=True)
    components.html(terminal_html(state.log, state.fresh), height=60 + 22 * (len(state.log) + 1))

    st.markdown('<div class="section-title">Görev dağılımı</div>', unsafe_allow_html=True)
    st.progress(done / max(total, 1), text=f"Sprint ilerlemesi: {done} / {total} puan")

    for i, (phase, details) in enumerate(tasks.items()):
        agent, skill, score, best = resolve(phase, details)
        status = state.status[phase]
        st.markdown(task_card(phase, details, i, agent, skill, score, best, status, state.fresh), unsafe_allow_html=True)
        c1, c2 = st.columns([3, 1])
        c1.selectbox("Ajan ataması", [AUTO] + [a["Agent ID"] for a in agents_data],
                     key=f"ov_{phase}", label_visibility="collapsed")
        c2.button(BTN_LABEL[status], key=f"adv_{phase}", on_click=advance, args=(phase,), use_container_width=True)
        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">Sprint burndown</div>', unsafe_allow_html=True)
    st.caption("Gri çizgi ideal hız, turkuaz çizgi gerçek ilerleme. Görevleri tamamladıkça çizgi aşağı iner.")
    st.line_chart(burndown_df(tasks, state.done_order), color=["#6B7280", "#00F2FE"], height=260)

    st.markdown('<div class="section-title">Ajan iş yükü</div>', unsafe_allow_html=True)
    load = current_load()
    peak = max(max(load.values()), 1)
    rows = ""
    for a in agents_data:
        pts = load[a["Agent ID"]]
        rows += (f'<div class="load-row" style="--c:{a["color"]}"><span class="load-name">{a["Agent ID"]}</span>'
                 f'<div class="load-track"><div class="load-fill" style="width:{pts / peak * 100:.0f}%"></div></div>'
                 f'<span class="load-pts">{pts} puan</span></div>')
    st.markdown(rows, unsafe_allow_html=True)

    with st.expander("Atama tablosu (Pandas)"):
        df = pd.DataFrame([
            {"Görev": p.replace("_", " "),
             "Zorluk": (d.get("complexity", "Medium") if isinstance(d, dict) else "Medium"),
             "Puan": pts_of(d),
             "Yetenek": (d.get("primary_skill_required", "Reasoning") if isinstance(d, dict) else "Reasoning"),
             "Ajan": resolve(p, d)[0]["Agent ID"],
             "Durum": state.status.get(p, "Beklemede")}
            for p, d in tasks.items()
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

    state.fresh = False

