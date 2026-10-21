import os
import json
import time
import html
import urllib.request
import urllib.error
import socket
import re
import sys
import inspect
from pathlib import Path
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
# 1. MERKEZİ API VE MODEL YAPILANDIRMASI (Central Config & Fallback - S2-01)
# ==========================================
def load_api_key(key_name: str = "GEMINI_API_KEY") -> str:
    """
    Merkezi API anahtarı yükleme işlevi (S2-01).
    Kaynak kodunda asla sabit anahtar (hardcoded secret) tutulmaz. Öncelik sırası:
    1. Sistem ortam değişkenleri (os.getenv)
    2. Streamlit secrets (st.secrets)
    Anahtar bulunamazsa veya yer tutucu ise güvenli bir şekilde boş dize döndürür.
    """
    env_val = os.getenv(key_name, "").strip()
    if env_val and env_val not in ("api.key", "YOUR_API_KEY_HERE", "None"):
        return env_val
    try:
        if hasattr(st, "secrets") and st.secrets and key_name in st.secrets:
            sec_val = str(st.secrets.get(key_name, "")).strip()
            if sec_val and sec_val not in ("api.key", "YOUR_API_KEY_HERE", "None"):
                return sec_val
    except Exception:
        pass
    return ""


def get_model_config() -> dict:
    """
    Tek ve merkezi API/Model yapılandırması.
    Yerel Ollama sunucusu ve isteğe bağlı bulut API parametrelerini yönetir.
    """
    return {
        "ollama_host": os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        "timeout": int(os.getenv("OLLAMA_TIMEOUT", "180")),
        "api_key": load_api_key("GEMINI_API_KEY"),
        "fallback_enabled": os.getenv("FALLBACK_ENABLED", "true").lower() in ("true", "1", "yes"),
    }


MODEL_CONFIG = get_model_config()
OLLAMA_HOST = MODEL_CONFIG["ollama_host"]
OLLAMA_MODEL = MODEL_CONFIG["ollama_model"]


class ModelServiceError(Exception):
    """Model sunucusu veya API çağrısı sırasında oluşan sınıflandırılmış hata."""

    def __init__(self, message: str, error_type: str = "UNKNOWN", status_code: int = None):
        super().__init__(message)
        self.message = message
        self.error_type = error_type  # QUOTA_EXCEEDED, TIMEOUT, CONNECTION_REFUSED, NOT_FOUND, SERVER_ERROR
        self.status_code = status_code


def call_local_ollama(prompt: str, model: str = None, host: str = None, timeout: int = None) -> str:
    """
    Yerel Ollama sunucusuna HTTP isteği gönderir ve yanıtı döndürür.
    Kota (429), zaman aşımı ve bağlantı kopukluğu hatalarını sınıflandırarak ModelServiceError fırlatır.
    """
    cfg = get_model_config()
    model = model or cfg["ollama_model"]
    host = host or cfg["ollama_host"]
    timeout = timeout or cfg["timeout"]

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

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise ModelServiceError(
                "Model sunucusu veya API kota sınırına ulaşıldı (HTTP 429 Too Many Requests).",
                error_type="QUOTA_EXCEEDED",
                status_code=429
            )
        elif e.code == 404:
            raise ModelServiceError(
                f"İstenen model '{model}' Ollama üzerinde bulunamadı (HTTP 404).",
                error_type="NOT_FOUND",
                status_code=404
            )
        else:
            raise ModelServiceError(
                f"Model sunucusu HTTP {e.code} hatası döndürdü: {e.reason}",
                error_type="SERVER_ERROR",
                status_code=e.code
            )
    except urllib.error.URLError as e:
        reason_str = str(e.reason).lower()
        if isinstance(e.reason, (socket.timeout, TimeoutError)) or "timed out" in reason_str:
            raise ModelServiceError(
                f"Model sunucusuna bağlantı zaman aşımına uğradı ({timeout}s).",
                error_type="TIMEOUT"
            )
        else:
            raise ModelServiceError(
                f"Yerel Ollama sunucusuna bağlanılamadı ({host}): Çevrimdışı veya bağlantı reddedildi.",
                error_type="CONNECTION_REFUSED"
            )
    except (socket.timeout, TimeoutError):
        raise ModelServiceError(
            f"Model sunucusu yanıt vermedi; istek zaman aşımına uğradı ({timeout}s).",
            error_type="TIMEOUT"
        )
    except Exception as e:
        raise ModelServiceError(
            f"Beklenmeyen model bağlantı hatası: {e}",
            error_type="UNKNOWN"
        )


# ==========================================
# 2. AJAN KAYIT DEFTERİ (config/agents_config.json)
#    Ajan listesi artık kodda sabit değil; tek kaynak config dosyasıdır.
# ==========================================
_HERE = Path(__file__).resolve().parent
CONFIG_CANDIDATES = [
    os.getenv("AGENTS_CONFIG_PATH", ""),
    _HERE.parent / "config" / "agents_config.json",  # repo kökü/config/
    _HERE / "config" / "agents_config.json",  # master_agent_projesi/config/
    _HERE / "agents_config.json",
]
INACTIVE_STATUSES = {"disabled", "inactive", "retired"}

