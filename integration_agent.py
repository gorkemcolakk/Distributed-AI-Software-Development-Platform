import os
import ast
import requests
from typing import Dict, List
from contracts import IntegrationFinding, IntegrationReportContract_v1

class IntegrationAgent:
    def __init__(self, model_name: str = "phi4-mini:3.8b", ollama_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.ollama_url = f"{ollama_url}/api/generate"

    def inspect_directory(self, run_id: str, directory_path: str) -> IntegrationReportContract_v1:
        """Fiziksel bir klasördeki gerçek çıktı dosyalarını okur ve inceler."""
        files_content: Dict[str, str] = {}
        if os.path.exists(directory_path):
            for fname in os.listdir(directory_path):
                fpath = os.path.join(directory_path, fname)
                if os.path.isfile(fpath):
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        files_content[fname] = f.read()
        return self.inspect_files(run_id, files_content)

    def inspect_files(self, run_id: str, files: Dict[str, str]) -> IntegrationReportContract_v1:
        """Ajanların ürettiği gerçek dosya içeriklerini inceler ve uygulanabilir bulgular üretir."""
        findings: List[IntegrationFinding] = []
        inspected = list(files.keys())

        # 1. KURAL: Hiç dosya üretilmemişse
        if not files:
            findings.append(IntegrationFinding(
                file_name="PROJECT_ROOT",
                severity="CRITICAL",
                issue="İncelenecek hiçbir çıktı dosyası bulunamadı.",
                actionable_suggestion="İşçi ajanların (Database, Backend, Frontend, Testing) çıktı ürettiğinden emin olun."
            ))
            return IntegrationReportContract_v1(
                run_id=run_id, overall_status="FAILED", inspected_files=[], findings=findings
            )

        # 2. KURAL: Tekil Dosya Kontrolleri (Sentaks ve Yapı)
        for fname, content in files.items():
            if not content.strip():
                findings.append(IntegrationFinding(
                    file_name=fname,
                    severity="CRITICAL",
                    issue="Dosya tamamen boş.",
                    actionable_suggestion=f"{fname} dosyasını üreten ajanın promptunu ve model çıktısını kontrol edin."
                ))
                continue

            # Python dosyaları için gerçek AST Sentaks kontrolü (main.py, test_*.py)
            if fname.endswith(".py"):
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    findings.append(IntegrationFinding(
                        file_name=fname,
                        severity="CRITICAL",
                        issue=f"Python yazım (syntax) hatası: {e.msg} (Satır {e.lineno})",
                        actionable_suggestion=f"{fname} dosyasının {e.lineno}. satırındaki parantez veya girinti hatasını düzeltin."
                    ))

            # SQL dosyaları kontrolü (schema.sql)
            elif fname.endswith(".sql"):
                if "CREATE TABLE" not in content.upper():
                    findings.append(IntegrationFinding(
                        file_name=fname,
                        severity="WARNING",
                        issue="SQL dosyasında 'CREATE TABLE' ifadesi bulunamadı.",
                        actionable_suggestion="Database Agent'ın tablo oluşturma komutlarını eksiksiz ürettiğini doğrulayın."
                    ))

            # HTML dosyaları kontrolü (index.html)
            elif fname.endswith(".html"):
                if "<html" not in content.lower() and "<body" not in content.lower() and "<form" not in content.lower():
                    findings.append(IntegrationFinding(
                        file_name=fname,
                        severity="WARNING",
                        issue="Standart HTML yapı etiketleri (<html>, <body> veya <form>) eksik.",
                        actionable_suggestion="Frontend Agent'ın geçerli bir HTML şablonu döndürdüğünden emin olun."
                    ))

        # 3. KURAL: Ajanlar Arası Çapraz Uyumluluk Kontrolü (Cross-File Check)
        if "schema.sql" in files and "main.py" in files:
            sql_lower = files["schema.sql"].lower()
            py_lower = files["main.py"].lower()
            if "users" in sql_lower and "user" not in py_lower:
                findings.append(IntegrationFinding(
                    file_name="main.py & schema.sql",
                    severity="WARNING",
                    issue="schema.sql içinde 'users' tablosu tanımlanmış ancak main.py içinde kullanıcı modeline/tablosuna referans görünmüyor.",
                    actionable_suggestion="Backend Agent'a schema.sql içeriğini context olarak gönderip tablolarla eşleşen endpoint yazmasını sağlayın."
                ))

        # 4. KURAL: Yerel Ollama Modeli (phi4-mini:3.8b) ile Akıllı Code Review
        llm_summary = self._ask_ollama_review(files)

        has_critical = any(f.severity == "CRITICAL" for f in findings)
        status = "FAILED" if has_critical else "PASSED"

        return IntegrationReportContract_v1(
            run_id=run_id,
            overall_status=status,
            inspected_files=inspected,
            findings=findings,
            llm_review_summary=llm_summary
        )

    def _ask_ollama_review(self, files: Dict[str, str]) -> str:
        """Yerel Ollama modeline (phi4-mini:3.8b) dosyaları inceletir."""
        prompt = (
            "Sen bir Integration ve Code Review Ajanısın. Aşağıdaki proje dosyalarını incele ve "
            "birbiriyle uyumlu olup olmadığını, eksik bir kısım varsa nasıl düzeltileceğini kısaca Türkçe özetle:\n\n"
        )
        for name, code in files.items():
            prompt += f"=== DOSYA: {name} ===\n{code[:600]}\n\n"

        try:
            response = requests.post(
                self.ollama_url,
                json={"model": self.model_name, "prompt": prompt, "stream": False},
                timeout=20
            )
            if response.status_code == 200:
                return response.json().get("response", "").strip()
        except Exception:
            return "Yerel Ollama servisine ulaşılamadı; statik AST ve kural tabanlı denetim bulguları yukarıda raporlanmıştır."
        return ""