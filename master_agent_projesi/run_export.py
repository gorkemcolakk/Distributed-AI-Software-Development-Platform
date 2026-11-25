"""
Zip export of one run: every generated file in a single download named after the project.

Pure functions (no Streamlit), so they are unit-tested in tests/test_run_export.py.
app.py only calls ``build_run_zip`` and passes the bytes to ``st.download_button``.
"""

import io
import re
import zipfile
from pathlib import PurePosixPath
from typing import Dict, Iterable, Optional, Tuple

# Turkish letters have no ASCII decomposition, so they are mapped by hand
_TR = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
                     "Ç": "c", "Ğ": "g", "İ": "i", "I": "i", "Ö": "o", "Ş": "s", "Ü": "u"})
MAX_NAME_LENGTH = 40


def safe_project_name(project_title: Optional[str], fallback: str = "proje") -> str:
    """'Restoran Sipariş Sistemi!' -> 'restoran-siparis-sistemi' (safe as a file and folder name)."""
    text = str(project_title or "").translate(_TR).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:MAX_NAME_LENGTH].strip("-")
    return slug or fallback


def _safe_member(relative_path: str) -> Optional[str]:
    """Relative path inside the zip, or None when it is empty, absolute or climbs out with '..'."""
    normalized = str(relative_path or "").replace("\\", "/").strip()
    if not normalized or normalized.startswith("/") or re.match(r"^[a-zA-Z]:", normalized):
        return None
    parts = [p for p in PurePosixPath(normalized).parts if p not in ("", ".")]
    if not parts or ".." in parts:
        return None
    return "/".join(parts)


def build_run_zip(project_title: Optional[str], files: Iterable[Dict], fallback_name: str = "proje"
                  ) -> Tuple[str, bytes, int]:
    """
    files: dicts with "file" (relative path) and "content" (text or None).
    Returns (zip_file_name, zip_bytes, file_count). Files without content or with an unsafe path are skipped.
    The files sit in one top folder with the project name, so unzipping never spills into the current folder.
    """
    name = safe_project_name(project_title, fallback_name)
    buffer = io.BytesIO()
    seen = set()
    count = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for row in files:
            member = _safe_member(row.get("file"))
            content = row.get("content")
            if member is None or not isinstance(content, str) or member in seen:
                continue
            seen.add(member)
            archive.writestr(f"{name}/{member}", content.encode("utf-8"))
            count += 1
    return f"{name}.zip", buffer.getvalue(), count