# Sadece görsel tercihler (renk/rozet). Puan, model, üye bilgisi config'ten gelir.
UI_STYLE = {
    "agent-master": {"color": "#818CF8", "badge": "MST"},
    "agent-integration": {"color": "#38BDF8", "badge": "INT"},
    "agent-frontend": {"color": "#FBBF24", "badge": "FE"},
    "agent-backend": {"color": "#A78BFA", "badge": "BE"},
    "agent-database": {"color": "#34D399", "badge": "DB"},
    "agent-testing": {"color": "#F87171", "badge": "QA"},
}
EXTRA_COLORS = ["#F472B6", "#22D3EE", "#A3E635", "#FB923C"]  # config'e sonradan eklenen ajanlar için


def _find_config_path():
    for c in CONFIG_CANDIDATES:
        if c and Path(c).is_file():
            return Path(c)
    raise FileNotFoundError(
        "agents_config.json bulunamadı. Aranan yerler: "
        + ", ".join(str(c) for c in CONFIG_CANDIDATES if c)
        + " (AGENTS_CONFIG_PATH ortam değişkeniyle de verebilirsiniz)")


def _num(v, default=0.0):
    try:
        return round(float(v), 1)
    except (TypeError, ValueError):
        return default


def load_agents_config():
    """config/agents_config.json dosyasını okur; arayüzün kullandığı ajan sözlüklerini üretir."""
    path = _find_config_path()
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    palette = iter(EXTRA_COLORS)
    master, workers = None, []
    for raw in cfg.get("agents", []):
        if raw.get("status", "active") in INACTIVE_STATUSES:
            continue
        aid = raw["agent_id"]
        caps = raw.get("capabilities", {})
        prov = set((raw.get("capability_provenance") or {}).values())
        tag = (raw.get("deployment") or {}).get("ollama_tag") or raw.get("model", "")
        style = UI_STYLE.get(aid) or {"color": next(palette, "#9CA3AF"), "badge": aid.split("-")[-1][:3].upper()}
        specialties = raw.get("specialties", [])
        agent = {
            "id": aid,
            "name": raw["name"],
            "provenance_map": dict(raw.get("capability_provenance") or {}),
            "Agent ID": f"{raw['name']} ({tag})",  # arayüzde görünen ad / sözlük anahtarı
            "short_name": tag,
            "Role": raw.get("role", ""),
            "Specialty": " ".join(specialties),
            "specialties": specialties,
            "Member": raw.get("member", ""),
            "badge": style["badge"],
            "color": style["color"],
            "Model": raw.get("model", tag),
            "ollama_tag": tag,
            "context_tokens": raw.get("context_tokens"),
            "Coding": _num(caps.get("coding")),
            "Reasoning": _num(caps.get("reasoning")),
            "Context": _num(caps.get("context_capacity")),
            "provenance": "ölçüldü" if prov == {"measured"} else "tahmini",
            "config_status": raw.get("status", "active"),
            "max_tasks": raw.get("max_concurrent_tasks", 1),
            "notes": raw.get("notes", ""),
        }
        if aid == "agent-master" or "orchestration" in specialties:
            master = agent
        else:
            workers.append(agent)
    if master is None:
        raise ValueError("agents_config.json içinde Master Agent (agent-master) bulunamadı.")
    if not workers:
        raise ValueError("agents_config.json içinde aktif alt ajan bulunamadı.")
    return {"master": master, "workers": workers, "path": path, "path_name": path.name,
            "version": cfg.get("version", "?"), "retrieved": cfg.get("retrieved", "?"),
            "weights": cfg.get("capability_weights", {})}


try:
    CONFIG, CONFIG_ERROR = load_agents_config(), None
except Exception as _e:
    CONFIG, CONFIG_ERROR = None, _e

MASTER = CONFIG["master"] if CONFIG else {"Model": "qwen2.5:7b", "ollama_tag": "qwen2.5:7b"}
agents_data = CONFIG["workers"] if CONFIG else []  # config'ten türetilir, elle yazılmaz

# ==========================================
# 3. MASTER AGENT MOTORU (src/master, src/agents) & OLLAMA SAĞLIK KONTROLÜ
# ==========================================
# OLLAMA_HOST / OLLAMA_MODEL: yukarıdaki merkezi get_model_config() (S2-01) üzerinden gelir.
_REPO_ROOT = _HERE.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))  # `from src...` importları için repo kökü

