import os
import ast
import time
import hashlib
from typing import Dict, Any, List, Optional

try:
    from src.agents.base_agent import BaseAgent, TaskResult
except ImportError:
    BaseAgent = object
    TaskResult = None

from src.contracts import (
    IntegrationFinding,
    IntegrationReportContract_v1,
    ArtifactManifest,
    ManifestReportContract
)

class IntegrationAgent(BaseAgent if isinstance(BaseAgent, type) else object):
    """
    S3-05 & S4-05: Dosya çakışması, boyut/hash doğrulaması (Manifest) ve 
    gerçek AST/SQL sözdizimi analizi yapan Bütünleştirme Ajanı.
    """

    def __init__(
        self,
        agent_id: str = "integration_agent",
        name: str = "Integration Agent",
        model_name: str = "phi4-mini:3.8b",
        workspace_root: Optional[str] = None,
        **kwargs,
    ):
        if isinstance(BaseAgent, type) and BaseAgent is not object:
            try:
                super().__init__(agent_id=agent_id, name=name, **kwargs)
            except TypeError:
                try:
                    super().__init__(agent_id, **kwargs)
                except Exception:
                    pass
                    
        self.agent_id = agent_id
        self.name = name
        self.model_name = model_name
        self.workspace_root = os.path.abspath(workspace_root or os.getcwd())

        # Master Orchestrator'ın çökmemesi için zorunlu başlangıç değerleri
        if not hasattr(self, "status"):
            self.status = "IDLE"
            
        if not hasattr(self, "current_tasks"):
            self.current_tasks = []
            
        if not hasattr(self, "capabilities"):
            class IntegrationCaps:
                def __init__(self):
                    self.coding_score = 80
                    self.reasoning_score = 90
                    self.context_capacity = 100
                    self.specialties = ["integration", "testing", "architecture"]
                    self.provenance = {"source": "mock"}

                def calculate_fit_score(self, category):
                    return 0.9

            self.capabilities = IntegrationCaps()

    def generate_artifact_manifest(self, run_id: str, artifacts: Dict[str, str]) -> ManifestReportContract:
        """S3-05: Dosya boyutunu ve SHA-256 özetini hesaplar."""
        manifests = []
        missing_or_empty = []

        for file_path, content in artifacts.items():
            if not content or not str(content).strip():
                missing_or_empty.append(file_path)
                continue

            content_bytes = str(content).encode('utf-8')
            size_bytes = len(content_bytes)
            sha256_hash = hashlib.sha256(content_bytes).hexdigest()

            file_name = os.path.basename(file_path)
            manifests.append(
                ArtifactManifest(
                    file_name=file_name,
                    relative_path=file_path,
                    size_bytes=size_bytes,
                    sha256_hash=sha256_hash
                )
            )

        status = "COMPLETED" if not missing_or_empty else "REVIEW_REQUIRED"
        
        return ManifestReportContract(
            run_id=run_id or "unknown_run",
            manifests=manifests,
            missing_or_empty_files=missing_or_empty,
            catalog_status=status
        )

    def _is_safe_path(self, file_path: str) -> bool:
        if ".." in file_path.replace("\\", "/").split("/"):
            return False
        abs_target = os.path.abspath(os.path.join(self.workspace_root, file_path))
        return abs_target.startswith(self.workspace_root)

    def inspect_artifacts(
        self,
        artifacts: Dict[str, str],
        run_id: Optional[str] = None,
        artifact_sources: Optional[Dict[str, List[str]]] = None,
        create_package_dir: Optional[str] = None,
    ) -> IntegrationReportContract_v1:
        """S4-05: Çıktı dosyalarını inceler, çakışmaları ve sentaks hatalarını bulur."""
        findings: List[IntegrationFinding] = []
        inspected: List[str] = []
        conflicts: List[str] = []

        # Hatanın kaynağı olan çakışma (conflict) kontrolü eklendi
        if artifact_sources:
            for path, producers in artifact_sources.items():
                if len(producers) > 1:
                    conflicts.append(path)
                    findings.append(
                        IntegrationFinding(
                            file_path=path,
                            severity="CRITICAL",
                            issue=f"Dosya yolu çakışması: '{path}' birden fazla ajan tarafından üretildi.",
                            actionable_suggestion="Her ajanın farklı bir dosya yoluna çıktı ürettiğinden emin olun.",
                        )
                    )

        if not artifacts:
            findings.append(
                IntegrationFinding(
                    file_path="WORKSPACE", severity="CRITICAL",
                    issue="İncelenecek hiçbir gerçek çıktı dosyası bulunamadı.",
                    actionable_suggestion="İşçi ajanların çıktı ürettiğini doğrulayın."
                )
            )
            return IntegrationReportContract_v1(
                run_id=run_id, status="REJECTED", conflicts_detected=conflicts, findings=findings, summary="Dosya bulunamadı."
            )

        for file_path, content in artifacts.items():
            if not self._is_safe_path(file_path):
                findings.append(
                    IntegrationFinding(file_path=file_path, severity="CRITICAL", issue="Güvensiz dosya yolu.", actionable_suggestion="Göreli yol kullanın.")
                )
                continue

            inspected.append(file_path)
            
            # Python Sözdizimi Kontrolü
            if file_path.endswith(".py"):
                try:
                    ast.parse(str(content))
                except SyntaxError as e:
                    findings.append(
                        IntegrationFinding(
                            file_path=file_path, severity="CRITICAL",
                            issue=f"Python sözdizimi hatası: {e.msg} (Satır {e.lineno})",
                            actionable_suggestion=f"{file_path} dosyasının {e.lineno}. satırındaki kodu düzeltin."
                        )
                    )

            # SQL Sözdizimi Kontrolü
            elif file_path.endswith(".sql"):
                upper_content = str(content).upper()
                if "CREATE " not in upper_content and "SELECT " not in upper_content and "INSERT " not in upper_content:
                    findings.append(
                        IntegrationFinding(
                            file_path=file_path, severity="WARNING",
                            issue="SQL dosyasında geçerli bir tablo veya sorgu görülmedi.",
                            actionable_suggestion="SQL şema dosyasının DDL/DML komutları içerdiğini kontrol edin."
                        )
                    )

        # Durum Belirleme
        has_critical = any(f.severity == "CRITICAL" for f in findings)
        has_warning = any(f.severity == "WARNING" for f in findings)

        if has_critical:
            final_status = "REJECTED"
        elif has_warning:
            final_status = "REVIEW_REQUIRED"
        else:
            final_status = "APPROVED"

        package_path = None
        if final_status == "APPROVED" and create_package_dir:
            os.makedirs(create_package_dir, exist_ok=True)
            for rel_path, content in artifacts.items():
                if content:
                    target = os.path.join(create_package_dir, os.path.basename(rel_path))
                    with open(target, "w", encoding="utf-8") as f:
                        f.write(str(content))
            package_path = os.path.abspath(create_package_dir)

        return IntegrationReportContract_v1(
            run_id=run_id, status=final_status, inspected_files=inspected,
            conflicts_detected=conflicts, findings=findings, package_path=package_path,
            summary=f"{len(inspected)} dosya incelendi. Durum: {final_status}"
        )

    def execute_task(self, task: Dict[str, Any]) -> Any:
        t0 = time.time()
        run_id = task.get("run_id")
        artifacts = task.get("output_artifacts") or task.get("artifacts") or {}
        sources = task.get("artifact_sources")
        pkg_dir = task.get("package_dir")

        if artifacts:
            # 1. S3-05: Dosya boyutları ve özetleri çıkartılır
            self.generate_artifact_manifest(run_id or "unknown", artifacts)
            
            # 2. S4-05: Sentaks ve çakışma kontrolü yapılır
            report = self.inspect_artifacts(
                artifacts=artifacts, run_id=run_id, artifact_sources=sources, create_package_dir=pkg_dir
            )
            
            result_dict = report.model_dump()
            worker_status = "COMPLETED" if report.status in ("APPROVED", "REVIEW_REQUIRED") else "FAILED"
        else:
            report = IntegrationReportContract_v1(
                run_id=run_id, status="REJECTED",
                findings=[IntegrationFinding(file_path="NONE", severity="CRITICAL", issue="output_artifacts bildirilmedi.", actionable_suggestion="")]
            )
            result_dict = report.model_dump()
            worker_status = "FAILED"

        elapsed = round(time.time() - t0, 4)

        if TaskResult is not None:
            try:
                return TaskResult(
                    task_id=task.get("task_id", "integration_task"),
                    agent_id=self.agent_id, status=worker_status,
                    output_artifacts=result_dict, logs=[report.summary],
                    error_message=None if worker_status == "COMPLETED" else report.summary,
                    execution_time_seconds=elapsed,
                )
            except Exception:
                pass

        return result_dict