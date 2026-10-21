from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ValidationError

# Ajan Rolleri
class AgentRole(str, Enum):
    DATABASE = "database"
    BACKEND = "backend"
    FRONTEND = "frontend"
    TESTING = "testing"
    INTEGRATION = "integration"

# Görev Durumları (Görkem ve Mahmut'un SQLite yapısı ile birebir uyumlu)
class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNASSIGNED = "UNASSIGNED"
    BLOCKED = "BLOCKED"

# =====================================================================
# GÖREV 1: GÖREV SINIFLANDIRMA (TASK CLASSIFICATION) ŞEMA DOĞRULAMASI
# =====================================================================
class ClassifiedSubTaskSchema(BaseModel):
    """Master Agent'ın böldüğü her bir alt görevin uyması gereken şema kuralı"""
    description: str = Field(..., min_length=10, description="Görevin detaylı teknik açıklaması")
    complexity: str = Field(..., pattern="^(Low|Medium|High)$", description="Zorluk derecesi")
    primary_skill_required: str = Field(..., pattern="^(Coding|Reasoning|Context)$", description="Gereken ana yetenek")
    story_points: int = Field(default=3, ge=1, le=13, description="Scrum hikaye puanı")

class TaskClassificationOutputSchema(BaseModel):
    """Master Agent'ın tüm sınıflandırma çıktısını doğrulayan ana kural"""
    Requirements_Analysis: ClassifiedSubTaskSchema
    Frontend_Development: ClassifiedSubTaskSchema
    Backend_Development: ClassifiedSubTaskSchema
    Database_Design: ClassifiedSubTaskSchema
    Quality_Assurance_and_Testing: ClassifiedSubTaskSchema

def validate_master_classification(raw_json_dict: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Master'ın böldüğü görev çıktısını şemaya göre kontrol eden fonksiyon.
    Geçerliyse (True, None), hatalıysa (False, 'Hata mesajı') döner.
    """
    try:
        TaskClassificationOutputSchema(**raw_json_dict)
        return True, None
    except ValidationError as e:
        return False, f"Görev Sınıflandırma Şema Hatası: {e}"

# =====================================================================
# GÖREV 2: ANA AJAN - İŞÇİ AJAN SÜRÜMLÜ (v1.0) SÖZLEŞMELERİ
# =====================================================================
class TaskContract_v1(BaseModel):
    """Ana Ajan -> İşçi Ajan Görev Atama Sözleşmesi (Sürüm 1.0)"""
    contract_version: str = Field(default="1.0", description="Sözleşme sürümü")
    run_id: str = Field(..., description="SQLite çalıştırma kimliği")
    task_id: str = Field(..., description="Alt görev kimliği")
    target_agent: AgentRole = Field(..., description="Görevin atandığı ajan rolü")
    description: str = Field(..., description="Yapılacak işin tanımı")
    input_artifacts: Dict[str, str] = Field(
        default_factory=dict,
        description="Önceki ajanlardan gelen dosyalar (Örn: {'schema.sql': 'CREATE TABLE...'})"
    )

class WorkerResultContract_v1(BaseModel):
    """İşçi Ajan -> Ana Ajan / Integration Agent Sonuç Sözleşmesi (Sürüm 1.0)"""
    contract_version: str = Field(default="1.0", description="Sözleşme sürümü")
    run_id: str = Field(..., description="SQLite çalıştırma kimliği")
    task_id: str = Field(..., description="Alt görev kimliği")
    agent_role: AgentRole = Field(..., description="Çıktıyı üreten ajan")
    status: TaskStatus = Field(..., description="Görev durumu (COMPLETED, FAILED vb.)")
    output_files: Dict[str, str] = Field(
        default_factory=dict,
        description="Üretilen gerçek kod dosyaları (Örn: {'main.py': 'from fastapi...'})"
    )
    error_message: Optional[str] = None

class IntegrationFinding(BaseModel):
    """Integration Agent'ın tespit ettiği tekil bulgu"""
    file_name: str
    severity: str  # "CRITICAL", "WARNING", "INFO"
    issue: str
    actionable_suggestion: str  # Uygulanabilir çözüm önerisi

class IntegrationReportContract_v1(BaseModel):
    """Integration Agent Nihai Denetim Sözleşmesi (Sürüm 1.0)"""
    contract_version: str = Field(default="1.0")
    run_id: str
    overall_status: str  # "PASSED" veya "FAILED"
    inspected_files: List[str]
    findings: List[IntegrationFinding] = Field(default_factory=list)
    llm_review_summary: str = ""