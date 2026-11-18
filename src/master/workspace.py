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

S4-04 — path conflicts between tasks of the same run:
- A file written by one task is never overwritten by another task.
- Same path + identical content (same SHA-256)  -> DEDUPLICATED: nothing is
  written, the second task simply references the existing file.
- Same path + different content -> RENAMED: the later version is written next
  to the original as ``<stem>.<task_id><ext>`` (e.g. ``api/main.task_3.py``),
  so both versions survive and the conflict is reported.
Every conflict is returned on the written-file record and kept in
``RunWorkspace.conflicts`` so the orchestrator can persist it and hand it to
the Integration Agent.
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


def _owner_slug(owner: Optional[str]) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", owner or "").strip("_-")[:40]
    return slug or "conflict"


class RunWorkspace:
    """File writer bound to a single run directory: ``<root>/<run_id>/``."""

    def __init__(self, run_id: str, root: Optional[str] = None):
        self.run_id = validate_run_id(run_id)
        self.root = Path(root or os.environ.get("WORKSPACE_ROOT") or DEFAULT_WORKSPACE_ROOT).resolve()
        self.path = (self.root / self.run_id).resolve()
        if self.path.parent != self.root:
            raise UnsafePathError(f"Çalışma alanı kök dizin dışına çıkıyor: {self.path}")
        # S4-04: case-insensitive absolute path -> {"owner", "relative_path", "sha256"}
        self._registry: Dict[str, Dict[str, Any]] = {}
        self.conflicts: List[Dict[str, Any]] = []

    @staticmethod
    def _key(target: Path) -> str:
        return str(target).lower()

    def owner_of(self, relative_path: str) -> Optional[str]:
        """Returns the task that first wrote ``relative_path`` in this run (None if unknown)."""
        entry = self._registry.get(self._key(self.resolve(relative_path)))
        return entry["owner"] if entry else None

    def _existing(self, target: Path) -> Optional[Dict[str, Any]]:
        """Who already holds this target: a task of this run, or an untracked file on disk."""
        entry = self._registry.get(self._key(target))
        if entry:
            return entry
        if target.is_file():
            return {
                "owner": None,
                "untracked": True,
                "relative_path": target.relative_to(self.path).as_posix(),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        return None

    def _alternate_target(self, target: Path, owner: Optional[str], taken: set) -> Path:
        """``<stem>.<owner><ext>``, then ``<stem>.<owner>-2<ext>`` ... until a free name is found."""
        clean = PurePosixPath(target.relative_to(self.path).as_posix())
        base = f"{clean.stem}.{_owner_slug(owner)}"
        for counter in range(1, 1000):
            name = base if counter == 1 else f"{base}-{counter}"
            candidate = self.resolve(str(clean.with_name(f"{name}{clean.suffix}")))
            key = self._key(candidate)
            if key not in taken and key not in self._registry and not candidate.exists():
                return candidate
        raise UnsafePathError(f"'{clean}' için çakışmasız bir dosya adı bulunamadı.")

    def resolve(self, relative_path: str) -> Path:
        """Returns the absolute target path inside this run directory, or raises UnsafePathError."""
        clean = normalize_relative_path(relative_path)
        candidate = self.path.joinpath(*clean.parts).resolve()
        if candidate == self.path or self.path not in candidate.parents:
            raise UnsafePathError(f"Çalışma alanı dışına yazma girişimi: '{relative_path}'")
        return candidate

    def _prepare(self, files: Iterable[Dict[str, Any]], owner: Optional[str] = None) -> List[Dict[str, Any]]:
        # Pass 1: validate every entry (nothing is resolved or written yet)
        entries, seen = [], set()
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
            key = self._key(target)
            if key in seen:
                raise UnsafePathError(f"Aynı görevde aynı dosya iki kez yazılamaz: '{rel}'")
            seen.add(key)
            entries.append({"target": target, "data": data, "sha256": hashlib.sha256(data).hexdigest()})

        # Pass 2: resolve conflicts with files written earlier by other tasks of this run
        taken = set(seen)
        prepared = []
        for item in entries:
            target, sha = item["target"], item["sha256"]
            requested = target.relative_to(self.path).as_posix()
            item.update(requested_path=requested, conflict=None, write=True)
            existing = self._existing(target)
            if existing and (existing.get("untracked") or existing["owner"] != owner):
                conflict = {
                    "conflict_type": "PATH",
                    "file_path": requested,
                    "task_id": owner,
                    "other_task_id": existing["owner"],
                }
                if existing["sha256"] == sha:
                    conflict.update(resolution="DEDUPLICATED", resolved_path=requested,
                                    detail="Aynı yol ve aynı içerik (SHA-256 eşleşti); dosya tekrar yazılmadı.")
                    item["write"] = False
                else:
                    alternate = self._alternate_target(target, owner, taken)
                    taken.add(self._key(alternate))
                    alt_rel = alternate.relative_to(self.path).as_posix()
                    holder = existing["owner"] or "diskteki mevcut dosya"
                    conflict.update(resolution="RENAMED", resolved_path=alt_rel,
                                    detail=f"'{requested}' zaten '{holder}' tarafından farklı içerikle yazılmıştı; "
                                           f"bu sürüm '{alt_rel}' olarak kaydedildi.")
                    item["target"] = alternate
                item["conflict"] = conflict
            prepared.append(item)
        return prepared

    def write_files(self, files: Iterable[Dict[str, Any]], owner: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Validates every entry first, then writes them all. Each entry needs
        ``filename`` (or ``path``) and string ``content``. ``owner`` is the task_id
        producing the files; it is used to detect path conflicts between tasks (S4-04).

        Returns one record per file: relative_path (where the content actually is),
        requested_path, absolute path, size_bytes, sha256 and conflict (None or a dict
        with conflict_type / resolution / resolved_path / other_task_id / detail).
        """
        prepared = self._prepare(files, owner=owner)
        written = []
        for item in prepared:
            target, data = item["target"], item["data"]
            if item["write"]:
                target.parent.mkdir(parents=True, exist_ok=True)
                # Re-check after mkdir: a directory swapped for a symlink must not redirect the write
                if self.path not in target.resolve().parents:
                    raise UnsafePathError(f"Çalışma alanı dışına yazma girişimi: '{target}'")
                target.write_bytes(data)
            relative = target.relative_to(self.path).as_posix()
            key = self._key(target)
            if key not in self._registry or self._registry[key]["owner"] == owner:
                self._registry[key] = {"owner": owner, "relative_path": relative, "sha256": item["sha256"]}
            if item["conflict"]:
                self.conflicts.append(item["conflict"])
            written.append({
                "relative_path": relative,
                "requested_path": item["requested_path"],
                "path": str(target),
                "size_bytes": len(data),
                "sha256": item["sha256"],
                "conflict": item["conflict"],
            })
        return written
