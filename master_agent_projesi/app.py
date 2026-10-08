import os
import json
import time
import html
import streamlit as st
import google.generativeai as genai
import pandas as pd
import streamlit.components.v1 as components

# ==========================================
# 1. API CONFIGURATION (anahtar koda gömülmez)
# ==========================================
def load_api_key():
    key = os.getenv("AQ.Ab8RN6JUZtGRBX0ayUaf_Qj3ZbjEiaUcYlg2MiCwUCjBJXYxCg")
    if key:
        return key
    try:
        return st.secrets["AQ.Ab8RN6JUZtGRBX0ayUaf_Qj3ZbjEiaUcYlg2MiCwUCjBJXYxCg"]  # .streamlit/secrets.toml
    except Exception:
        return ""

API_KEY = load_api_key()
if API_KEY:
    genai.configure(api_key=API_KEY)
# ==========================================
# 1. API CONFIGURATION (Güvenli Yükleme)
# ==========================================
def load_api_key():
    # Sistem değişkenlerinde "GEMINI_API_KEY" adında bir şifre var mı diye bakar
    key = os.getenv("AQ.Ab8RN6JUZtGRBX0ayUaf_Qj3ZbjEiaUcYlg2MiCwUCjBJXYxCg")
    if key:
        return key
    try:
        # Streamlit secrets içinde "GEMINI_API_KEY" adında bir şifre var mı diye bakar
        return st.secrets["api.key"]  
    except Exception:
        # Eğer ikisi de yoksa (bilgisayarında test ederken) varsayılan anahtarı kullanır
        return "api.key"

API_KEY = load_api_key()
if API_KEY:
    genai.configure(api_key=API_KEY)

