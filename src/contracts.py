from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field, ValidationError

# 1. DURUM TANIMLARI (Worker vs Orchestrator Ayrımı - Madde 4)
class WorkerTaskStatus(str, Enum):
    """İşçi ajanın (BaseAgent / TaskResult) doğrudan döndürebileceği durumlar"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class OrchestratorTaskStatus(str, Enum):
    """Master Orchestrator'ın raporlayabileceği durumlar (UNASSIGNED ve BLOCKED dahil)"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNASSIGNED = "UNASSIGNED"
    BLOCKED = "BLOCKED"

# =====================================================================
# 2. MASTER MOTORU GÖREV SINIFLANDIRMA ŞEMASI (Madde 5)
# =====================================================================
class MasterSubTaskSchema(BaseModel):
    """Master motorunun (orchestrator) çalıştığı gerçek görev şeması"""
    task_id: str = Field(..., min_length=1, description="Alt görevin benzersiz kimliği")
    title: str = Field(..., min_length=2, description="Görev başlığı")
    category: str = Field(..., min_length=2, description="Görev kategorisi (backend, frontend, database, testing vb.)")
    description: str = Field(..., min_length=5, description="Görevin teknik açıklaması")
    dependencies: List[str] = Field(default_factory=list, description="Bağımlı olduğu task_id listesi")
    required_specialty: str = Field(..., min_length=2, description="Gereken ajan uzmanlığı")

class LegacyClassificationItemSchema(BaseModel):
    """app.py arayüzündeki 5 sabit kategorili şema desteği (Geriye dönük uyumluluk)"""
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
# 3. ANA AJAN - İŞÇİ AJAN SÜRÜMLÜ SÖZLEŞMELERİ (v1.0 - Madde 4)
# =====================================================================
class TaskPayloadContract_v1(BaseModel):
    """Master Agent -> Worker Agent Görev Gönderim Sözleşmesi"""
    contract_version: str = Field(default="1.0")
    run_id: Optional[str] = None
    task_id: str
    title: str
    category: str
    description: str
    dependencies: List[str] = Field(default_factory=list)
    required_specialty: str
    context_artifacts: Dict[str, Any] = Field(default_factory=dict)

class WorkerTaskResultContract_v1(BaseModel):
    """
    Worker Agent -> Master Agent Sonuç Sözleşmesi
    (src/agents/base_agent.py içindeki TaskResult ile birebir uyumlu)
    """
    contract_version: str = Field(default="1.0")
    task_id: str
    agent_id: str
    status: WorkerTaskStatus
    output_artifacts: Dict[str, Any] = Field(default_factory=dict, description="Üretilen dosya/çıktı bildirimleri")
    logs: List[str] = Field(default_factory=list, description="Ajan çalışma kayıtları")
    error_message: Optional[str] = None
    execution_time_seconds: float = Field(default=0.0, ge=0.0)

class OrchestratorTaskRecordContract_v1(BaseModel):
    """
    Master Orchestrator Sonuç Sözleşmesi
    (src/master/orchestrator.py çıktısı ile birebir uyumlu)
    """
    contract_version: str = Field(default="1.0")
    run_id: str
    task_id: str
    status: OrchestratorTaskStatus
    assigned_agent: Optional[str] = None
    agent_result_status: Optional[str] = None
    attempted_agents: List[str] = Field(default_factory=list)
    output_artifacts: Dict[str, Any] = Field(default_factory=dict)
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
    contract_version: str = Field(default="1.0")
    run_id: Optional[str] = None
    status: str  # "APPROVED", "REVIEW_REQUIRED", "REJECTED"
    inspected_files: List[str] = Field(default_factory=list)
    conflicts_detected: List[str] = Field(default_factory=list)
    conflicts_resolved: int = 0
    findings: List[IntegrationFinding] = Field(default_factory=list)
    package_path: Optional[str] = None
    summary: str = ""