try:
    from src.master.orchestrator import MasterOrchestrator
    from src.master.capability_eval import CapabilityEvaluator
    from src.master.analyzer import RequirementsAnalyzer
    from src.agents.base_agent import AgentCapabilityProfile, AgentStatus
    from src.agents.frontend_agent import FrontendAgent
    from src.agents.backend_agent import BackendAgent
    from src.agents.database_agent import DatabaseAgent
    from src.agents.testing_agent import TestingAgent
    from src.agents.integration_agent import IntegrationAgent

    ENGINE_ERROR = None
except Exception as _e:  # motor yüklenemezse arayüz DEMO VERİSİ moduna düşer
    ENGINE_ERROR = _e

# config'teki agent_id -> motor sınıfı. Puanlar/model/ad sınıftan değil config'ten alınır.
AGENT_CLASSES = ({
                     "agent-integration": IntegrationAgent, "agent-frontend": FrontendAgent,
                     "agent-backend": BackendAgent, "agent-database": DatabaseAgent, "agent-testing": TestingAgent,
                 } if ENGINE_ERROR is None else {})


@st.cache_data(ttl=10, show_spinner=False)
def ollama_models():
    """Ollama'da yüklü modeller; sunucuya ulaşılamazsa None."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return sorted(m.get("name", "") for m in data.get("models", []))
    except Exception:
        return None


def _norm(tag):
    return tag[:-7] if str(tag).endswith(":latest") else str(tag)


def model_available(tag, models):
    return models is not None and _norm(tag) in {_norm(m) for m in models}


TASK_ICONS = {"task-req-1": "📋", "task-db-1": "🗄️", "task-be-1": "⚙️", "task-fe-1": "🎨", "task-qa-1": "🧪",
              "task-int-1": "📦"}
# Ajan durumları: IDLE, BUSY, OFFLINE, FAILED (motordaki ERROR). Görev durumları: COMPLETED, FAILED, BLOCKED, UNASSIGNED.
STATUS_STYLE = {
    "IDLE": ("#9CA3AF", 0), "BUSY": ("#FBBF24", 50), "COMPLETED": ("#34D399", 100),
    "FAILED": ("#F87171", 100), "BLOCKED": ("#FB923C", 100), "UNASSIGNED": ("#F472B6", 100),
    "OFFLINE": ("#6B7280", 0),
}

st.set_page_config(page_title="Nexus | AI Command Center", page_icon="🧿", layout="wide",
                   initial_sidebar_state="expanded")

if CONFIG_ERROR is not None:
    st.error(f"Ajan yapılandırması yüklenemedi: {CONFIG_ERROR}")
    st.stop()

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


def network_html(load=None, statuses=None):
    """Master -> 5 Model/Ajan bağlantılarını gösteren canlı SVG. load verilirse çizgi kalınlığı ve akış hızı iş yüküne göre değişir."""
    # 5 model için 800px genişlik üzerinde simetrik ve dengeli konumlar
    n_ag = len(agents_data)
    pos = [(400, 225)] if n_ag == 1 else [(round(90 + i * 620 / (n_ag - 1), 1), 225) for i in range(n_ag)]
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
        out.append(
            f'<path id="p{i}" d="M400,72 C400,150 {x},140 {x},{y - 30}" fill="none" stroke="{c}" stroke-opacity=".4" stroke-width="{width}" stroke-dasharray="6 6" class="flow"/>')
        for k in range(n):
            out.append(
                f'<circle r="4.5" fill="{c}"><animateMotion dur="{dur}s" begin="{k * dur / n}s" repeatCount="indefinite"><mpath href="#p{i}"/></animateMotion></circle>')
        sub = (f"{pts} puan · {statuses[a['Agent ID']]}" if statuses else f"{pts} puan") if load else a["Role"]
        badge = a.get("badge", str(i + 2))
        model_label = a["short_name"]
        out.append(
            f'<circle cx="{x}" cy="{y}" r="26" fill="#121828" stroke="{c}" stroke-width="2"/>'
            f'<circle cx="{x}" cy="{y}" r="26" fill="none" stroke="{c}" class="ring"/>'
            f'<text x="{x}" y="{y + 5}" text-anchor="middle" fill="{c}" font-size="12" font-weight="800">{badge}</text>'
            f'<text x="{x}" y="{y + 48}" text-anchor="middle" fill="#E5E7EB" font-size="12" font-weight="600">{model_label}</text>'
            f'<text x="{x}" y="{y + 64}" text-anchor="middle" fill="#9CA3AF" font-size="11">{sub}</text>')
    out.append('<circle cx="400" cy="42" r="30" fill="#121828" stroke="#818CF8" stroke-width="2.5"/>'
               '<circle cx="400" cy="42" r="30" fill="none" stroke="#818CF8" class="ring"/>'
               '<text x="400" y="47" text-anchor="middle" fill="#818CF8" font-size="13" font-weight="800">MASTER</text>'
               '<text x="400" y="86" text-anchor="middle" fill="#E5E7EB" font-size="13" font-weight="600">' + html.escape(
        MASTER["Model"]) + '</text>'
                           '<text x="400" y="102" text-anchor="middle" fill="#9CA3AF" font-size="11">Master Agent / Nexus Core</text>')
    style = ("<style>body{margin:0;background:transparent;font-family:Inter,'Segoe UI',sans-serif}"
             ".flow{animation:dash 1.1s linear infinite}@keyframes dash{to{stroke-dashoffset:-12}}"
             ".ring{transform-box:fill-box;transform-origin:center;animation:pulse 2.6s ease-out infinite}"
             "@keyframes pulse{from{transform:scale(1);opacity:.8}to{transform:scale(1.7);opacity:0}}"
             "@media (prefers-reduced-motion:reduce){.flow,.ring{animation:none}}</style>")
    return style + '<svg viewBox="0 0 800 320" width="100%" style="max-width:780px;display:block;margin:0 auto" xmlns="http://www.w3.org/2000/svg">' + "".join(
        out) + "</svg>"


def skill_bar(label, value):
    return (f'<div class="bar-row"><span class="bar-label">{label}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{value}%"></div></div>'
            f'<span class="bar-val">{value:g}</span></div>')


def terminal_html(lines, animate):
    colors = {"MASTER": "#4FACFE", "ROUTER": "#A78BFA", "SYSTEM": "#34D399", "ENGINE": "#FBBF24", "CONFIG": "#38BDF8",
              "FALLBACK": "#F59E0B"}
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
    """
    Gereksinim metnini 5 alt göreve ayrıştırır.
    (json_metni, demo_modu_mu, mod_etiketi) döndürür.
    Model sunucusu çevrimdışı, bağlantı zaman aşımına uğramış veya kota (429) durumunda
    sistem çökmeden etiketlenmiş güvenli yedek (fallback/demo) moduna geçer.
    """
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
        raw_response = call_local_ollama(prompt)

        # JSON bloğunu temizle ve ayıkla
        match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        if match:
            text = match.group(0).strip()
        else:
            text = raw_response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        # JSON geçerliliğini doğrula
        json.loads(text)
        st.toast("Yerel Qwen 2.5 (7B) modeli görevi başarıyla ayrıştırdı! 🚀", icon="🧠")
        return text, False, "Yerel Ollama (Qwen 2.5:7b)"
    except ModelServiceError as err:
        if err.error_type == "QUOTA_EXCEEDED":
            st.warning(
                "⚠️ **Kota Uyarısı (429):** API / Model kullanım kotası aşıldı. Kesinti yaşanmaması için sistem etiketlenmiş güvenli yedek (fallback) moduna geçti.")
            st.toast("Kota sınırı (429) aşıldı! Güvenli yedek mod devrede.", icon="⚠️")
            label = "Kota Sınırı (429) - Güvenli Yedek"
        elif err.error_type == "TIMEOUT":
            st.warning(
                "⏱️ **Zaman Aşımı Uyarısı:** Model sunucusuna bağlantı zaman aşımına uğradı. Sistem çökmeden güvenli yedek (fallback) kipine geçti.")
            st.toast("Zaman aşımı! Güvenli yedek mod devrede.", icon="⏱️")
            label = "Zaman Aşımı (Timeout) - Güvenli Yedek"
        elif err.error_type == "CONNECTION_REFUSED":
            st.info(
                "🔌 **Bağlantı Uyarısı:** Yerel Ollama sunucusuna erişilemedi (Çevrimdışı). Sistem kesintisiz güvenli yedek (fallback) modunda çalışıyor.")
            st.toast("Ollama çevrimdışı. Güvenli yedek mod devrede.", icon="🛡️")
            label = "Ollama Çevrimdışı - Güvenli Yedek"
        else:
            st.warning(f"🛡️ **Yedek Mod:** {err.message} Sistem güvenli yedek modda çalışıyor.")
            st.toast("Güvenli yedek mod devrede.", icon="🛡️")
            label = f"Yedek Mod ({err.error_type})"
        return get_fallback_json(user_requirement), True, label
    except Exception as e:
        st.warning(f"🛡️ **Yedek Mod:** Beklenmeyen model çıktısı ({e}). Güvenli yedek şablonu kullanıldı.")
        st.toast("Güvenli yedek mod devrede.", icon="🛡️")
        return get_fallback_json(user_requirement), True, "Ayrıştırma Hatası - Güvenli Yedek"


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
    for wrap_key in ["tasks", "phases", "subtasks", "decomposition", "Requirement_Decomposition", "sub_tasks",
                     "requirement"]:
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
            skill = str(
                val.get("primary_skill_required", fb.get("primary_skill_required", default_skills[phase]))).capitalize()
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


def esc(x):
    return html.escape(str(x))


for _k, _v in {"report": None, "meta": {}, "artifacts": {}, "snapshot": {}, "mode": None, "stub": True,
               "elapsed": None, "log": [], "fresh": False, "requirement": "",
               "decomp": None, "decomp_demo": False, "decomp_label": ""}.items():
    st.session_state.setdefault(_k, _v)
state = st.session_state


def agent_by_name():
    return {a["name"]: a for a in agents_data}


def agent_status(a):
    """Ajan durumu: son motor çalıştırmasından (snapshot); yoksa Ollama'da modelin yüklü olup olmadığından."""
    raw = state.snapshot.get(a["id"])
    if raw is None:
        raw = "IDLE"
        if state.get("reflect_ollama", REFLECT_DEFAULT) and not model_available(a["ollama_tag"], ollama_models()):
            raw = "OFFLINE"
    return "FAILED" if raw == "ERROR" else raw


