import os
import ast
import time
from typing import Dict, Any, List, Optional

try:
    from src.agents.base_agent import BaseAgent, TaskResult, AgentStatus
except ImportError:
    BaseAgent = object
    TaskResult = None
    AgentStatus = None

from src.contracts import (
    IntegrationFinding,
    IntegrationReportContract_v1,
    validate_master_tasks,
)


class IntegrationAgent(BaseAgent if isinstance(BaseAgent, type) else object):
    """
    Gerçek çıktı dosyalarını (output_artifacts) inceleyen, sözdizimi/statik analiz
    ve dosya çakışması kontrolü yaparak kanıta dayalı bulgu üreten Bütünleştirme Ajanı.
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

        # Master motorunun ajan durumunu kontrol edebilmesi için.
        # Diğer ajanlarla aynı tip olmalı: arayüz status.value okuyor.
        if not hasattr(self, "status"):
            self.status = AgentStatus.IDLE if AgentStatus else "IDLE"
            
        # YENİ EKLENEN: Master motorunun aktif görev sayısını okuyabilmesi için
        if not hasattr(self, "current_tasks"):
            self.current_tasks = []
            
        # Master motorunun DB'ye kaydederken aradığı tüm alanlar eksiksiz eklendi
        if not hasattr(self, "capabilities"):
            class IntegrationCaps:
                def __init__(self):
                    self.coding_score = 80
                    self.reasoning_score = 90
                    self.context_capacity = 100
                    self.specialties = ["integration", "testing"]
                    self.provenance = {"source": "mock"}

                def calculate_fit_score(self, category):
                    return 0.9

                def model_dump(self):
                    return {
                        "coding_score": self.coding_score,
                        "reasoning_score": self.reasoning_score,
                        "context_capacity": self.context_capacity,
                        "specialties": self.specialties,
                        "provenance": self.provenance
                    }

                def dict(self):
                    return self.model_dump()
            
            self.capabilities = IntegrationCaps()

    def _is_safe_path(self, file_path: str) -> bool:
        """Dosya yolunun çalışma alanı (workspace) dışına çıkıp çıkmadığını kontrol eder."""
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
        """
        Çıktı dosyalarını (dosya_yolu -> içerik) inceler, çakışmaları ve sentaks
        hatalarını bulur, kanıta dayalı IntegrationReportContract_v1 döndürür.
        """
        findings: List[IntegrationFinding] = []
        inspected: List[str] = []
        conflicts: List[str] = []

        # 1. Çakışma Kontrolü
        if artifact_sources:
            for path, producers in artifact_sources.items():
                if len(producers) > 1:
                    conflicts.append(path)
                    findings.append(
                        IntegrationFinding(
                            file_path=path,
                            severity="CRITICAL",
                            issue=f"Dosya yolu çakışması: '{path}' birden fazla ajan tarafından üretildi ({', '.join(producers)}).",
                            actionable_suggestion="Her ajanın farklı bir modül veya dosya yoluna çıktı ürettiğinden emin olun.",
                        )
                    )

        # 2. Hiç dosya yoksa
        if not artifacts:
            findings.append(
                IntegrationFinding(
                    file_path="WORKSPACE",
                    severity="CRITICAL",
                    issue="İncelenecek hiçbir gerçek çıktı dosyası (output_artifacts) bulunamadı.",
                    actionable_suggestion="İşçi ajanların çıktı ürettiğini ve bildirdiğini doğrulayın.",
                )
            )
            return IntegrationReportContract_v1(
                run_id=run_id,
                status="REJECTED",
                inspected_files=[],
                conflicts_detected=conflicts,
                conflicts_resolved=0,
                findings=findings,
                package_path=None,
                summary="Çıktı dosyası bulunamadığı için bütünleştirme reddedildi.",
            )

        # 3. Güvenlik, Varlık ve Sözdizimi Denetimleri
        for file_path, content in artifacts.items():
            if not self._is_safe_path(file_path):
                findings.append(
                    IntegrationFinding(
                        file_path=file_path,
                        severity="CRITICAL",
                        issue="İzin verilen çalışma alanı dışına çıkan güvensiz dosya yolu tespit edildi.",
                        actionable_suggestion="Göreli ve çalışma alanı içinde kalan bir dosya yolu kullanın.",
                    )
                )
                continue

            inspected.append(file_path)

            actual_content = content
            full_disk_path = os.path.join(self.workspace_root, file_path)
            if (actual_content is None or actual_content == "") and os.path.isfile(full_disk_path):
                with open(full_disk_path, "r", encoding="utf-8", errors="ignore") as f:
                    actual_content = f.read()

            if not actual_content or not str(actual_content).strip():
                findings.append(
                    IntegrationFinding(
                        file_path=file_path,
                        severity="CRITICAL",
                        issue="Çıktı dosyası boş veya diskte bulunamadı.",
                        actionable_suggestion=f"'{file_path}' dosyasının içerik ürettiğinden emin olun.",
                    )
                )
                continue

            # Python AST Denetimi
            if file_path.endswith(".py"):
                try:
                    ast.parse(str(actual_content))
                except SyntaxError as e:
                    findings.append(
                        IntegrationFinding(
                            file_path=file_path,
                            severity="CRITICAL",
                            issue=f"Python sözdizimi (syntax) hatası: {e.msg} (Satır {e.lineno})",
                            actionable_suggestion=f"{file_path} dosyasının {e.lineno}. satırındaki yazım hatasını düzeltin.",
                        )
                    )

            # SQL Şema Denetimi
            elif file_path.endswith(".sql"):
                if "CREATE " not in str(actual_content).upper() and "SELECT " not in str(actual_content).upper():
                    findings.append(
                        IntegrationFinding(
                            file_path=file_path,
                            severity="WARNING",
                            issue="SQL dosyasında geçerli bir DDL/DML (CREATE/SELECT) ifadesi görülmedi.",
                            actionable_suggestion="SQL şema dosyasının tablo tanımlarını içerdiğini kontrol edin.",
                        )
                    )

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
                if self._is_safe_path(rel_path) and content:
                    target = os.path.join(create_package_dir, os.path.basename(rel_path))
                    with open(target, "w", encoding="utf-8") as f:
                        f.write(str(content))
            package_path = os.path.abspath(create_package_dir)

        return IntegrationReportContract_v1(
            run_id=run_id,
            status=final_status,
            inspected_files=inspected,
            conflicts_detected=conflicts,
            conflicts_resolved=0,
            findings=findings,
            package_path=package_path,
            summary=f"{len(inspected)} dosya incelendi, {len(findings)} bulgu saptandı. Durum: {final_status}",
        )

    def execute_task(self, task: Dict[str, Any]) -> Any:
        t0 = time.time()
        run_id = task.get("run_id")
        artifacts = task.get("output_artifacts") or task.get("artifacts") or {}
        sources = task.get("artifact_sources")
        pkg_dir = task.get("package_dir")

        if artifacts:
            report = self.inspect_artifacts(
                artifacts=artifacts,
                run_id=run_id,
                artifact_sources=sources,
                create_package_dir=pkg_dir,
            )
            result_dict = report.model_dump()
            worker_status = "COMPLETED" if report.status in ("APPROVED", "REVIEW_REQUIRED") else "FAILED"
        else:
            report = IntegrationReportContract_v1(
                run_id=run_id,
                status="REVIEW_REQUIRED",
                inspected_files=[],
                conflicts_detected=[],
                conflicts_resolved=0,
                findings=[
                    IntegrationFinding(
                        file_path="NONE",
                        severity="WARNING",
                        issue="Görev yükünde incelenecek output_artifacts bildirilmedi.",
                        actionable_suggestion="İnceleme için output_artifacts sözlüğünü iletin.",
                    )
                ],
                package_path=None,
                summary="İncelenecek dosya bildirilmediği için inceleme gerekli olarak işaretlendi.",
            )
            result_dict = report.model_dump()
            worker_status = "COMPLETED"

        elapsed = round(time.time() - t0, 4)

        if TaskResult is not None:
            try:
                return TaskResult(
                    task_id=task.get("task_id", "integration_task"),
                    agent_id=self.agent_id,
                    status=worker_status,
                    output_artifacts=result_dict,
                    logs=[report.summary],
                    error_message=None if worker_status == "COMPLETED" else report.summary,
                    execution_time_seconds=elapsed,
                )
            except Exception:
                pass

        return result_dict