# ==========================================
# 2. AGENTS DATABASE (her ajanın kendi rengi var)
# ==========================================
agents_data = [
    {"Agent ID": "Agent A (GPT-X)", "Specialty": "Full-Stack / Backend", "Coding": 90, "Reasoning": 85, "Context": 95, "color": "#00F2FE"},
    {"Agent ID": "Agent B (Model-Y)", "Specialty": "Architecture / Logic", "Coding": 75, "Reasoning": 95, "Context": 70, "color": "#A78BFA"},
    {"Agent ID": "Agent C (Model-Z)", "Specialty": "Frontend / UI", "Coding": 95, "Reasoning": 70, "Context": 80, "color": "#FBBF24"},
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
    .block-container { position: relative; z-index: 1; }
    #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
    .block-container { padding-top: 2rem; max-width: 1200px; }

    section[data-testid="stSidebar"] { background-color: #0A0E17; border-right: 1px solid #1F2937; }

    .main-header { font-size: 2.8rem; font-weight: 800; letter-spacing: -0.02em;
        background: linear-gradient(45deg, #00F2FE, #4FACFE); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.2rem; }
    .sub-header { color: #8B949E; font-size: 1.05rem; margin-bottom: 1.8rem; }
    .section-title { font-size: 1.15rem; font-weight: 600; color: #F3F4F6; margin: 1.6rem 0 0.8rem 0; }

    div[data-testid="stMetric"] { background-color: #121828; border: 1px solid #1F2937; border-radius: 12px; padding: 16px 20px; }
    div[data-testid="stMetricValue"] { color: #4FACFE; font-weight: 700; }

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
# 4. YARDIMCI FONKSİYONLAR
# ==========================================
def assign_best_agent(primary_skill):
    skill = str(primary_skill).capitalize()
    if skill not in ["Coding", "Reasoning", "Context"]:
        skill = "Reasoning"
    best = max(agents_data, key=lambda a: a[skill])
    return best, skill, best[skill]

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
    Analyze the provided software requirement and decompose it into specific, actionable sub-tasks.
    Categorize work into: Requirements_Analysis, Frontend_Development, Backend_Development, Database_Design, Quality_Assurance_and_Testing.

    CRITICAL INSTRUCTION FOR DESCRIPTION: The "description" field MUST be highly detailed, containing at least 3-4 full sentences explaining the technical steps, required frameworks, and expected outcomes. Do not give short answers.

    Provide a JSON object containing for each:
    - "description": Highly detailed technical explanation (min 3 sentences).
    - "complexity": "Low", "Medium", or "High".
    - "primary_skill_required": "Coding", "Reasoning", or "Context".
    - "story_points": Estimated Agile story points (1, 2, 3, 5, or 8).

    Return ONLY valid JSON.
    """
    try:
        if not API_KEY:
            st.toast("API anahtarı bulunamadı. Demo modu devrede.", icon="🛡️")
            return get_fallback_json(user_requirement), True
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content(f"{system_prompt}\n\nUser Requirement:\n{user_requirement}")
        text = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        return text.strip(), False
    except Exception as e:
        msg = str(e).lower()
        if "429" in msg or "quota" in msg:
            st.toast("API kotası doldu. Demo modu (yedek veri) devrede.", icon="🛡️")
            return get_fallback_json(user_requirement), True
        raise

def network_html(load=None):
    """Master -> ajan bağlantılarını gösteren canlı SVG. load verilirse çizgi kalınlığı ve akış hızı iş yüküne göre değişir."""
    pos = [(140, 215), (400, 215), (660, 215)]
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
        sub = f"{pts} puan" if load else a["Specialty"]
        out.append(
            f'<circle cx="{x}" cy="{y}" r="28" fill="#121828" stroke="{c}" stroke-width="2"/>'
            f'<circle cx="{x}" cy="{y}" r="28" fill="none" stroke="{c}" class="ring"/>'
            f'<text x="{x}" y="{y+6}" text-anchor="middle" fill="{c}" font-size="17" font-weight="800">{a["Agent ID"][6]}</text>'
            f'<text x="{x}" y="{y+52}" text-anchor="middle" fill="#E5E7EB" font-size="13" font-weight="600">{a["Agent ID"]}</text>'
            f'<text x="{x}" y="{y+70}" text-anchor="middle" fill="#9CA3AF" font-size="12">{sub}</text>')
    out.append('<circle cx="400" cy="42" r="30" fill="#121828" stroke="#4FACFE" stroke-width="2.5"/>'
               '<circle cx="400" cy="42" r="30" fill="none" stroke="#4FACFE" class="ring"/>'
               '<text x="400" y="48" text-anchor="middle" fill="#4FACFE" font-size="18" font-weight="800">M</text>'
               '<text x="442" y="47" fill="#E5E7EB" font-size="13" font-weight="600">Master Agent</text>')
    style = ("<style>body{margin:0;background:transparent;font-family:Inter,'Segoe UI',sans-serif}"
             ".flow{animation:dash 1.1s linear infinite}@keyframes dash{to{stroke-dashoffset:-12}}"
             ".ring{transform-box:fill-box;transform-origin:center;animation:pulse 2.6s ease-out infinite}"
             "@keyframes pulse{from{transform:scale(1);opacity:.8}to{transform:scale(1.7);opacity:0}}"
             "@media (prefers-reduced-motion:reduce){.flow,.ring{animation:none}}</style>")
    return style + '<svg viewBox="0 0 800 300" width="100%" style="max-width:760px;display:block;margin:0 auto" xmlns="http://www.w3.org/2000/svg">' + "".join(out) + "</svg>"

def skill_bar(label, value, color):
    return (f'<div class="bar-row"><span class="bar-label">{label}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{value}%"></div></div>'
            f'<span class="bar-val">{value}</span></div>')

AUTO = "Otomatik (algoritma önerisi)"
STATUS_STYLE = {"Beklemede": ("#9CA3AF", 0), "Çalışıyor": ("#FBBF24", 50), "Tamamlandı": ("#34D399", 100)}
NEXT_STATUS = {"Beklemede": "Çalışıyor", "Çalışıyor": "Tamamlandı", "Tamamlandı": "Beklemede"}
BTN_LABEL = {"Beklemede": "▶ Başlat", "Çalışıyor": "✔ Tamamla", "Tamamlandı": "↺ Sıfırla"}

def pts_of(d):
    try:
        return int(d.get("story_points", 3))
    except (TypeError, ValueError):
        return 3

def resolve(phase, details):
    """(atanan ajan, yetenek, ajanın skoru, algoritmanın önerdiği ajan). Kullanıcı seçimi öneriyi geçersiz kılar."""
    best, skill, _ = assign_best_agent(details.get("primary_skill_required", "Reasoning"))
    ov = st.session_state.get(f"ov_{phase}", AUTO)
    agent = next((a for a in agents_data if a["Agent ID"] == ov), best)
    return agent, skill, agent[skill], best

def advance(phase):
    ss = st.session_state
    cur = ss.status[phase]
    ss.status[phase] = NEXT_STATUS[cur]
    if ss.status[phase] == "Tamamlandı":
        ss.done_order.append(phase)
    elif cur == "Tamamlandı" and phase in ss.done_order:
        ss.done_order.remove(phase)

def task_card(phase, details, idx, agent, skill, score, best, status, fresh):
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
        f'<span class="assign">🤖 {agent["Agent ID"]}<small>{skill} {score}</small></span>'
        f'</div></div>'
    )

def build_log(req, tasks, demo):
    lines = [("MASTER", f"Gereksinim alındı ({len(req)} karakter)"),
             ("MASTER", "Demo verisi kullanılıyor (yedek mod)" if demo else "Gemini ile görev ayrıştırma tamamlandı"),
             ("MASTER", f"{len(tasks)} alt görev sınıflandırıldı")]
    for ph, d in tasks.items():
        ag, sk, sc = assign_best_agent(d.get("primary_skill_required", "Reasoning"))
        lines.append(("ROUTER", f"{ph.replace('_', ' ')} → {ag['Agent ID']} ({sk} {sc})"))
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
    st.caption("Dağıtık ajan ağı aktif")
    st.markdown("### Ajan Listesi")
    for a in agents_data:
        st.markdown(
            f'<div class="agent-card" style="--c:{a["color"]}">'
            f'<div class="agent-name"><span class="dot"></span>{a["Agent ID"]}</div>'
            f'<div class="agent-spec">{a["Specialty"]}</div>'
            + skill_bar("Coding", a["Coding"], a["color"])
            + skill_bar("Reasoning", a["Reasoning"], a["color"])
            + skill_bar("Context", a["Context"], a["color"])
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
m2.metric("Aktif ajan", len(agents_data))
m3.metric("Son analiz süresi", f"{state.last_time:.1f} sn" if state.last_time else "Henüz yok")
m4.metric("Veri kaynağı", "Demo" if state.demo_mode else "Gemini")

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
                parsed = json.loads(raw)
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
            {"Görev": p.replace("_", " "), "Zorluk": d.get("complexity"), "Puan": pts_of(d),
             "Yetenek": d.get("primary_skill_required"), "Ajan": resolve(p, d)[0]["Agent ID"], "Durum": state.status[p]}
            for p, d in tasks.items()
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

    state.fresh = False