def is_real_agent(agent):
    """Ajanın _process'i Ollama çağırıyorsa gerçek, değilse stub (sabit çıktı) sayılır."""
    try:
        fn = (agent if isinstance(agent, type) else type(agent))._process
        return "ollama" in inspect.getsource(fn).lower()
    except (OSError, TypeError):
        return False


def engine_uses_ollama():
    """Motor ajanlarından en az biri gerçekten Ollama çağırıyorsa True (şimdilik hepsi stub)."""
    return any(is_real_agent(c) for c in AGENT_CLASSES.values())


REFLECT_DEFAULT = engine_uses_ollama() if ENGINE_ERROR is None else False


def build_agents():
    """config'teki ajanlardan motor ajanlarını üretir (puan/ad/model config'ten)."""
    out, skipped = [], []
    for a in agents_data:
        cls = AGENT_CLASSES.get(a["id"])
        if cls is None:
            skipped.append(a["Agent ID"])
            continue
        inst = cls(agent_id=a["id"], name=a["name"], model_name=a["ollama_tag"])
        inst.capabilities = AgentCapabilityProfile(
            coding_score=a["Coding"], reasoning_score=a["Reasoning"], context_capacity=a["Context"],
            specialties=list(a["specialties"]), provenance=dict(a["provenance_map"]))
        out.append(inst)
    return out, skipped


