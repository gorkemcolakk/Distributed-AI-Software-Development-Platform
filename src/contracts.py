"""
Master–Worker & Integration Inter-Agent Contracts (v1.0).

S2-04 (Elif Yılmaz) & S3-01 (Eren Görkem Çolak):
- Versioned Pydantic schemas (contract_version = "1.0") for task envelopes,
  worker results, orchestrator records, worker errors, and integration reports.
- Explicit run_id, task_id, category, dependencies, payload, timestamps,
  envelope_id, and timeout_seconds in task envelopes.
- Status normalization between Worker ("SUCCESS" / "COMPLETED") and Orchestrator.
- Thread-safe DuplicateTaskTracker for idempotent duplicate message handling.
"""

from enum import Enum
import threading
import time
from typing import Dict, Any, List, Optional, Tuple
import uuid
from pydantic import BaseModel, Field, ValidationError

CONTRACT_VERSION = "1.0"
DEFAULT_TASK_TIMEOUT_SECONDS = 180.0


# =====================================================================
# 1. DURUM VE HATA KODU TANIMLARI (Worker vs Orchestrator Ayrımı)
# =====================================================================
class WorkerTaskStatus(str, Enum):
    """İşçi ajanın (BaseAgent / TaskResult / HTTP Worker) döndürebileceği durumlar."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class OrchestratorTaskStatus(str, Enum):
    """Master Orchestrator'ın raporlayabileceği durumlar (UNASSIGNED ve BLOCKED dahil)."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNASSIGNED = "UNASSIGNED"
    BLOCKED = "BLOCKED"


class WorkerErrorCode(str, Enum):
    """Dağıtık Master–Worker haberleşmesinde standart hata kodları (S3-01)."""
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    TIMEOUT = "TIMEOUT"
    DUPLICATE_TASK = "DUPLICATE_TASK"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    UNREACHABLE = "UNREACHABLE"
    UNSAFE_PATH = "UNSAFE_PATH"
    CONTRACT_VIOLATION = "CONTRACT_VIOLATION"


def normalize_worker_status(status: Any) -> str:
    """
    Worker katmanındaki 'COMPLETED' ve 'SUCCESS' durumlarını çekirdek motor ve
    SQLite kısıtlarıyla (tasks.agent_result_status IN ('SUCCESS', 'FAILED'))
    birebir uyumlu olacak şekilde 'SUCCESS' veya 'FAILED' olarak normalize eder.
    """
    raw = getattr(status, "value", str(status or "")).strip().upper()
    if raw in ("SUCCESS", "COMPLETED"):
        return "SUCCESS"
    if raw in ("FAILED", "ERROR", "REJECTED"):
        return "FAILED"
    return raw or "FAILED"


# =====================================================================
# 2. MASTER MOTORU GÖREV SINIFLANDIRMA ŞEMASI
# =====================================================================
class MasterSubTaskSchema(BaseModel):
    """Master motorunun (orchestrator) çalıştığı gerçek görev şeması."""
    task_id: str = Field(..., min_length=1, description="Alt görevin benzersiz kimliği")
    title: str = Field(..., min_length=2, description="Görev başlığı")
    category: str = Field(..., min_length=2, description="Görev kategorisi (backend, frontend, database, testing vb.)")
    description: str = Field(..., min_length=5, description="Görevin teknik açıklaması")
    dependencies: List[str] = Field(default_factory=list, description="Bağımlı olduğu task_id listesi")
    required_specialty: str = Field(..., min_length=2, description="Gereken ajan uzmanlığı")


class LegacyClassificationItemSchema(BaseModel):
    """app.py arayüzündeki 5 sabit kategorili şema desteği (Geriye dönük uyumluluk)."""
    description: str = Field(..., min_length=5)
    complexity: str = Field(default="Medium")
    primary_skill_required: str = Field(default="Reasoning")
    story_points: int = Field(default=3, ge=1, le=21)


def validate_master_tasks(tasks_data: Any) -> Tuple[bool, Optional[str], List[Dict[str, Any]]]:
    """
    Master Agent'ın ürettiği görev listesini (veya sözlüğünü) doğrular.
    Geçerliyse (True, None, doğrulanmış_liste), hatalıysa (False, hata_mesajı, []) döner.
    """
    if not tasks_data:
        return False, "Görev listesi boş veya geçersiz.", []

    try:
        # 1. Durum: Master Motoru formatı (Liste halinde görevler veya {"tasks": [...]})
        task_list = tasks_data.get("tasks") if isinstance(tasks_data, dict) and "tasks" in tasks_data else tasks_data

        if isinstance(task_list, list):
            if len(task_list) == 0:
                return False, "Görev listesi boş olamaz.", []
            validated = [MasterSubTaskSchema(**item).model_dump() for item in task_list]
            return True, None, validated

        # 2. Durum: app.py 5'li sabit kategori sözlüğü
        if isinstance(tasks_data, dict):
            validated_dict = {}
            for k, v in tasks_data.items():
                if isinstance(v, dict) and "task_id" in v:
                    validated_dict[k] = MasterSubTaskSchema(**v).model_dump()
                elif isinstance(v, dict):
                    validated_dict[k] = LegacyClassificationItemSchema(**v).model_dump()
                else:
                    return False, f"Geçersiz görev formatı: {k}", []
            return True, None, [validated_dict]

        return False, "Desteklenmeyen görev veri yapısı.", []
    except ValidationError as e:
        return False, f"Şema doğrulama hatası: {e}", []


