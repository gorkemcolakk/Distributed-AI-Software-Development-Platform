import os
import ast
import json
import time
import hashlib
import requests
from typing import Dict, Any, List, Optional, Tuple

try:
    from src.agents.base_agent import BaseAgent, TaskResult, AgentStatus, AgentCapabilityProfile
except ImportError:
    BaseAgent = object
    TaskResult = None
    AgentStatus = None
    AgentCapabilityProfile = None



def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


from src.contracts import (
    IntegrationFinding,
    IntegrationReportContract_v1,
    validate_master_tasks,
    ArtifactManifest,
    ManifestReportContract,
)


class IntegrationAgent(BaseAgent if isinstance(BaseAgent, type) else object):
    """
    S3-05, S4-04 & S4-05: Gerçek çıktı dosyalarını (Python, SQL, UI/HTML/CSS/JS) okuyan,
    sözdizimi/statik analiz, dosya çakışması kontrolü, SHA-256 manifest üretimi
    ve yerel Ollama modeli (phi4-mini:3.8b) ile otomatik kod incelemesi (Code Review)
    ve paket birleştirme yapan Bütünleştirme Ajanı.
    """

    def __init__(
        self,
        agent_id: str = "integration_agent",
        name: str = "Integration Agent",
        model_name: str = "phi4-mini:3.8b",
        workspace_root: Optional[str] = None,
        ollama_url: Optional[str] = None,
        use_llm: Optional[bool] = None,
        **kwargs,
    ):
        profile = kwargs.pop("capability_profile", None)
        if profile is None and AgentCapabilityProfile is not None:
            profile = AgentCapabilityProfile(
                coding_score=78.0,
                reasoning_score=95.0,
                context_capacity=90.0,
                specialties=["integration", "code_review", "conflict_resolution", "deployment"],
            )

        if isinstance(BaseAgent, type) and BaseAgent is not object:
            try:
                super().__init__(
                    agent_id=agent_id,
                    name=name,
                    model_name=model_name,
                    capability_profile=profile,
                )
            except Exception:
                pass

        self.agent_id = agent_id or getattr(self, "agent_id", "integration_agent")
        self.name = name
        self.model_name = os.getenv("INTEGRATION_MODEL", model_name)
        self.workspace_root = os.path.abspath(workspace_root or os.getcwd())

        base_host = (
            ollama_url
            or os.getenv("OLLAMA_BASE_URL")
            or os.getenv("OLLAMA_HOST")
            or "http://localhost:11434"
        ).rstrip("/")
        if base_host.endswith("/api/generate"):
            self.ollama_generate_url = base_host
        else:
            self.ollama_generate_url = f"{base_host}/api/generate"

        self.ollama_timeout = float(os.getenv("OLLAMA_TIMEOUT", "45"))
        # Same switch style as the other agents (BACKEND_AGENT_USE_OLLAMA, ...); tests pass use_llm=False
        self.use_llm = _env_flag("INTEGRATION_AGENT_USE_OLLAMA", True) if use_llm is None else bool(use_llm)
        # (review_mode, fallback_reason) of the last LLM review: "llm" / "fallback" / "static"
        self._llm_outcome: Tuple[str, Optional[str]] = ("static", None)

        # Master motoru ve arayüz uyumluluğu: status her zaman AgentStatus kalmalı
        if not hasattr(self, "status") or self.status is None or isinstance(self.status, str):
            self.status = AgentStatus.IDLE if AgentStatus is not None else "IDLE"

        if not hasattr(self, "current_tasks") or self.current_tasks is None:
            self.current_tasks = []

        if not hasattr(self, "capabilities") or self.capabilities is None:
            if profile is not None:
                self.capabilities = profile
            else:
                class IntegrationCaps:
                    def __init__(self):
                        self.coding_score = 78.0
                        self.reasoning_score = 95.0
                        self.context_capacity = 90.0
                        self.specialties = ["integration", "code_review", "conflict_resolution", "deployment"]
                        self.provenance = {
                            "coding": "estimated",
                            "reasoning": "estimated",
                            "context_capacity": "estimated",
                        }

                    def calculate_fit_score(self, category):
                        return 89.5

                    def model_dump(self):
                        return {
                            "coding_score": self.coding_score,
                            "reasoning_score": self.reasoning_score,
                            "context_capacity": self.context_capacity,
                            "specialties": self.specialties,
                            "provenance": self.provenance,
                        }

                    def dict(self):
                        return self.model_dump()

                self.capabilities = IntegrationCaps()

    def generate_artifact_manifest(self, run_id: str, artifacts: Dict[str, str]) -> ManifestReportContract:
        """
        Gelen dosya içeriklerinin boyutunu ve SHA-256 özetini hesaplar;
        boş veya geçersiz olanları raporlar ve kataloglar (S3-05).
        """
        manifests = []
        missing_or_empty = []

        for file_path, content in artifacts.items():
            if not content or not str(content).strip():
                missing_or_empty.append(file_path)
                continue

            content_bytes = str(content).encode("utf-8")
            size_bytes = len(content_bytes)
            sha256_hash = hashlib.sha256(content_bytes).hexdigest()
            file_name = os.path.basename(file_path)

            manifests.append(
                ArtifactManifest(
                    file_name=file_name,
                    relative_path=file_path,
                    size_bytes=size_bytes,
                    sha256_hash=sha256_hash,
                )
            )

        status = "COMPLETED" if not missing_or_empty else "REVIEW_REQUIRED"

        return ManifestReportContract(
            run_id=run_id or "unknown_run",
            manifests=manifests,
            missing_or_empty_files=missing_or_empty,
            catalog_status=status,
        )

    def _is_safe_path(self, file_path: str) -> bool:
        """Dosya yolunun çalışma alanı (workspace) dışına çıkıp çıkmadığını kontrol eder."""
        if ".." in file_path.replace("\\", "/").split("/"):
            return False
        abs_target = os.path.abspath(os.path.join(self.workspace_root, file_path))
        return abs_target.startswith(self.workspace_root)

    def _check_ui_syntax(self, file_path: str, text_content: str) -> List[IntegrationFinding]:
        """
        S4-05 Checklist 1 & 2: Üretilen gerçek UI dosyalarını (.html, .htm, .css, .js)
        sözdizimi ve yapısal bütünlük açısından denetler.
        """
        ui_findings: List[IntegrationFinding] = []
        lower_path = file_path.lower()

        if lower_path.endswith((".html", ".htm")):
            if "<" not in text_content or ">" not in text_content:
                ui_findings.append(
                    IntegrationFinding(
                        file_path=file_path,
                        severity="CRITICAL",
                        issue="HTML dosyasında geçerli hiçbir HTML etiketi bulunamadı.",
                        actionable_suggestion=f"'{file_path}' dosyasına geçerli HTML yapısı (<html>, <body> vb.) ekleyin.",
                    )
                )
            elif text_content.count("<") != text_content.count(">"):
                ui_findings.append(
                    IntegrationFinding(
                        file_path=file_path,
                        severity="WARNING",
                        issue="HTML dosyasında açılan ve kapanan açısal parantez ('<', '>') sayıları eşleşmiyor.",
                        actionable_suggestion=f"'{file_path}' içindeki kapanmamış HTML etiketlerini kontrol edin.",
                    )
                )

        elif lower_path.endswith((".css", ".js", ".jsx", ".tsx")):
            if text_content.count("{") != text_content.count("}"):
                ui_findings.append(
                    IntegrationFinding(
                        file_path=file_path,
                        severity="CRITICAL",
                        issue="UI dosyasında süslü parantez ('{' ve '}') dengesizliği (syntax hatası) tespit edildi.",
                        actionable_suggestion=f"'{file_path}' dosyasındaki açık kalan blok parantezlerini kapatın.",
                    )
                )

        return ui_findings

    def _review_with_llm(
        self,
        valid_files: Dict[str, str],
        task_description: str = "",
    ) -> Tuple[str, List[IntegrationFinding]]:
        """
        S4-05: Yerel Ollama modelini (phi4-mini:3.8b) çağırarak üretilen kod dosyalarını
        mimari uyum, eksik import/tablo referansı ve kod kalitesi açısından inceler.
        """
        self._llm_outcome = ("static", None)
        if not valid_files:
            return "", []

        snippets = []
        for path, code in valid_files.items():
            snippet = str(code)[:1500]
            snippets.append(f"--- FILE: {path} ---\n{snippet}")
        joined_files = "\n\n".join(snippets)

        prompt = (
            "You are an expert Software Integration and Code Review Agent.\n"
            f"Task Context: {task_description or 'Integrate and review multi-agent generated artifacts.'}\n\n"
            "Inspect the following generated code files for cross-file consistency, missing references, "
            "security risks, or logical bugs. Respond ONLY with a valid JSON object in this exact schema:\n"
            "{\n"
            '  "summary": "Brief Turkish summary of code quality and integration compatibility",\n'
            '  "findings": [\n'
            "    {\n"
            '      "file_path": "filename",\n'
            '      "severity": "WARNING or INFO",\n'
            '      "issue": "Turkish description of the issue",\n'
            '      "actionable_suggestion": "Turkish actionable fix suggestion"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "If there are no issues, return an empty list [] for findings.\n\n"
            f"{joined_files}"
        )

        try:
            response = requests.post(
                self.ollama_generate_url,
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=self.ollama_timeout,
            )
            if response.status_code != 200:
                self._llm_outcome = ("fallback", f"HTTP_{response.status_code}")
                return f"LLM incelemesi atlandı (HTTP {response.status_code}).", []

            raw_text = (response.json().get("response") or "").strip()
            if not raw_text:
                self._llm_outcome = ("fallback", "EMPTY_RESPONSE")
                return "LLM boş yanıt döndürdü; statik analiz sonuçları geçerlidir.", []

            self._llm_outcome = ("llm", None)

            cleaned = raw_text
            if "```json" in cleaned:
                cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()

            llm_findings: List[IntegrationFinding] = []
            try:
                start_idx = cleaned.find("{")
                end_idx = cleaned.rfind("}")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    parsed = json.loads(cleaned[start_idx : end_idx + 1])
                    summary_text = str(parsed.get("summary") or "").strip()
                    for item in parsed.get("findings") or []:
                        if isinstance(item, dict) and item.get("issue"):
                            sev = str(item.get("severity", "INFO")).upper()
                            if sev not in ("CRITICAL", "WARNING", "INFO"):
                                sev = "INFO"
                            if sev == "CRITICAL":
                                sev = "WARNING"
                            llm_findings.append(
                                IntegrationFinding(
                                    file_path=str(item.get("file_path") or "GENERAL"),
                                    severity=sev,
                                    issue=str(item.get("issue")),
                                    actionable_suggestion=str(
                                        item.get("actionable_suggestion")
                                        or "İlgili dosyadaki modül uyumluluğunu kontrol edin."
                                    ),
                                )
                            )
                    return summary_text or raw_text[:400], llm_findings
            except Exception:
                pass

            return raw_text[:500], []
        except Exception as exc:
            reason = "TIMEOUT" if "timeout" in type(exc).__name__.lower() else "CONNECTION_ERROR"
            self._llm_outcome = ("fallback", reason)
            return f"Yerel model ({self.model_name}) bağlantısı kurulamadı, statik analiz uygulandı: {exc}", []

    def inspect_artifacts(
        self,
        artifacts: Dict[str, str],
        run_id: Optional[str] = None,
        artifact_sources: Optional[Dict[str, List[str]]] = None,
        create_package_dir: Optional[str] = None,
        conflicts_log: Optional[List[Dict[str, Any]]] = None,
        use_llm: Optional[bool] = None,
        task_description: str = "",
    ) -> IntegrationReportContract_v1:
        """
        S4-04 & S4-05: Gerçek çıktı dosyalarını (Python, SQL, UI) okur, çakışmaları ve sentaks
        hatalarını denetler, yerel model (phi4-mini:3.8b) ile kod inceleme raporu üretir
        ve tüm zorunlu denetimler geçtiğinde birleştirilmiş paketi onaylar.
        """
        findings: List[IntegrationFinding] = []
        inspected: List[str] = []
        conflicts: List[str] = []
        resolved_count = 0
        valid_files_for_llm: Dict[str, str] = {}

        # 1a. Workspace / Şema Çakışma Kayıtları (S4-04)
        for conf in conflicts_log or []:
            c_path = conf.get("file_path") or "UNKNOWN"
            if c_path not in conflicts:
                conflicts.append(c_path)
            resolution = conf.get("resolution")
            detail = conf.get("detail") or f"{conf.get('conflict_type', 'PATH')} çakışması ({resolution})."
            if resolution in ("RENAMED", "DEDUPLICATED"):
                resolved_count += 1
                findings.append(
                    IntegrationFinding(
                        file_path=conf.get("resolved_path") or c_path,
                        severity="INFO",
                        issue=f"Çakışma çözüldü ({resolution}): {detail}",
                        actionable_suggestion="Çalışma alanında her iki sürüm de korundu; birleştirme gerekip gerekmediğini kontrol edin.",
                    )
                )
            else:
                findings.append(
                    IntegrationFinding(
                        file_path=c_path,
                        severity="WARNING",
                        issue=f"Şema/Dosya çakışması tespit edildi: {detail}",
                        actionable_suggestion="Çakışan tablo veya dosya tanımlarını tek şemada hizalayın.",
                    )
                )

        # 1b. Çakışma Kontrolü (çözülmemiş çoklu üretici durumu)
        if artifact_sources:
            for path, producers in artifact_sources.items():
                if len(producers) > 1:
                    if path not in conflicts:
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
                conflicts_resolved=resolved_count,
                findings=findings,
                package_path=None,
                summary="Çıktı dosyası bulunamadığı için bütünleştirme reddedildi.",
            )

        # 3. Güvenlik, Varlık ve Sözdizimi (Python / SQL / UI) Denetimleri
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

            text_content = str(actual_content)
            valid_files_for_llm[file_path] = text_content
            lower_path = file_path.lower()

            # Python AST Sözdizimi Denetimi
            if lower_path.endswith(".py"):
                try:
                    ast.parse(text_content)
                except SyntaxError as e:
                    findings.append(
                        IntegrationFinding(
                            file_path=file_path,
                            severity="CRITICAL",
                            issue=f"Python sözdizimi (syntax) hatası: {e.msg} (Satır {e.lineno})",
                            actionable_suggestion=f"{file_path} dosyasının {e.lineno}. satırındaki yazım hatasını düzeltin.",
                        )
                    )

            # SQL Şema ve Sözdizimi Denetimi
            elif lower_path.endswith(".sql"):
                upper_sql = text_content.upper()
                sql_keywords = ("CREATE ", "SELECT ", "INSERT ", "UPDATE ", "ALTER ", "DROP ")
                if not any(kw in upper_sql for kw in sql_keywords):
                    findings.append(
                        IntegrationFinding(
                            file_path=file_path,
                            severity="WARNING",
                            issue="SQL dosyasında geçerli bir DDL/DML (CREATE/SELECT/INSERT) ifadesi görülmedi.",
                            actionable_suggestion=f"'{file_path}' dosyasının tablo veya sorgu tanımlarını içerdiğini kontrol edin.",
                        )
                    )

            # UI (HTML / CSS / JS) Sözdizimi Denetimi
            elif lower_path.endswith((".html", ".htm", ".css", ".js", ".jsx", ".tsx")):
                findings.extend(self._check_ui_syntax(file_path, text_content))

        # 4. S4-05: Yerel Ollama Modeli (phi4-mini:3.8b) ile Kod İncelemesi
        should_call_llm = use_llm if use_llm is not None else bool(self.use_llm)
        llm_summary = ""
        self._llm_outcome = ("static", None)
        if should_call_llm and valid_files_for_llm:
            llm_summary, llm_findings = self._review_with_llm(
                valid_files=valid_files_for_llm,
                task_description=task_description,
            )
            findings.extend(llm_findings)

        # 5. S4-05 Checklist 3: Zorunlu denetimler geçtiğinde APPROVED, aksi durumda REVIEW_REQUIRED veya REJECTED
        has_critical = any(f.severity == "CRITICAL" for f in findings)
        has_warning = any(f.severity == "WARNING" for f in findings)

        if has_critical:
            final_status = "REJECTED"
        elif has_warning:
            final_status = "REVIEW_REQUIRED"
        else:
            final_status = "APPROVED"

        # 6. S4-05 Checklist 4: Paket yolu YALNIZCA birleştirilmiş paket gerçekten oluşturulduysa raporlanır
        package_path = None
        if final_status == "APPROVED" and create_package_dir:
            written_files = 0
            os.makedirs(create_package_dir, exist_ok=True)
            for rel_path, file_text in valid_files_for_llm.items():
                if self._is_safe_path(rel_path) and file_text.strip():
                    target = os.path.join(create_package_dir, os.path.basename(rel_path))
                    with open(target, "w", encoding="utf-8") as f:
                        f.write(file_text)
                    if os.path.isfile(target):
                        written_files += 1
            if written_files > 0 and os.path.isdir(create_package_dir):
                package_path = os.path.abspath(create_package_dir)

        review_mode, fallback_reason = self._llm_outcome
        base_summary = f"{len(inspected)} dosya incelendi, {len(findings)} bulgu saptandı. Durum: {final_status}"
        if llm_summary:
            full_summary = f"{base_summary} | Model ({self.model_name}): {llm_summary}"
        else:
            full_summary = base_summary

        return IntegrationReportContract_v1(
            run_id=run_id,
            status=final_status,
            inspected_files=inspected,
            conflicts_detected=conflicts,
            conflicts_resolved=resolved_count,
            findings=findings,
            package_path=package_path,
            summary=full_summary,
            llm_review_summary=llm_summary,
            # Shows whether phi4-mini really reviewed the files (UI and logs read these)
            model_used=self.model_name if review_mode == "llm" else None,
            review_mode=review_mode,
            fallback_reason=fallback_reason,
        )

    def _extract_artifacts_from_task(self, task: Dict[str, Any]) -> Dict[str, str]:
        """
        Orchestrator veya HTTP Worker zarfından gelen görev içindeki
        output_artifacts, artifacts veya context_artifacts dosyalarını toplar.
        """
        raw = (
            task.get("output_artifacts")
            or task.get("artifacts")
            or task.get("context_artifacts")
            or (task.get("payload") or {}).get("output_artifacts")
            or (task.get("payload") or {}).get("context_artifacts")
            or {}
        )
        extracted: Dict[str, str] = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, str) and ("." in k or "/" in k):
                    extracted[k] = v
                elif isinstance(v, dict):
                    for sub_k, sub_v in v.items():
                        if isinstance(sub_v, str) and ("." in sub_k or "/" in sub_k):
                            extracted[sub_k] = sub_v
        return extracted

    def execute_task(self, task: Dict[str, Any]) -> Any:
        t0 = time.time()
        task_id = task.get("task_id", "integration_task")
        run_id = task.get("run_id")
        artifacts = self._extract_artifacts_from_task(task)
        sources = task.get("artifact_sources")
        pkg_dir = task.get("package_dir")
        conflicts_log = task.get("conflicts_log")
        task_desc = str(task.get("description") or task.get("title") or "")

        if AgentStatus is not None:
            self.status = AgentStatus.BUSY
        if hasattr(self, "current_tasks") and isinstance(self.current_tasks, list):
            if task_id not in self.current_tasks:
                self.current_tasks.append(task_id)

        use_llm_flag = task.get("use_llm")
        if use_llm_flag is None:
            use_llm_flag = self.use_llm

        logs: List[str] = [
            f"[{self.name}] Starting integration & code review for task '{task_id}' with model '{self.model_name}'"
        ]

        try:
            if artifacts:
                report = self.inspect_artifacts(
                    artifacts=artifacts,
                    run_id=run_id,
                    artifact_sources=sources,
                    create_package_dir=pkg_dir,
                    conflicts_log=conflicts_log,
                    use_llm=bool(use_llm_flag),
                    task_description=task_desc,
                )
                result_dict = report.model_dump()
                # S3-05: incelenen dosyaların boyut ve SHA-256 kataloğu sonuca eklenir
                manifest = self.generate_artifact_manifest(run_id or "unknown", artifacts)
                result_dict["artifact_manifest"] = manifest.model_dump()
                worker_status = "SUCCESS" if report.status in ("APPROVED", "REVIEW_REQUIRED") else "FAILED"
                logs.append(report.summary)
            else:
                # Nothing to review: no model call (reviewing the task text alone would be meaningless)
                llm_note = ""
                summary_msg = "İncelenecek dosya bildirilmediği için inceleme gerekli olarak işaretlendi."

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
                            actionable_suggestion="İnceleme için output_artifacts veya context_artifacts sözlüğünü iletin.",
                        )
                    ],
                    package_path=None,
                    summary=summary_msg,
                    llm_review_summary=llm_note,
                )
                result_dict = report.model_dump()
                worker_status = "SUCCESS"
                logs.append(report.summary)
        finally:
            if hasattr(self, "current_tasks") and isinstance(self.current_tasks, list):
                if task_id in self.current_tasks:
                    self.current_tasks.remove(task_id)

        if AgentStatus is not None:
            self.status = AgentStatus.IDLE if worker_status == "SUCCESS" else AgentStatus.ERROR

        elapsed = round(time.time() - t0, 4)

        if TaskResult is not None:
            try:
                return TaskResult(
                    task_id=task_id,
                    agent_id=self.agent_id,
                    status=worker_status,
                    output_artifacts=result_dict,
                    logs=logs,
                    error_message=None if worker_status == "SUCCESS" else report.summary,
                    execution_time_seconds=elapsed,
                )
            except Exception:
                pass

        return result_dict