"""
Secure Run Workspace Writer (S3-04 — Mahmut Karaalioğlu).

Every file produced by a worker agent is written by the Master Orchestrator
through this module, and only inside ``<workspace_root>/<run_id>/``.

Rejected before anything touches the disk:
- empty names, NUL bytes, control characters
- absolute paths (``/etc/x``), drive letters (``C:\\x``, ``C:x``), UNC paths (``\\\\srv\\share``)
- any ``..`` segment, in either ``/`` or ``\\`` form
- Windows reserved device names (CON, NUL, COM1 ...) and trailing dots/spaces
- file extensions outside the allow-list
- paths that resolve outside the run directory (e.g. through a symlink)
- run_ids that are not a plain slug (a run_id must never be able to escape the root)

A batch of files is validated completely before the first write, so an unsafe
entry never leaves a half-written task output behind.
"""

import hashlib
import os
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../workspaces"))

ALLOWED_EXTENSIONS = frozenset({
    ".py", ".sql", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss",
    ".json", ".md", ".txt", ".yml", ".yaml", ".toml", ".ini", ".cfg",
})
MAX_FILE_BYTES = 1_000_000
MAX_PATH_DEPTH = 8

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
)


class UnsafePathError(ValueError):
    """A requested output path would escape (or is not allowed in) the run workspace."""


def _has_allowed_extension(name: str) -> bool:
    lower = name.lower()
    return any(lower.endswith(ext) for ext in ALLOWED_EXTENSIONS)


def validate_run_id(run_id: str) -> str:
    """A run_id becomes a directory name, so it must be a plain slug (no separators, no dots)."""
    if not isinstance(run_id, str) or not _RUN_ID_PATTERN.match(run_id):
        raise UnsafePathError(f"Geçersiz run_id (yalnızca harf, rakam, '-' ve '_' kullanılabilir): {run_id!r}")
    return run_id


def normalize_relative_path(relative_path: str) -> PurePosixPath:
    """
    Checks a relative output path from an agent and returns it as a clean POSIX path.
    Raises UnsafePathError for anything that could leave the workspace.
    """
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise UnsafePathError("Çıktı dosya yolu boş veya geçersiz.")
    if any(ord(ch) < 32 for ch in relative_path):
        raise UnsafePathError(f"Çıktı dosya yolunda kontrol karakteri var: {relative_path!r}")

    raw = relative_path.strip()
    win = PureWindowsPath(raw)
    normalized = raw.replace("\\", "/")
    if win.drive or win.anchor or normalized.startswith("/"):
        raise UnsafePathError(f"Mutlak yol kabul edilmez: '{relative_path}'")

    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    if not parts:
        raise UnsafePathError(f"Çıktı dosya yolu boş: '{relative_path}'")
    if any(p == ".." for p in parts):
        raise UnsafePathError(f"Yol geçişi (..) tespit edildi: '{relative_path}'")
    if len(parts) > MAX_PATH_DEPTH:
        raise UnsafePathError(f"Çıktı dosya yolu çok derin (en fazla {MAX_PATH_DEPTH} seviye): '{relative_path}'")

    for part in parts:
        if part != part.rstrip(" ."):
            raise UnsafePathError(f"Nokta veya boşlukla biten yol bileşeni kabul edilmez: '{relative_path}'")
        if part.split(".")[0].upper() in _WINDOWS_RESERVED:
            raise UnsafePathError(f"Ayrılmış aygıt adı kabul edilmez: '{relative_path}'")
        if ":" in part:
            raise UnsafePathError(f"Yol bileşeninde ':' kabul edilmez: '{relative_path}'")

    if not _has_allowed_extension(parts[-1]):
        raise UnsafePathError(f"İzin verilmeyen dosya uzantısı: '{relative_path}'")
    return PurePosixPath(*parts)


class RunWorkspace:
    """File writer bound to a single run directory: ``<root>/<run_id>/``."""

    def __init__(self, run_id: str, root: Optional[str] = None):
        self.run_id = validate_run_id(run_id)
        self.root = Path(root or os.environ.get("WORKSPACE_ROOT") or DEFAULT_WORKSPACE_ROOT).resolve()
        self.path = (self.root / self.run_id).resolve()
        if self.path.parent != self.root:
            raise UnsafePathError(f"Çalışma alanı kök dizin dışına çıkıyor: {self.path}")

    def resolve(self, relative_path: str) -> Path:
        """Returns the absolute target path inside this run directory, or raises UnsafePathError."""
        clean = normalize_relative_path(relative_path)
        candidate = self.path.joinpath(*clean.parts).resolve()
        if candidate == self.path or self.path not in candidate.parents:
            raise UnsafePathError(f"Çalışma alanı dışına yazma girişimi: '{relative_path}'")
        return candidate

    def _prepare(self, files: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        prepared, seen = [], set()
        for entry in files:
            if not isinstance(entry, dict):
                raise UnsafePathError(f"Dosya kaydı sözlük olmalı: {entry!r}")
            rel = entry.get("filename") or entry.get("path")
            content = entry.get("content")
            if not isinstance(content, str):
                raise UnsafePathError(f"'{rel}' için dosya içeriği metin olmalı.")
            data = content.encode("utf-8")
            if len(data) > MAX_FILE_BYTES:
                raise UnsafePathError(f"'{rel}' dosyası çok büyük ({len(data)} bayt > {MAX_FILE_BYTES}).")
            target = self.resolve(rel)
            key = str(target).lower()
            if key in seen:
                raise UnsafePathError(f"Aynı görevde aynı dosya iki kez yazılamaz: '{rel}'")
            seen.add(key)
            prepared.append({"target": target, "data": data})
        return prepared

    def write_files(self, files: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validates every entry first, then writes them all. Each entry needs
        ``filename`` (or ``path``) and string ``content``. Returns one record per
        written file: relative_path, absolute path, size_bytes, sha256.
        """
        prepared = self._prepare(files)
        written = []
        for item in prepared:
            target, data = item["target"], item["data"]
            target.parent.mkdir(parents=True, exist_ok=True)
            # Re-check after mkdir: a directory swapped for a symlink must not redirect the write
            if self.path not in target.resolve().parents:
                raise UnsafePathError(f"Çalışma alanı dışına yazma girişimi: '{target}'")
            target.write_bytes(data)
            written.append({
                "relative_path": target.relative_to(self.path).as_posix(),
                "path": str(target),
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })
        return written