# =====================================================================
# 3. ANA AJAN - İŞÇİ AJAN SÜRÜMLÜ SÖZLEŞMELERİ (v1.0 - S3-01)
# =====================================================================
class TaskPayloadContract_v1(BaseModel):
    """
    Master Agent -> Worker Agent Görev Gönderim Zarfı (Task Envelope v1.0).
    S3-01 kapsamında run_id, task_id, category, dependencies, payload, timestamps,
    timeout_seconds ve context_artifacts alanlarını içerir.
    """
    contract_version: str = Field(default=CONTRACT_VERSION)
    envelope_id: str = Field(default_factory=lambda: f"env-{uuid.uuid4().hex[:12]}")
    run_id: Optional[str] = None
    task_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    description: str = Field(default="")
    dependencies: List[str] = Field(default_factory=list)
    required_specialty: str = Field(default="general")
    timeout_seconds: float = Field(default=DEFAULT_TASK_TIMEOUT_SECONDS, gt=0.0)
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamps: Dict[str, float] = Field(
        default_factory=lambda: {
            "created_at": time.time(),
            "dispatched_at": time.time(),
        }
    )
    context_artifacts: Dict[str, Any] = Field(default_factory=dict)


def build_task_envelope(
    task: Dict[str, Any],
    run_id: Optional[str] = None,
    context_artifacts: Optional[Dict[str, Any]] = None,
    timeout_seconds: Optional[float] = None,
) -> TaskPayloadContract_v1:
    """
    Ham görev sözlüğünü run_id, task_id, category, dependencies, payload, timestamps,
    timeout_seconds ve birleştirilmiş context_artifacts alanlarıyla doğrulanmış
    bir TaskPayloadContract_v1 zarfına dönüştürür.
    """
    merged_context = dict(task.get("context_artifacts") or {})
    if context_artifacts:
        merged_context.update(context_artifacts)

    effective_timeout = float(
        timeout_seconds
        if timeout_seconds is not None
        else task.get("timeout_seconds", DEFAULT_TASK_TIMEOUT_SECONDS)
    )
    resolved_run_id = run_id if run_id is not None else task.get("run_id")

    now_ts = time.time()
    raw_timestamps = dict(task.get("timestamps") or {})
    raw_timestamps.setdefault("created_at", now_ts)
    raw_timestamps["dispatched_at"] = raw_timestamps.get("dispatched_at", now_ts)

    raw_payload = dict(task.get("payload") or {})
    raw_payload.setdefault("description", str(task.get("description") or ""))
    raw_payload.setdefault("required_specialty", str(task.get("required_specialty") or "general").strip())
    if merged_context:
        raw_payload.setdefault("context_keys", sorted(merged_context.keys()))

    envelope_kwargs: Dict[str, Any] = {
        "contract_version": str(task.get("contract_version") or CONTRACT_VERSION),
        "run_id": resolved_run_id,
        "task_id": str(task.get("task_id") or "").strip(),
        "title": str(task.get("title") or task.get("task_id") or "Untitled Task").strip(),
        "category": str(task.get("category") or "BACKEND").strip(),
        "description": str(task.get("description") or ""),
        "dependencies": list(task.get("dependencies") or []),
        "required_specialty": str(task.get("required_specialty") or "general").strip(),
        "timeout_seconds": effective_timeout,
        "payload": raw_payload,
        "timestamps": raw_timestamps,
        "context_artifacts": merged_context,
    }
    if task.get("envelope_id"):
        envelope_kwargs["envelope_id"] = str(task["envelope_id"])

    return TaskPayloadContract_v1(**envelope_kwargs)


class WorkerTaskResultContract_v1(BaseModel):
    """
    Worker Agent -> Master Agent Sonuç Sözleşmesi (v1.0).
    src/agents/base_agent.py içindeki TaskResult ile birebir dönüştürülebilir.
    """
    contract_version: str = Field(default=CONTRACT_VERSION)
    run_id: Optional[str] = None
    task_id: str = Field(..., min_length=1)
    agent_id: str = Field(..., min_length=1)
    status: WorkerTaskStatus
    output_artifacts: Dict[str, Any] = Field(default_factory=dict, description="Üretilen dosya/çıktı bildirimleri")
    logs: List[str] = Field(default_factory=list, description="Ajan çalışma kayıtları")
    error_message: Optional[str] = None
    execution_time_seconds: float = Field(default=0.0, ge=0.0)
    timestamps: Dict[str, float] = Field(
        default_factory=lambda: {"completed_at": time.time()}
    )

    def is_success(self) -> bool:
        """Hem SUCCESS hem COMPLETED durumlarını başarılı kabul eder."""
        return self.status in (WorkerTaskStatus.SUCCESS, WorkerTaskStatus.COMPLETED)

    def normalized_status(self) -> str:
        """Motor ve veritabanı için durumu 'SUCCESS' veya 'FAILED' olarak döndürür."""
        return normalize_worker_status(self.status)