def run_engine(requirement, live):
    """Gerçek MasterOrchestrator'ı çalıştırır; sonucu session_state'e yazar."""
    agents, skipped = build_agents()
    if state.get("reflect_ollama", REFLECT_DEFAULT):
        models = ollama_models()
        for ag in agents:
            if not model_available(ag.model_name, models):
                ag.status = AgentStatus.OFFLINE
                live.write(f"⚪ {ag.name}: model '{ag.model_name}' Ollama'da yok → OFFLINE")
    for ag in agents:  # canlı BUSY/sonuç satırları için sarmalayıcı
        orig = ag.execute_task

        def wrapped(task, _ag=ag, _orig=orig):
            live.write(f"🟡 {_ag.name} → BUSY ({task.get('title')})")
            res = _orig(task)
            live.write(
                f"{'🟢' if res.status == 'SUCCESS' else '🔴'} {_ag.name} → {res.status} ({res.execution_time_seconds} sn)")
            return res

        ag.execute_task = wrapped
    title = " ".join(requirement.split())[:60] or "Generated Software System"
    orch = MasterOrchestrator(evaluator=CapabilityEvaluator(agents), persist=False)
    t0 = time.perf_counter()
    report = orch.process_requirement(requirement, title)
    elapsed = time.perf_counter() - t0
    state.meta = {t["task_id"]: t for t in RequirementsAnalyzer().decompose(requirement, title)["tasks"]}
    state.artifacts = {r.task_id: {"artifacts": r.output_artifacts, "logs": r.logs}
                       for r in orch.execution_history if r.status == "SUCCESS"}
    state.snapshot = {ag.agent_id: ag.status.value for ag in agents}
    state.stub = not any(is_real_agent(ag) for ag in agents)
    state.report, state.mode, state.elapsed, state.requirement = report, "engine", elapsed, requirement
    state.log = build_log(report, skipped, state.decomp_label, state.decomp_demo)


def demo_report(requirement):
    """Motor yüklenemediğinde: açıkça DEMO etiketli örnek veri (gerçek çalıştırma değildir)."""
    plan = [("task-req-1", "System Specification & Architecture Design", "architecture", 0.6, 0.3, 0.1),
            ("task-db-1", "Database Schema & Migration Definition", "database", 0.45, 0.15, 0.4),
            ("task-be-1", "Core Backend API Implementation", "backend", 0.35, 0.2, 0.45),
            ("task-fe-1", "Frontend User Interface & Components", "frontend", 0.2, 0.3, 0.5),
            ("task-qa-1", "Automated Testing & Quality Assurance", "testing", 0.3, 0.2, 0.5),
            ("task-int-1", "Code Review, Integration & Deployment Package", "integration", 0.5, 0.2, 0.3)]
    recs, meta = [], {}
    for tid, title, spec, wr, wx, wc in plan:
        best = max(agents_data, key=lambda a: a["Reasoning"] * wr + a["Context"] * wx + a["Coding"] * wc
                                              + (5 if spec in a["specialties"] else 0))
        fit = round(min(100, best["Reasoning"] * wr + best["Context"] * wx + best["Coding"] * wc + (
            5 if spec in best["specialties"] else 0)), 2)
        recs.append({"task_id": tid, "title": title, "assigned_agent": best["name"], "model_used": best["ollama_tag"],
                     "fit_score": fit, "execution_time_seconds": 0.0, "status": "COMPLETED",
                     "reason": "DEMO VERİSİ: gerçek çalıştırma yapılmadı", "attempted_agents": [best["name"]]})
        meta[tid] = {"description": "(demo)", "dependencies": []}
    return {"run_id": "demo", "total_tasks_processed": len(recs), "task_assignments": recs,
            "system_status": "COMPLETED",
            "status_counts": {"COMPLETED": len(recs), "FAILED": 0, "UNASSIGNED": 0, "BLOCKED": 0}}, meta


