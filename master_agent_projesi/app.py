import os
import json
import time
import html
import urllib.request
import urllib.error
import socket
import re
import sys
import threading
from pathlib import Path
import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

try:  # S4-03: yeniden deneme / kod inceleme paneli
    import review_panel as rp
except ImportError:  # app.py repo kökünden import edildiğinde (testler)
    from master_agent_projesi import review_panel as rp

try:  # çalıştırmanın dosyalarını proje adıyla zip olarak indirme
    import run_export
except ImportError:  # app.py repo kökünden import edildiğinde (testler)
    from master_agent_projesi import run_export

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
        "endpoint_url": (raw.get("deployment") or {}).get("endpoint_url") or "",
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
    from src.agents.remote_agent import wrap_agent_if_remote, RemoteAgentProxy, get_agent_endpoint_url
    from src.security.input_validation import validate_requirement_text, InputValidationError
    from src.security.output_sanitizer import redact_secrets

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


def agent_endpoint(a):
    """Ajanın uzak işçi adresi (config ya da <ROL>_AGENT_URL ortam değişkeni); yerel ajanda None."""
    if ENGINE_ERROR is not None:
        return None
    return get_agent_endpoint_url(a["id"], a.get("endpoint_url"))


def _check_worker_auth(base_url, timeout=2.0):
    """Korumalı heartbeat ucuna hafif bir istek atarak token uyumunu doğrular."""
    token = (os.getenv("WORKER_AUTH_TOKEN") or os.getenv("BACKEND_AUTH_TOKEN") or "").strip()
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{base_url}/api/v1/agents/heartbeat",
        data=b"{}",
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200, ""
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Yanlış veya eksik WORKER_AUTH_TOKEN (HTTP 401)"
        return True, ""
    except Exception:
        return True, ""


def _normalize_role_key(agent_id: str) -> str:
    """'agent-backend-01', 'agent-backend', 'backend-agent' -> 'backend' olarak normalize eder."""
    s = str(agent_id or "").strip().lower()
    for token in ("backend", "frontend", "database", "testing", "integration", "master"):
        if token in s:
            return token
    return s


def probe_worker(endpoint_url, expected_agent_id=None, timeout=2.0):
    """Uzak işçinin /health adresine bakar; rol/port ve token uyumsuzluğunu tespit eder."""
    base = endpoint_url.rstrip("/")
    try:
        req = urllib.request.Request(f"{base}/health", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not isinstance(data, dict) or str(data.get("status", "")).upper() != "HEALTHY":
            return {"online": False, "agent_status": "OFFLINE", "reason": "sağlıklı değil", "warning": ""}

        actual_id = str(data.get("agent_id") or "")
        actual_name = str(data.get("agent_name") or "")
        actual_role = _normalize_role_key(f"{actual_id} {actual_name}")
        expected_role = _normalize_role_key(expected_agent_id)
        if expected_role and actual_role and actual_role != expected_role:
            shown = actual_name or actual_id
            warn = f"Yanlış rol/port: '{expected_agent_id}' bekleniyordu, '{shown}' ({actual_id}) yanıt verdi!"
            return {"online": False, "agent_status": "OFFLINE", "reason": "yanlış rol/port", "warning": warn}

        if data.get("token_configured") is False:
            warn = "Worker üzerinde WORKER_AUTH_TOKEN tanımlanmamış!"
            return {"online": False, "agent_status": "OFFLINE", "reason": "token eksik", "warning": warn}

        auth_ok, auth_err = _check_worker_auth(base, timeout=timeout)
        if not auth_ok:
            return {"online": False, "agent_status": "OFFLINE", "reason": "yanlış token", "warning": auth_err}

        return {"online": True, "agent_status": str(data.get("agent_status", "IDLE")).upper(), "reason": "", "warning": ""}
    except Exception:
        return {"online": False, "agent_status": "OFFLINE", "reason": "bağlanılamıyor", "warning": ""}


@st.cache_data(ttl=10, show_spinner=False)
def probe_workers(endpoint_pairs):
    """Birden çok uzak işçiyi paralel yoklar: {url: probe_worker sonucu}.
    endpoint_pairs: ((url, expected_agent_id), ...) veya (url, ...)"""
    items = [(p[0], p[1]) if isinstance(p, tuple) else (p, None) for p in endpoint_pairs]
    if not items:
        return {}
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(items)) as pool:
        results = list(pool.map(lambda pair: probe_worker(pair[0], pair[1]), items))
    return {pair[0]: res for pair, res in zip(items, results)}


def backup_note(a):
    """Yerel ajanın modeli bu bilgisayarda yoksa kartta kısa not: ajan yine çalışır ama yedek modda."""
    if agent_endpoint(a) or model_available(a["ollama_tag"], ollama_models()):
        return ""
    return "↳ model yok · yedek mod"