class WorkerErrorContract_v1(BaseModel):
    """
    Worker Agent -> Master Agent Standart Hata Zarfı (v1.0 - S3-01).
    Zaman aşımı, yetkisiz erişim, mükerrer görev ve şema ihlallerini sürümlü raporlar.
    """
    contract_version: str = Field(default=CONTRACT_VERSION)
    run_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    error_code: WorkerErrorCode
    message: str = Field(..., min_length=1)
    retryable: bool = Field(default=False)
    timestamp: float = Field(default_factory=time.time)
    timestamps: Dict[str, float] = Field(
        default_factory=lambda: {"occurred_at": time.time()}
    )


class OrchestratorTaskRecordContract_v1(BaseModel):
    """
    Master Orchestrator Sonuç Sözleşmesi (v1.0).
    src/master/orchestrator.py çıktısı ile birebir uyumlu.
    """
    contract_version: str = Field(default=CONTRACT_VERSION)
    run_id: str = Field(..., min_length=1)
    task_id: str = Field(..., min_length=1)
    status: OrchestratorTaskStatus
    assigned_agent: Optional[str] = None
    agent_result_status: Optional[str] = None
    attempted_agents: List[str] = Field(default_factory=list)
    output_artifacts: Dict[str, Any] = Field(default_factory=dict)
    output_files: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


# =====================================================================
# 4. BÜTÜNLEŞTİRME (INTEGRATION) RAPORU SÖZLEŞMESİ
# =====================================================================
class IntegrationFinding(BaseModel):
    file_path: str
    severity: str  # "CRITICAL", "WARNING", "INFO"
    issue: str
    actionable_suggestion: str


class IntegrationReportContract_v1(BaseModel):
    contract_version: str = Field(default=CONTRACT_VERSION)
    run_id: Optional[str] = None
    status: str  # "APPROVED", "REVIEW_REQUIRED", "REJECTED"
    inspected_files: List[str] = Field(default_factory=list)
    conflicts_detected: List[str] = Field(default_factory=list)
    conflicts_resolved: int = 0
    findings: List[IntegrationFinding] = Field(default_factory=list)
    package_path: Optional[str] = None
    summary: str = ""


# =====================================================================
# 5. MÜKERRER GÖREV (DUPLICATE MESSAGE) KORUMASI (S3-01 Madde 3)
# =====================================================================
class DuplicateTaskTracker:
    """
    Aynı (run_id, task_id) veya envelope_id ile gelen mükerrer görev isteklerini
    yakalayan iş parçacığı güvenli (thread-safe) idempotency izleyicisi.

    Davranış:
    - Görev şu an çalışıyorsa ('IN_PROGRESS'): yeni isteği reddeder -> ('IN_PROGRESS', None)
    - Görev aynı run içinde zaten başarıyla tamamlandıysa ('COMPLETED'):
      modeli tekrar çalıştırmadan önbellekteki sonucu döner -> ('COMPLETED', cached_result)
    - Görev ilk kez geliyorsa (veya önceki deneme başarısız olup serbest bırakıldıysa):
      durumu 'IN_PROGRESS' işaretler -> ('NEW', None)
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._in_progress: set = set()
        self._completed_cache: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def make_key(
        run_id: Optional[str],
        task_id: str,
        envelope_id: Optional[str] = None,
    ) -> Optional[str]:
        if run_id and task_id:
            return f"run:{run_id}::task:{task_id}"
        if envelope_id:
            return f"env:{envelope_id}"
        return None

    def begin(
        self,
        run_id: Optional[str],
        task_id: str,
        envelope_id: Optional[str] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        key = self.make_key(run_id, task_id, envelope_id)
        if key is None:
            return "NEW", None

        with self._lock:
            if key in self._completed_cache:
                return "COMPLETED", dict(self._completed_cache[key])
            if key in self._in_progress:
                return "IN_PROGRESS", None
            self._in_progress.add(key)
            return "NEW", None

    def complete(
        self,
        run_id: Optional[str],
        task_id: str,
        result: Dict[str, Any],
        envelope_id: Optional[str] = None,
    ) -> None:
        key = self.make_key(run_id, task_id, envelope_id)
        if key is None:
            return
        with self._lock:
            self._in_progress.discard(key)
            self._completed_cache[key] = dict(result)

    def release(
        self,
        run_id: Optional[str],
        task_id: str,
        envelope_id: Optional[str] = None,
    ) -> None:
        """Başarısız denemelerde kilidi kaldırır ki failover / yeniden deneme çalışabilsin."""
        key = self.make_key(run_id, task_id, envelope_id)
        if key is None:
            return
        with self._lock:
            self._in_progress.discard(key)

    def clear(self) -> None:
        with self._lock:
            self._in_progress.clear()
            self._completed_cache.clear()