def build_log(report, skipped=(), decomp_label="", decomp_demo=False):
    lines = [("MASTER", f"Gereksinim motora verildi · run: {report['run_id']}"),
             ("MASTER", f"{report['total_tasks_processed']} görev işlendi" + (
                 " (DEMO VERİSİ)" if report["run_id"] == "demo" else " (MasterOrchestrator)"))]
    if decomp_label:
        lines.append(("CONFIG", f"Görev ayrıştırma kipi: {decomp_label}"))
        if decomp_demo:
            lines.append(("FALLBACK", "Etiketli yedek/tanıtım ayrıştırma verisi devrede"))
    for r in report["task_assignments"]:
        if r["assigned_agent"]:
            lines.append(("ROUTER", f"{r['title']} → {r['assigned_agent']} (FitScore: {r['fit_score']})"))
        lines.append(
            ("ENGINE", f"{r['title']}: {r['status']}" + ("" if r["status"] == "COMPLETED" else f" — {r['reason']}")))
    for s in skipped:
        lines.append(("SYSTEM", f"Uyarı: '{s}' için motor sınıfı yok, atlandı"))
    lines.append(("SYSTEM", f"Sistem durumu: {report['system_status']}"))
    return lines


def current_load():
    by_name = agent_by_name()
    load = {a["Agent ID"]: 0 for a in agents_data}
    for r in (state.report or {}).get("task_assignments", []):
        if r["assigned_agent"] in by_name and r["status"] == "COMPLETED":
            load[by_name[r["assigned_agent"]]["Agent ID"]] += 1
    return load


def mode_badge():
    if state.mode == "demo":
        eng = '<span class="chip chip-cx" style="--c:#FBBF24">DEMO VERİSİ (motor yok)</span>'
    else:
        txt = "CANLI MOTOR · stub ajan çıktısı" if state.stub else "CANLI MOTOR · LLM ajan çıktısı"
        eng = f'<span class="chip chip-cx" style="--c:#34D399">{txt}</span>'
    if state.decomp_label:
        c = "#FBBF24" if state.decomp_demo else "#34D399"
        eng += f' <span class="chip chip-cx" style="--c:{c}">Ayrıştırma: {esc(state.decomp_label)}</span>'
    return eng


def task_card(rec, meta, agent, idx, fresh):
    sc, pct = STATUS_STYLE.get(rec["status"], STATUS_STYLE["IDLE"])
    color = agent["color"] if agent else "#6B7280"
    desc = esc(meta.get("description", ""))
    deps = ", ".join(meta.get("dependencies", [])) or "yok"
    who = (f'<span class="assign">🤖 {esc(rec["assigned_agent"])}<small>FitScore: {rec["fit_score"]}</small></span>'
           if rec["assigned_agent"] else '<span class="assign" style="--c:#6B7280">🤖 atanmadı</span>')
    reason = "" if rec[
                       "status"] == "COMPLETED" else f'<div class="task-desc" style="margin-top:-6px;color:{sc}">⚠ {esc(rec["reason"])}</div>'
    return (
        f'<div class="task-card{" fresh" if fresh else ""}" style="--c:{color}; animation-delay:{idx * 0.15}s">'
        f'<div class="task-head"><span class="task-title">{TASK_ICONS.get(rec["task_id"], "🔹")} {esc(rec["title"])}</span>'
        f'<span><span class="chip chip-cx" style="--c:{sc}">● {rec["status"]}</span> '
        f'<span class="chip">⏱ {rec["execution_time_seconds"]} sn</span></span></div>'
        f'<div class="prog"><div style="width:{pct}%;background:{sc}"></div></div>'
        f'<div class="task-desc">{desc}</div>{reason}'
        f'<div class="task-foot"><span class="chip">Bağımlılık: {esc(deps)}</span>'
        f'<span class="chip">Denenen: {esc(", ".join(rec["attempted_agents"]) or "-")}</span>{who}</div></div>')