def machine_label(a):
    """Kartta tek kısa satır: sadece uzak işçide hangi makinede çalıştığı; yerel ajanda boş."""
    url = agent_endpoint(a)
    return "🖥 " + url.split("://", 1)[-1].rstrip("/") if url else ""


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

    /* ---------- Kullanılabilirlik katmanı ---------- */
    .stApp::before { opacity: .6; }
    .stApp::after { opacity: .65; }
    .block-container { max-width: 1240px; padding-bottom: 4rem; }
    .stApp p, .stApp li { line-height: 1.6; }
    .section-title { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 1.1rem;
        padding-bottom: 8px; border-bottom: 1px solid #1F2937; }
    .section-hint { color: #8B949E; font-size: .88rem; margin: -4px 0 12px 0; }

    /* Bildirim kutuları (başarı / hata / uyarı / bilgi) */
    div[data-testid="stAlert"] { border-radius: 12px !important; border: 1px solid transparent; }
    div[data-testid="stAlert"] > div { border-radius: 12px !important; }
    div[data-testid="stAlertContentSuccess"] { color: #D1FAE5; }
    div[data-testid="stAlertContentError"] { color: #FEE2E2; }
    div[data-testid="stAlertContentWarning"] { color: #FEF3C7; }
    div[data-testid="stAlertContentInfo"] { color: #DBEAFE; }

    /* Açılır paneller kart gibi */
    div[data-testid="stExpander"] details { background: #0F1524; border: 1px solid #1F2937 !important; border-radius: 12px !important;
        transition: border-color .2s; }
    div[data-testid="stExpander"] details:hover { border-color: #2A3B5F !important; }
    div[data-testid="stExpander"] summary { font-weight: 600; }

    /* Sekmeler */
    div[data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid #1F2937; }
    button[data-baseweb="tab"] { background: #111827 !important; border-radius: 10px 10px 0 0 !important; padding: 10px 18px !important;
        border: 1px solid #1F2937 !important; border-bottom: none !important; }
    button[data-baseweb="tab"][aria-selected="true"] { background: #16213A !important; color: #4FACFE !important; }
    button[data-baseweb="tab"] p { font-weight: 600 !important; font-size: .95rem !important; }

    /* İndirme ve ikincil butonlar */
    div.stDownloadButton > button { border-radius: 10px; border: 1px solid #2A3550; background: #121828; color: #E5E7EB; font-weight: 600; }
    div.stDownloadButton > button:hover { border-color: #4FACFE; color: #4FACFE; }
    div[data-testid="stButtonGroup"] button { border-radius: 999px !important; }

    /* Özet kutucukları */
    .kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 4px 0 14px 0; }
    .kpi { background: #121828; border: 1px solid #1F2937; border-top: 3px solid var(--c); border-radius: 12px; padding: 12px 16px; }
    .kpi b { display: block; font-size: 1.6rem; color: var(--c); line-height: 1.2; }
    .kpi span { color: #9CA3AF; font-size: .82rem; text-transform: uppercase; letter-spacing: .04em; }

    /* Sonuç bandı */
    .result-banner { display: flex; align-items: center; gap: 14px; padding: 14px 18px; border-radius: 12px; margin: 6px 0 16px 0;
        background: color-mix(in srgb, var(--c) 12%, #0F1524); border: 1px solid color-mix(in srgb, var(--c) 45%, transparent); }
    .result-banner .ico { font-size: 1.6rem; }
    .result-banner .t { font-weight: 700; color: #F9FAFB; }
    .result-banner .d { color: #CBD5E1; font-size: .9rem; }

    /* Boş durum: nasıl çalışır */
    .steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; margin: 18px 0 6px 0; }
    .step { background: #0F1524; border: 1px dashed #2A3550; border-radius: 12px; padding: 16px; }
    .step .n { display: inline-flex; width: 26px; height: 26px; border-radius: 50%; align-items: center; justify-content: center;
        background: rgba(79,172,254,.15); color: #4FACFE; font-weight: 800; font-size: .85rem; margin-bottom: 8px; }
    .step .h { font-weight: 700; color: #F3F4F6; margin-bottom: 4px; }
    .step .p { color: #9CA3AF; font-size: .88rem; }

    .char-count { text-align: right; color: #6B7280; font-size: .8rem; margin-top: -6px; }
    .char-count.warn { color: #FBBF24; }
    .task-card:hover { border-color: #2A3B5F; }
    .task-card .task-reason { margin: -6px 0 14px 0; padding: 8px 12px; border-radius: 8px; font-size: .9rem;
        background: color-mix(in srgb, var(--sc) 10%, transparent); color: var(--sc); }
    @media (max-width: 640px) { .main-header { font-size: 2rem; } .assign { margin-left: 0; } .load-name { width: 100px; } }
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


for _k, _v in {"report": None, "meta": {}, "artifacts": {}, "snapshot": {}, "mode": None,
               "elapsed": None, "log": [], "fresh": False, "requirement": "",
               "decomp": None, "decomp_demo": False, "decomp_label": "", "history": [], "attempt_rows": {},
               "plan": None}.items():
    st.session_state.setdefault(_k, _v)
state = st.session_state


def agent_by_id():
    return {a["id"]: a for a in agents_data}


def agent_by_name():
    return {a["name"]: a for a in agents_data}


def agent_status(a):
    """Tek durum, motorun gerçekten yapacağı şeye göre: uzak işçi /health cevap vermiyorsa veya
    rol/port/token hatalıysa OFFLINE (görev almaz)."""
    url = agent_endpoint(a)
    if url:
        probe = probe_workers(((url, a["id"]),)).get(url)
        if not probe or not probe["online"]:
            return "OFFLINE"
        raw = state.snapshot.get(a["id"]) or probe["agent_status"]
    else:
        raw = state.snapshot.get(a["id"]) or "IDLE"
    raw = "FAILED" if raw == "ERROR" else raw
    return raw if raw in STATUS_STYLE else "IDLE"


MODEL_MODES = {"ollama", "ollama_inference"}
BACKUP_MODES = {"template", "fallback", "safe_fallback"}


def output_source(artifacts):
    """Where a task's output really came from, read from the agent's own result
    (same for local and remote agents): "model" = generated by the Ollama model,
    "backup" = labelled template / fallback, "check" = static review without a model
    (IntegrationAgent), None = unknown."""
    a = artifacts if isinstance(artifacts, dict) else {}
    if "inspected_files" in a:  # IntegrationAgent: model review, or code check only
        return "model" if a.get("model_used") else "check"
    if a.get("fallback_reason"):
        return "backup"
    mode = str(a.get("generation_mode") or a.get("synthesis_mode") or "").lower()
    if mode in MODEL_MODES:
        return "model"
    if mode in BACKUP_MODES:
        return "backup"
    return None


def output_label(artifacts):
    """Expander title for one task's output."""
    a = artifacts if isinstance(artifacts, dict) else {}
    source = output_source(a)
    if source == "model":
        model = a.get("model_used") or a.get("model")
        return f"Ajan çıktısı · gerçek model ({model})" if model else "Ajan çıktısı · gerçek model"
    if source == "backup":
        reason = a.get("fallback_reason")
        return f"Ajan çıktısı · yedek şablon ({reason})" if reason else "Ajan çıktısı · yedek şablon"
    if source == "check":
        reason = a.get("fallback_reason")
        if reason:
            return f"Ajan çıktısı · kod kontrolü (model kullanılamadı: {reason})"
        return "Ajan çıktısı · kod kontrolü (model kullanılmadı)"
    return "Ajan çıktısı"


def output_summary(artifacts_by_task):
    """(badge text, color) for the whole run, from what the agents actually returned."""
    sources = [output_source((v or {}).get("artifacts")) for v in (artifacts_by_task or {}).values()]
    n_model, n_backup = sources.count("model"), sources.count("backup")
    if n_backup and n_model:
        return f"CANLI MOTOR · {n_model} görev gerçek model, {n_backup} görev yedek şablon", "#FBBF24"
    if n_backup:
        return "CANLI MOTOR · yedek şablon çıktısı", "#FBBF24"
    if n_model:
        return "CANLI MOTOR · gerçek model çıktısı", "#34D399"
    return "CANLI MOTOR", "#34D399"


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
        inst = wrap_agent_if_remote(inst, endpoint_url=a.get("endpoint_url"))
        out.append(inst)
    return out, skipped


def remote_start_problem(ag):
    """Görev dağıtılmadan önce uzak işçinin sorunu: cevap yok, yanlış rol/port ya da token. Sorun yoksa "".
    Sorun varsa ajan OFFLINE yapılır; böylece kartta görünen uyarı motorda da geçerli olur (yanlış role görev gitmez)."""
    ag.check_health()
    if ag.status == AgentStatus.OFFLINE:
        return "yanıt vermiyor"
    warning = probe_worker(ag.endpoint_url, ag.agent_id, timeout=3.0).get("warning")
    if warning:
        ag.status = AgentStatus.OFFLINE
        return warning
    return ""


def run_engine(requirement, live):
    """Gerçek MasterOrchestrator'ı çalıştırır; sonucu session_state'e yazar."""
    agents, skipped = build_agents()
    for ag in agents:  # uzak işçiler: görev dağıtılmadan önce /health, rol ve token kontrolü
        if isinstance(ag, RemoteAgentProxy):
            problem = remote_start_problem(ag)
            if problem:
                if ag.fallback_to_local:
                    ag.status = AgentStatus.IDLE  # yerel yedek devreye girer
                    live.write(f"⚪ {ag.name}: {ag.endpoint_url} {problem} → yerel yedek kullanılacak")
                else:
                    live.write(f"⚪ {ag.name}: {ag.endpoint_url} {problem} → OFFLINE, görev almayacak")
            else:
                live.write(f"🔗 {ag.name}: {ag.endpoint_url} → ONLINE")
    ui_ctx = get_script_run_ctx()  # S4-07: paralel görevler başka thread'den yazar, Streamlit bağlamı gerekir
    ui_lock = threading.Lock()
    for ag in agents:  # canlı BUSY/sonuç satırları için sarmalayıcı
        orig = ag.execute_task

        def wrapped(task, _ag=ag, _orig=orig):
            if ui_ctx is not None and get_script_run_ctx(suppress_warning=True) is None:
                add_script_run_ctx(threading.current_thread(), ui_ctx)
            return _run_with_live_log(task, _ag, _orig)

        def _run_with_live_log(task, _ag, _orig):
            with ui_lock:
                live.write(f"🟡 {_ag.name} → BUSY ({task.get('title')})")
                set_card_status(_ag.agent_id, "BUSY")
            try:
                res = _orig(task)
            finally:
                with ui_lock:
                    set_card_status(_ag.agent_id, CARD_STATUS.get(_ag.agent_id, "IDLE"))
            with ui_lock:
                _write_result(res, _ag)
            return res

        def _write_result(res, _ag):
            live.write(
                f"{'🟢' if res.status == 'SUCCESS' else '🔴'} {_ag.name} → {res.status} ({res.execution_time_seconds} sn)")
            if res.status == "SUCCESS":
                names = [f.get("filename") or f.get("path") for f in (res.output_artifacts or {}).get("files") or []
                         if isinstance(f, dict)]
                if names:
                    live.write(f"📄 Üretilen dosya: {', '.join(str(n) for n in names)}")
            elif res.error_message:
                live.write(f"↳ Başarısız: {res.error_message}")

        ag.execute_task = wrapped
    title = " ".join(requirement.split())[:60] or "Generated Software System"
    # S4-07: görevleri Master modeli (qwen2.5:7b) böler; MASTER_ANALYZER_USE_OLLAMA=false ise sabit şablon
    use_llm = os.getenv("MASTER_ANALYZER_USE_OLLAMA", "true").strip().lower() not in ("0", "false", "no", "off")
    live.write(f"🧠 Master Agent ({OLLAMA_MODEL}) gereksinimi görevlere bölüyor..." if use_llm
               else "📋 Görevler sabit şablondan alınıyor (MASTER_ANALYZER_USE_OLLAMA=false)")
    orch = MasterOrchestrator(evaluator=CapabilityEvaluator(agents),  # çalıştırma state.db'ye yazılır (S2-07)
                              analyzer=RequirementsAnalyzer(use_llm=use_llm, model=OLLAMA_MODEL, host=OLLAMA_HOST))
    t0 = time.perf_counter()
    report = orch.process_requirement(requirement, title)
    elapsed = time.perf_counter() - t0
    plan = report.get("decomposition") or {}
    state.plan = plan
    state.meta = {t["task_id"]: t for t in plan.get("tasks") or []}
    state.decomp_label = plan.get("label") or ""
    state.decomp_demo = plan.get("mode") != "llm"
    state.artifacts = {r.task_id: {"artifacts": r.output_artifacts, "logs": r.logs}
                       for r in orch.execution_history if r.status == "SUCCESS"}
    state.history = list(orch.execution_history)  # başarısız denemeler dahil (S4-03)
    state.attempt_rows = rp.attempt_rows(state.history, agents)
    state.snapshot = {ag.agent_id: ag.status.value for ag in agents}
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


# Ajanın üretim kipi -> (etiket, renk). Yedek/şablon çıktı asla "model çıktısı" gibi gösterilmez.
GEN_MODE_LABELS = {
    "ollama": ("Model çıktısı", "#34D399"),
    "ollama_inference": ("Model çıktısı", "#34D399"),
    "fallback": ("Yedek şablon · model çıktısı değil", "#FBBF24"),
    "safe_fallback": ("Yedek şablon · model çıktısı değil", "#FBBF24"),
    "template": ("Şablon · Ollama kapalı", "#FBBF24"),
}
CODE_LANGUAGES = {".html": "html", ".css": "css", ".js": "javascript", ".py": "python", ".sql": "sql",
                  ".json": "json", ".md": "markdown"}


def generated_file_rows(report, artifacts):
    """Master'ın workspaces/<run_id>/ altına yazdığı dosyalar (görev kaydındaki output_files)."""
    workspace = report.get("workspace_path")
    rows = []
    for rec in report.get("task_assignments", []):
        art = ((artifacts or {}).get(rec["task_id"]) or {}).get("artifacts") or {}
        contents = {}
        for f in art.get("files") or []:
            if isinstance(f, dict):
                contents[str(f.get("filename") or f.get("path") or "").replace("\\", "/")] = f.get("content")
        mode = art.get("generation_mode") or art.get("synthesis_mode")
        for rel in rec.get("output_files") or []:
            rows.append({"task": rec["title"], "agent": rec["assigned_agent"] or "-", "file": rel,
                         "path": str(Path(workspace) / rel) if workspace else rel,
                         "mode": mode, "content": contents.get(rel)})
    return rows


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


def render_smoke_test(smoke):
    """S5: did the generated backend really start and answer the contract's endpoints? (MASTER_SMOKE_TEST)"""
    if not smoke:
        return
    icon = {"PASSED": "✅", "FAILED": "❌"}.get(smoke.get("status"), "⏭️")
    with st.expander(f"{icon} Üretilen uygulamanın duman testi · {smoke.get('status')} · {smoke.get('reason', '')}"):
        rows = [{"Uç nokta": f"{c['method']} {c['path']}", "HTTP": c["status_code"],
                 "Sonuç": "çalıştı" if c["ok"] else (c.get("error") or "sunucu hatası")}
                for c in smoke.get("checks") or []]
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        if smoke.get("backend_file"):
            st.caption(f"Denenen dosya: {smoke['backend_file']} (çalışma alanının geçici kopyasında)")


def render_generated_tests(result):
    """S5-06: pass rate of the Testing Agent's tests against the generated backend (MASTER_SMOKE_TEST)."""
    if not result:
        return
    icon = {"PASSED": "✅", "FAILED": "❌"}.get(result.get("status"), "⏭️")
    with st.expander(f"{icon} Üretilen testlerin geçme oranı · {result.get('status')} · {result.get('reason', '')}"):
        rate = result.get("pass_rate")
        cols = st.columns(4)
        cols[0].metric("Geçme oranı", "—" if rate is None else f"%{rate * 100:.0f}")
        cols[1].metric("Geçen", result.get("passed", 0))
        cols[2].metric("Kalan / hata", (result.get("failed") or 0) + (result.get("errors") or 0))
        cols[3].metric("Test modeli", result.get("model_used") or "—")
        rows = [{"Test": c.get("name"), "Sonuç": c.get("outcome"), "Mesaj": c.get("message") or ""}
                for c in result.get("cases") or []]
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)


def render_plan(plan):
    """S4-07: Master'ın bu çalıştırmada kullandığı görev planı ve ajanlara giden ortak sözleşme."""
    is_llm = plan.get("mode") == "llm"
    title = "Master Agent planı · " + (plan.get("label") or ("Yerel model" if is_llm else "Sabit şablon"))
    with st.expander(title):
        if not is_llm:
            st.caption("Model kullanılamadığı için sabit 6 görevlik şablon çalıştı"
                       + (f" (sebep: {plan.get('fallback_reason')})." if plan.get("fallback_reason") else "."))
        td = "padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.08);vertical-align:top;"
        rows = "".join(
            f'<tr><td style="{td}white-space:nowrap;font-weight:600">{esc(t.get("task_id", ""))}</td>'
            f'<td style="{td}white-space:nowrap">{esc(t.get("category", ""))}</td>'
            f'<td style="{td}">{esc(t.get("title", ""))}</td>'
            f'<td style="{td}white-space:nowrap">{esc(", ".join(t.get("dependencies") or []) or "-")}</td></tr>'
            for t in plan.get("tasks") or [])
        head = "".join(f'<th style="{td}text-align:left;color:#9CA3AF;white-space:nowrap">{h}</th>'
                       for h in ("Görev", "Kategori", "Başlık", "Bağımlılık"))
        st.markdown('<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:.9em">'
                    f'<thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
        contract = plan.get("shared_contract") or {}
        if contract:
            st.markdown("**Ajanlara giden ortak sözleşme**")
            for ent in contract.get("entities") or []:
                fields = ", ".join(f'{f.get("name")} ({f.get("type")})' for f in ent.get("fields") or [])
                st.markdown(f"- `{esc(ent.get('table', ''))}` ({esc(ent.get('name', ''))}): {esc(fields)}")
            for ep in contract.get("endpoints") or []:
                st.markdown(f"- `{esc(ep.get('method', ''))} {esc(ep.get('path', ''))}` {esc(ep.get('description', ''))}")
        elif is_llm:
            st.caption("Model ortak sözleşme döndürmedi.")


def mode_badge():
    if state.mode == "demo":
        eng = '<span class="chip chip-cx" style="--c:#FBBF24">DEMO VERİSİ (motor yok)</span>'
    else:
        txt, color = output_summary(state.artifacts)
        eng = f'<span class="chip chip-cx" style="--c:{color}">{esc(txt)}</span>'
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
    reason = "" if rec["status"] == "COMPLETED" or not rec.get("reason") else (
        f'<div class="task-reason" style="--sc:{sc}">⚠ {esc(rec["reason"])}</div>')
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


CARD_SLOTS, CARD_STATUS = {}, {}


def agent_card_html(a, ast_name):
    """Sidebar ajan kartı; rol/port veya token uyuşmazlığı varsa kartta uyarı gösterir."""
    ast_color = STATUS_STYLE[ast_name][0]
    label = f"ONLINE - {ast_name}" if ast_name in ("IDLE", "BUSY") else ast_name
    machine = machine_label(a) or backup_note(a)
    url = agent_endpoint(a)
    warn_msg = ""
    if url:
        probe = probe_workers(((url, a["id"]),)).get(url) or {}
        warn_msg = probe.get("warning", "")
    return (
        f'<div class="agent-card" style="--c:{a["color"]}">'
        f'<div class="agent-name"><span class="dot"></span>{esc(a["Agent ID"])}'
        f'<span class="chip chip-cx" style="--c:{ast_color};float:right;font-size:.7em">● {label}</span></div>'
        f'<div class="agent-spec">{esc(a["Role"])} · <span style="color:#9CA3AF">Üye: {esc(a["Member"])}</span></div>'
        + (f'<div class="agent-spec" style="color:#9CA3AF">{esc(machine)}</div>' if machine else "")
        + (f'<div class="agent-spec" style="color:#F87171;font-weight:600">⚠️ {esc(warn_msg)}</div>' if warn_msg else "")
        + skill_bar("Coding", a["Coding"]) + skill_bar("Reasoning", a["Reasoning"]) + skill_bar("Context", a["Context"])
        + f'<div class="agent-spec" style="margin-top:10px">Puanlar: {a["provenance"]} · kayıt: {esc(a["config_status"])}</div></div>')


def set_card_status(agent_id, ast_name):
    """Çalışma sırasında kartı canlı günceller (kart yoksa sessizce geçer)."""
    slot, a = CARD_SLOTS.get(agent_id), agent_by_id().get(agent_id)
    if slot is not None and a is not None:
        slot.markdown(agent_card_html(a, ast_name), unsafe_allow_html=True)


# ==========================================
# 5. SIDEBAR (ajanlar config'ten, durumlar motor/Ollama'dan)
# ==========================================
with st.sidebar:
    st.markdown("## 🌐 Nexus Core")
    st.caption("Dağıtık multi-agent orkestrasyon motoru")
    st.caption(f"📄 {CONFIG['path_name']} · v{CONFIG['version']} · {CONFIG['retrieved']}")
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
    _pairs = tuple((agent_endpoint(x), x["id"]) for x in agents_data if agent_endpoint(x))
    _worker_warnings = []
    if _pairs:
        _p = probe_workers(_pairs)
        st.caption(f"🔗 Uzak işçiler: {sum(1 for u, _ in _pairs if _p[u]['online'])}/{len(_pairs)} ONLINE")
        for x in agents_data:
            u = agent_endpoint(x)
            if u and _p.get(u, {}).get("warning"):
                _worker_warnings.append(f"**{x['name']}** (`{u}`): {_p[u]['warning']}")
    for a in agents_data:
        CARD_SLOTS[a["id"]] = st.empty()  # çalışma sırasında kart BUSY'ye döner, bitince geri döner
        CARD_STATUS[a["id"]] = agent_status(a)
        CARD_SLOTS[a["id"]].markdown(agent_card_html(a, CARD_STATUS[a["id"]]), unsafe_allow_html=True)

# ==========================================
# 6. ANA EKRAN
# ==========================================
st.markdown(
    '<div class="title-row"><span class="emo">🧿</span><div class="main-header">Distributed AI Platform</div></div>',
    unsafe_allow_html=True)
st.markdown('<div class="sub-header">Gereksinimden koda: dağıtık ajanlarla görev ayrıştırma, atama ve izleme</div>',
            unsafe_allow_html=True)

for _w in _worker_warnings:
    st.error(f"🚨 Worker Yapılandırma Uyarısı — {_w}")

models_now = ollama_models()
m1, m2, m3, m4 = st.columns(4)
m1.metric("Ollama", "Çevrimiçi" if models_now is not None else "Çevrimdışı")
m2.metric("Aktif Ajan", f"{1 + len(agents_data)} (1 Master + {len(agents_data)} Alt)")
m3.metric("Son çalıştırma", f"{state.elapsed:.2f} sn" if state.elapsed is not None else "Henüz yok")
m4.metric("Sistem durumu", state.report["system_status"].replace("_", " ") if state.report else "—")

components.html(network_html(current_load() if state.report else None,
                             {a["Agent ID"]: agent_status(a) for a in agents_data} if state.report else None),
                height=310)

EXAMPLE_REQUIREMENTS = {
    "📚 Kütüphane": "Kullanıcıların hesap açabileceği, kitap arayabileceği, ödünç alıp iade edebileceği bir kütüphane "
                   "yönetim sistemi istiyorum. Yöneticiler kitap ekleyip silebilmeli.",
    "✅ Görev takibi": "Ekiplerin görev oluşturup kişilere atayabileceği, durumunu (yapılacak / sürüyor / bitti) "
                      "güncelleyebileceği basit bir görev takip uygulaması istiyorum.",
    "🛒 E-ticaret": "Ürünlerin listelendiği, kullanıcıların sepete ürün ekleyip sipariş verebileceği ve "
                   "siparişlerini görüntüleyebileceği küçük bir e-ticaret altyapısı istiyorum.",
}
REQ_MAX = 50_000


def _use_example():
    """Örnek seçildiğinde gereksinim kutusunu doldurur, seçimi sıfırlar (tekrar seçilebilsin)."""
    choice = st.session_state.get("req_example")
    if choice:
        st.session_state["req_text"] = EXAMPLE_REQUIREMENTS[choice]
    st.session_state["req_example"] = None


st.markdown('<div class="section-title">📝 Gereksinim</div>', unsafe_allow_html=True)
st.markdown('<div class="section-hint">Ne inşa etmek istediğinizi düz bir dille yazın; Master Agent bunu görevlere bölüp '
            'uygun ajanlara dağıtır. Hızlı başlamak için bir örnek seçebilirsiniz.</div>', unsafe_allow_html=True)
st.pills("Örnek gereksinimler", list(EXAMPLE_REQUIREMENTS), key="req_example", on_change=_use_example,
         label_visibility="collapsed")
requirement_input = st.text_area(
    "Gereksinim:", height=150, label_visibility="collapsed", key="req_text",
    placeholder="Örnek: Kullanıcıların hesap açabileceği, kitap arayabileceği bir kütüphane altyapısı istiyorum...")
_n = len(requirement_input or "")
st.markdown(f'<div class="char-count{" warn" if _n > REQ_MAX else ""}">'
            f'{_n:,} / {REQ_MAX:,} karakter</div>'.replace(",", "."), unsafe_allow_html=True)

if ENGINE_ERROR is not None:
    st.warning(f"Master Agent motoru yüklenemedi ({ENGINE_ERROR}). Sonuçlar DEMO VERİSİ olarak gösterilecek.")

if st.button("🚀 Analiz et ve ajanlara dağıt", use_container_width=True, type="primary"):
    try:
        cleaned_req = validate_requirement_text(requirement_input) if ENGINE_ERROR is None else requirement_input.strip()
        if not cleaned_req:
            st.warning("✍️ Analiz için önce bir gereksinim metni girin ya da yukarıdan bir örnek seçin.")
            st.stop()
    except InputValidationError as val_err:
        st.warning(f"⚠️ {val_err.reason}")
        st.stop()

    state.decomp, state.plan, state.decomp_label, state.decomp_demo = None, None, "", False
    if ENGINE_ERROR is not None:  # motor yoksa eski etiketli 5 aşamalı ayrıştırma (DEMO)
        with st.spinner("Master Agent gereksinimi ayrıştırıyor..."):
            raw, d_demo, d_label = decompose_task(cleaned_req)  # S2-01: etiketli yerel/yedek ayrıştırma
            try:
                state.decomp = normalize_tasks(json.loads(raw), cleaned_req)
            except Exception:
                state.decomp = normalize_tasks({}, cleaned_req)
                d_demo, d_label = True, "Ayrıştırma Hatası - Güvenli Yedek"
            state.decomp_demo, state.decomp_label = d_demo, d_label
    if ENGINE_ERROR is None:
        live = st.status("Master Agent motoru çalışıyor...", expanded=True)
        try:
            run_engine(cleaned_req, live)
        except Exception as e:
            live.update(label="Motor hata verdi", state="error")
            safe_err = redact_secrets(f"{type(e).__name__}: {e}") if ENGINE_ERROR is None else f"{type(e).__name__}: {e}"
            st.error(f"❌ Motor çalıştırılamadı: {safe_err}")
            st.stop()
        live.update(label="Motor çalıştırması bitti", state="complete")
    else:
        rep, meta = demo_report(cleaned_req)
        state.report, state.meta, state.artifacts, state.snapshot = rep, meta, {}, {}
        state.history, state.attempt_rows = [], {}
        state.mode, state.elapsed, state.requirement = "demo", None, cleaned_req
        state.log = build_log(rep, (), state.decomp_label, state.decomp_demo)
    state.fresh = True
    st.rerun()

if not state.report:
    st.markdown(
        '<div class="steps">'
        '<div class="step"><div class="n">1</div><div class="h">Gereksinimi yazın</div>'
        '<div class="p">Ne istediğinizi birkaç cümleyle anlatın ya da bir örnek seçin.</div></div>'
        '<div class="step"><div class="n">2</div><div class="h">Master ayrıştırır</div>'
        '<div class="p">Gereksinim veritabanı, backend, frontend, test ve entegrasyon görevlerine bölünür.</div></div>'
        '<div class="step"><div class="n">3</div><div class="h">Ajanlar üretir</div>'
        '<div class="p">Her görev en uygun ajana (FitScore) atanır; hata olursa yeniden denenir ya da devredilir.</div></div>'
        '<div class="step"><div class="n">4</div><div class="h">Sonucu indirin</div>'
        '<div class="p">Üretilen dosyaları inceleyin, test sonuçlarını görün ve projeyi zip olarak indirin.</div></div>'
        '</div>', unsafe_allow_html=True)

if state.report:
    report = state.report
    assignments = report["task_assignments"]
    by_name = agent_by_name()
    total = len(assignments)
    done = sum(1 for r in assignments if r["status"] == "COMPLETED")
    counts = report["status_counts"]
    n_failed = sum(n for s, n in counts.items() if s in ("FAILED", "BLOCKED", "UNASSIGNED"))

    # ---- Sonuç özeti ----
    st.markdown(f'<div class="section-title">📊 Sonuç &nbsp;{mode_badge()}</div>', unsafe_allow_html=True)
    if total and done == total:
        b_ico, b_col, b_t = "✅", "#34D399", "Tüm görevler başarıyla tamamlandı"
    elif done:
        b_ico, b_col, b_t = "⚠️", "#FBBF24", "Görevlerin bir kısmı tamamlanamadı"
    else:
        b_ico, b_col, b_t = "❌", "#F87171", "Hiçbir görev tamamlanamadı"
    b_d = (f"{done} / {total} görev tamamlandı"
           + (f" · {state.elapsed:.2f} sn" if state.elapsed is not None else "")
           + (" · nedenleri Görevler sekmesindeki kartlarda" if n_failed else ""))
    st.markdown(f'<div class="result-banner" style="--c:{b_col}"><span class="ico">{b_ico}</span>'
                f'<div><div class="t">{b_t}</div><div class="d">{esc(b_d)}</div></div></div>', unsafe_allow_html=True)
    if state.fresh:
        st.toast(f"{b_ico} {b_t} ({done}/{total})")

    st.markdown('<div class="kpi-row">'
                + f'<div class="kpi" style="--c:#4FACFE"><b>{total}</b><span>Toplam görev</span></div>'
                + "".join(f'<div class="kpi" style="--c:{STATUS_STYLE.get(s, STATUS_STYLE["IDLE"])[0]}">'
                          f'<b>{n}</b><span>{esc(s)}</span></div>' for s, n in counts.items())
                + '</div>', unsafe_allow_html=True)
    st.progress(done / max(total, 1), text=f"İlerleme: {done} / {total} görev tamamlandı")

    if state.decomp_demo:
        st.info(f"🛡️ **Aktif Kip: Güvenli Tanıtım / Yedek (Fallback Mode)** — {state.decomp_label}. "
                "Görev ayrıştırma etiketli yedek şablonla yapıldı; ajan atamaları ve durumlar Master Agent motorundan gelir.")

    with st.expander(f"🖥️ Master Agent günlüğü ({len(state.log)} satır)", expanded=state.fresh):
        components.html(terminal_html(state.log, state.fresh), height=60 + 22 * (len(state.log) + 1))

    file_rows = generated_file_rows(report, state.artifacts) if state.mode == "engine" else []
    tab_labels = (["📁 Üretilen dosyalar"] if state.mode == "engine" else []) + [
        "📋 Görevler", "🧪 Kalite & test", "📈 Plan & analiz"]
    tabs = dict(zip(tab_labels, st.tabs(tab_labels)))

    # ---- Görevler ----
    with tabs["📋 Görevler"]:
        for i, rec in enumerate(assignments):
            agent = by_name.get(rec["assigned_agent"])
            st.markdown(task_card(rec, state.meta.get(rec["task_id"], {}), agent, i, state.fresh), unsafe_allow_html=True)
            rp.render_task_attempts(st, rec["task_id"], state.attempt_rows, rec.get("attempted_agents"))
            art = state.artifacts.get(rec["task_id"])
            if art:
                label = output_label(art["artifacts"])
                with st.expander(label):
                    st.json(art["artifacts"])
                    raw_logs = "\n".join(art["logs"])
                    st.code(redact_secrets(raw_logs) if ENGINE_ERROR is None else raw_logs, language="text")
            st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

    # ---- Üretilen dosyalar ----
    if state.mode == "engine":
        with tabs["📁 Üretilen dosyalar"]:
            if file_rows:
                zip_name, zip_bytes, zip_count = run_export.build_run_zip(
                    report.get("project_title"), file_rows, fallback_name=str(report.get("run_id") or "proje"))
                c1, c2 = st.columns([3, 2], vertical_alignment="center")
                c1.markdown(f"**{len(file_rows)} dosya üretildi**")
                if report.get("workspace_path"):
                    c1.caption(f"Çalışma alanı: {report['workspace_path']}")
                if zip_count:
                    c2.download_button(f"📦 Tümünü zip olarak indir ({zip_count} dosya)", zip_bytes,
                                       file_name=zip_name, mime="application/zip", type="primary",
                                       use_container_width=True, on_click="ignore",
                                       key=f"zip-{report['run_id']}")
                for i, row in enumerate(file_rows):
                    mode_txt, mode_color = GEN_MODE_LABELS.get(row["mode"], ("Üretim kipi bilinmiyor", "#6B7280"))
                    with st.expander(f"📄 {row['file']} · {row['task']}"):
                        st.markdown(f'<span class="chip chip-cx" style="--c:{mode_color}">{esc(mode_txt)}</span> '
                                    f'<span class="chip">🤖 {esc(row["agent"])}</span>', unsafe_allow_html=True)
                        st.caption(row["path"])
                        if row["content"]:
                            st.code(row["content"][:20000], language=CODE_LANGUAGES.get(Path(row["file"]).suffix.lower()))
                            st.download_button("⬇️ İndir", row["content"], file_name=Path(row["file"]).name,
                                               on_click="ignore", key=f"dl-{report['run_id']}-{i}")
                        else:
                            st.caption("Dosya içeriği okunamadı.")
            else:
                st.info("📭 Bu çalıştırmada diske yazılmış dosya yok (tamamlanan görev yok ya da çıktı dosya içermiyor).")

    # ---- Kalite & test ----
    with tabs["🧪 Kalite & test"]:
        if state.mode == "engine":
            rp.render_review_panel(st, report, state.history)
            render_smoke_test(report.get("smoke_test"))
        render_generated_tests(report.get("generated_tests"))
        if state.mode != "engine" and not report.get("generated_tests"):
            st.info("Kod inceleme ve test sonuçları yalnızca canlı motor çalıştırmalarında üretilir.")

    # ---- Plan & analiz ----
    with tabs["📈 Plan & analiz"]:
        if state.plan:
            render_plan(state.plan)

        if state.decomp:
            with st.expander(f"Master Agent görev ayrıştırması (5 aşama) · {state.decomp_label}"):
                # Küçük sütunlar tek satır, açıklama kısaltılır (tamamı fareyle üstüne gelince), tablo yana kayar
                def _short(t, n=110):
                    t = " ".join(str(t).split())
                    return t if len(t) <= n else t[:n].rstrip() + "…"

                _td = "padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.08);vertical-align:top;"
                rows = "".join(
                    f'<tr><td style="{_td}white-space:nowrap;font-weight:600">{esc(p.replace("_", " "))}</td>'
                    f'<td style="{_td}white-space:nowrap">{esc(d.get("complexity", ""))}</td>'
                    f'<td style="{_td}white-space:nowrap">{esc(d.get("primary_skill_required", ""))}</td>'
                    f'<td style="{_td}white-space:nowrap;text-align:center">{esc(d.get("story_points", ""))}</td>'
                    f'<td style="{_td}min-width:320px;color:#D1D5DB" title="{esc(d.get("description", ""))}">'
                    f'{esc(_short(d.get("description", "")))}</td></tr>'
                    for p, d in state.decomp.items())
                head = "".join(f'<th style="{_td}text-align:left;color:#9CA3AF;white-space:nowrap">{h}</th>'
                               for h in ("Aşama", "Zorluk", "Yetenek", "Puan", "Açıklama"))
                st.markdown('<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:.9em">'
                            f'<thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)

        g1, g2 = st.columns(2, gap="large")
        with g1:
            st.markdown('<div class="section-title">Sprint burndown</div>', unsafe_allow_html=True)
            st.caption("Gri çizgi ideal hız, turkuaz çizgi gerçek ilerleme (her görev 1 birim).")
            st.line_chart(burndown_df(assignments), color=["#6B7280", "#00F2FE"], height=260)
        with g2:
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