def burndown_df(assignments):
    n = len(assignments)
    ideal = [n * (1 - k / n) for k in range(n + 1)]
    actual, rem = [n], n
    for r in assignments:
        if r["status"] == "COMPLETED":
            rem -= 1
            actual.append(rem)
    actual += [None] * (n + 1 - len(actual))
    return pd.DataFrame({"İdeal": ideal, "Gerçek": actual}, index=pd.Index(range(n + 1), name="Tamamlanan görev"))


# ==========================================
# 5. SIDEBAR (ajanlar config'ten, durumlar motor/Ollama'dan)
# ==========================================
with st.sidebar:
    st.markdown("## 🌐 Nexus Core")
    st.caption("Dağıtık multi-agent orkestrasyon motoru")
    st.caption(f"📄 {CONFIG['path_name']} · v{CONFIG['version']} · {CONFIG['retrieved']}")
    st.checkbox("Ollama'da yüklü olmayan modeli OFFLINE say", value=REFLECT_DEFAULT, key="reflect_ollama",
                help="Ajanlar stub (sabit çıktı) iken model gerekmediği için varsayılan kapalı; ajanlar Ollama çağırmaya başlayınca otomatik açılır.")

    st.markdown("### Master Agent")
    m = MASTER
    st.markdown(
        f'<div class="agent-card" style="--c:{m["color"]};">'
        f'<div class="agent-name"><span class="dot" style="--c:{m["color"]}"></span>{esc(m["Agent ID"])}</div>'
        f'<div class="agent-spec">{esc(m["Role"])} · <span style="color:#9CA3AF">Üye: {esc(m["Member"])}</span></div>'
        + skill_bar("Coding", m["Coding"]) + skill_bar("Reasoning", m["Reasoning"]) + skill_bar("Context", m["Context"])
        + f'<div class="agent-spec" style="margin-top:10px">Puanlar: {m["provenance"]}</div></div>',
        unsafe_allow_html=True)

    st.markdown(f"### 🤖 Alt Ajan Havuzu ({len(agents_data)} Worker)")
    for a in agents_data:
        ast_name = agent_status(a)
        ast_color = STATUS_STYLE[ast_name][0]
        st.markdown(
            f'<div class="agent-card" style="--c:{a["color"]}">'
            f'<div class="agent-name"><span class="dot"></span>{esc(a["Agent ID"])}'
            f'<span class="chip chip-cx" style="--c:{ast_color};float:right;font-size:.7em">● {ast_name}</span></div>'
            f'<div class="agent-spec">{esc(a["Role"])} · <span style="color:#9CA3AF">Üye: {esc(a["Member"])}</span></div>'
            + skill_bar("Coding", a["Coding"]) + skill_bar("Reasoning", a["Reasoning"]) + skill_bar("Context",
                                                                                                    a["Context"])
            + f'<div class="agent-spec" style="margin-top:10px">Puanlar: {a["provenance"]} · kayıt: {esc(a["config_status"])}</div></div>',
            unsafe_allow_html=True)

# ==========================================
# 6. ANA EKRAN
# ==========================================
st.markdown(
    '<div class="title-row"><span class="emo">🧿</span><div class="main-header">Distributed AI Platform</div></div>',
    unsafe_allow_html=True)
st.markdown('<div class="sub-header">Sprint 2: Ajan yönetimi, görev ataması ve durum izleme</div>',
            unsafe_allow_html=True)

models_now = ollama_models()
m1, m2, m3, m4 = st.columns(4)
m1.metric("Ollama", "Çevrimiçi" if models_now is not None else "Çevrimdışı")
m2.metric("Aktif Ajan", f"{1 + len(agents_data)} (1 Master + {len(agents_data)} Alt)")
m3.metric("Son çalıştırma", f"{state.elapsed:.2f} sn" if state.elapsed is not None else "Henüz yok")
m4.metric("Sistem durumu", state.report["system_status"].replace("_", " ") if state.report else "—")

components.html(network_html(current_load() if state.report else None,
                             {a["Agent ID"]: agent_status(a) for a in agents_data} if state.report else None),
                height=310)

st.markdown('<div class="section-title">Gereksinim</div>', unsafe_allow_html=True)
requirement_input = st.text_area(
    "Gereksinim:", height=130, label_visibility="collapsed",
    placeholder="Örnek: Kullanıcıların hesap açabileceği, kitap arayabileceği bir kütüphane altyapısı istiyorum...")

if ENGINE_ERROR is not None:
    st.warning(f"Master Agent motoru yüklenemedi ({ENGINE_ERROR}). Sonuçlar DEMO VERİSİ olarak gösterilecek.")

if st.button("🚀 Analiz et ve ajanlara dağıt", use_container_width=True):
    if not requirement_input.strip():
        st.warning("Analiz için önce bir gereksinim metni girin.")
    else:
        with st.spinner("Master Agent gereksinimi ayrıştırıyor..."):
            raw, d_demo, d_label = decompose_task(requirement_input)  # S2-01: etiketli yerel/yedek ayrıştırma
            try:
                state.decomp = normalize_tasks(json.loads(raw), requirement_input)
            except Exception:
                state.decomp = normalize_tasks({}, requirement_input)
                d_demo, d_label = True, "Ayrıştırma Hatası - Güvenli Yedek"
            state.decomp_demo, state.decomp_label = d_demo, d_label
        if ENGINE_ERROR is None:
            live = st.status("Master Agent motoru çalışıyor...", expanded=True)
            try:
                run_engine(requirement_input, live)
            except Exception as e:
                live.update(label="Motor hata verdi", state="error")
                st.error(f"Motor çalıştırılamadı: {type(e).__name__}: {e}")
                st.stop()
            live.update(label="Motor çalıştırması bitti", state="complete")
        else:
            rep, meta = demo_report(requirement_input)
            state.report, state.meta, state.artifacts, state.snapshot = rep, meta, {}, {}
            state.mode, state.stub, state.elapsed, state.requirement = "demo", True, None, requirement_input
            state.log = build_log(rep, (), state.decomp_label, state.decomp_demo)
        state.fresh = True
        st.rerun()

if state.report:
    report = state.report
    assignments = report["task_assignments"]
    by_name = agent_by_name()
    total = len(assignments)
    done = sum(1 for r in assignments if r["status"] == "COMPLETED")

    if state.decomp_demo:
        st.info(f"🛡️ **Aktif Kip: Güvenli Tanıtım / Yedek (Fallback Mode)** — {state.decomp_label}. "
                "Görev ayrıştırma etiketli yedek şablonla yapıldı; ajan atamaları ve durumlar Master Agent motorundan gelir.")
    st.markdown(f'<div class="section-title">Master Agent günlüğü &nbsp;{mode_badge()}</div>', unsafe_allow_html=True)
    components.html(terminal_html(state.log, state.fresh), height=60 + 22 * (len(state.log) + 1))

    st.markdown('<div class="section-title">Görev dağılımı</div>', unsafe_allow_html=True)
    st.progress(done / max(total, 1), text=f"İlerleme: {done} / {total} görev tamamlandı")
    counts = report["status_counts"]
    st.markdown("".join(
        f'<span class="chip chip-cx" style="--c:{STATUS_STYLE[s][0]};margin:0 8px 8px 0;display:inline-block">{s}: {n}</span>'
        for s, n in counts.items()), unsafe_allow_html=True)

    for i, rec in enumerate(assignments):
        agent = by_name.get(rec["assigned_agent"])
        st.markdown(task_card(rec, state.meta.get(rec["task_id"], {}), agent, i, state.fresh), unsafe_allow_html=True)
        art = state.artifacts.get(rec["task_id"])
        if art:
            label = "Ajan çıktısı (stub: sabit örnek çıktı)" if state.stub else "Ajan çıktısı"
            with st.expander(label):
                st.json(art["artifacts"])
                st.code("\n".join(art["logs"]), language="text")
        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

    if state.decomp:
        with st.expander(f"Master Agent görev ayrıştırması (5 aşama) · {state.decomp_label}"):
            st.dataframe(pd.DataFrame([
                {"Aşama": p.replace("_", " "), "Zorluk": d.get("complexity", ""),
                 "Yetenek": d.get("primary_skill_required", ""),
                 "Puan": d.get("story_points", ""), "Açıklama": d.get("description", "")}
                for p, d in state.decomp.items()]), use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Sprint burndown</div>', unsafe_allow_html=True)
    st.caption("Gri çizgi ideal hız, turkuaz çizgi gerçek ilerleme (her görev 1 birim).")
    st.line_chart(burndown_df(assignments), color=["#6B7280", "#00F2FE"], height=260)

    st.markdown('<div class="section-title">Ajan iş yükü (tamamlanan görev)</div>', unsafe_allow_html=True)
    load = current_load()
    peak = max(max(load.values()), 1)
    rows = ""
    for a in agents_data:
        pts = load[a["Agent ID"]]
        rows += (f'<div class="load-row" style="--c:{a["color"]}"><span class="load-name">{esc(a["Agent ID"])}</span>'
                 f'<div class="load-track"><div class="load-fill" style="width:{pts / peak * 100:.0f}%"></div></div>'
                 f'<span class="load-pts">{pts} görev</span></div>')
    st.markdown(rows, unsafe_allow_html=True)

    with st.expander("Atama tablosu (Pandas)"):
        df = pd.DataFrame([{"Görev": r["title"], "Ajan": r["assigned_agent"] or "-", "Model": r["model_used"] or "-",
                            "FitScore": r["fit_score"], "Süre (sn)": r["execution_time_seconds"],
                            "Durum": r["status"], "Neden": r["reason"]} for r in assignments])
        st.dataframe(df, use_container_width=True, hide_index=True)

    state.fresh = False