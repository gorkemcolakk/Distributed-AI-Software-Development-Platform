"""
Reproducible local model smoke test for S1-06 (docs/MODEL_RESEARCH.md).

Runs two fixed tasks against a local Ollama server and writes a JSON evidence file:
  1. json_task   - decompose a requirement into JSON subtasks (parse + schema check)
  2. coding_task - write a Python function, then run fixed asserts against it

It also records a hardware fit check (RAM/VRAM vs. model size, `ollama list`) for each model.

Usage:
  python scripts/model_smoke_test.py --member kubra --model qwen2.5-coder:3b --model gemma2:2b
  python scripts/model_smoke_test.py --member kubra --model gemma2:2b --check-only   # hardware only

No hostnames, usernames or secrets are recorded; only OS, CPU, RAM, GPU name and Ollama output.
Note: the coding task executes model-generated code in a subprocess on your machine.
"""

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone

OLLAMA_OPTIONS = {"temperature": 0, "seed": 42}

# Approximate default-quantization download sizes (GB) from the Ollama library, used when the
# model is not installed yet. The size reported by `ollama list` takes precedence.
MODEL_SIZE_GB = {
    "qwen2.5:3b": 1.9, "phi4-mini:3.8b": 2.5, "llama3.2:3b": 2.0, "qwen2.5-coder:7b": 4.7,
    "qwen2.5-coder:3b": 1.9, "gemma2:2b": 1.6, "deepseek-coder:6.7b": 3.8,
}
# Headroom on top of the model file for KV cache, runtime and OS (see docs/MODEL_RESEARCH.md 3.3)
VRAM_OVERHEAD_GB = 1.0
RAM_OVERHEAD_GB = 3.0
ALLOWED_CATEGORIES = {"REQUIREMENTS", "FRONTEND", "BACKEND", "DATABASE", "TESTING", "INTEGRATION", "DOCUMENTATION"}

JSON_PROMPT = """Decompose this requirement into subtasks.
Requirement: "Users can register with email and password, log in, and see a list of their saved notes."
Respond with JSON only, no prose, using exactly this shape:
{"subtasks": [{"id": "T1", "title": "...", "category": "BACKEND", "depends_on": []}]}
Allowed categories: REQUIREMENTS, FRONTEND, BACKEND, DATABASE, TESTING, INTEGRATION, DOCUMENTATION.
Return between 3 and 8 subtasks."""

CODING_PROMPT = """Write a Python function `is_palindrome(s: str) -> bool` that returns True if `s`
is a palindrome when ignoring case and all non-alphanumeric characters.
Return only one Python code block, no explanation."""

CODING_ASSERTS = """
assert is_palindrome("A man, a plan, a canal: Panama") is True
assert is_palindrome("race a car") is False
assert is_palindrome("") is True
assert is_palindrome("No 'x' in Nixon") is True
assert is_palindrome("ab") is False
print("ASSERTS_OK")
"""


def run_cmd(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return (out.stdout or out.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"unavailable ({e.__class__.__name__})"


def total_ram_gb():
    try:
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3, 1)
    except (ValueError, OSError, AttributeError):
        pass
    if platform.system() == "Darwin":
        out = run_cmd(["sysctl", "-n", "hw.memsize"])
        return round(int(out) / 1024 ** 3, 1) if out.isdigit() else None
    if platform.system() == "Windows":
        import ctypes

        class MemStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        stat = MemStatus()
        stat.dwLength = ctypes.sizeof(MemStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return round(stat.ullTotalPhys / 1024 ** 3, 1)
    return None


def machine_info():
    return {
        "os": f"{platform.system()} {platform.release()}",
        "cpu": platform.processor() or platform.machine(),
        "ram_gb": total_ram_gb(),
        "gpu": run_cmd(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"]),
        "ollama_version": run_cmd(["ollama", "--version"]),
        "ollama_list": run_cmd(["ollama", "list"]),
    }


def parse_ollama_list(text):
    """Returns {tag: size_gb} from `ollama list` output."""
    models = {}
    for line in text.splitlines()[1:]:
        match = re.match(r"(\S+)\s+\S+\s+([\d.]+)\s*(GB|MB)", line)
        if match:
            size = float(match.group(2))
            models[match.group(1)] = size if match.group(3) == "GB" else round(size / 1024, 2)
    return models


def parse_vram_gb(gpu_text):
    """Largest single-GPU memory from `nvidia-smi` csv output, e.g. 'RTX 3060, 12288 MiB'."""
    sizes = [int(m) / 1024 for m in re.findall(r"(\d+)\s*MiB", gpu_text)]
    return round(max(sizes), 1) if sizes else None


def hardware_fit(model, machine):
    installed = parse_ollama_list(machine["ollama_list"])
    tag = model if ":" in model else f"{model}:latest"
    size, source = installed.get(tag), "ollama list"
    if size is None:
        size, source = MODEL_SIZE_GB.get(tag), "reference table"
    vram = parse_vram_gb(machine["gpu"])
    ram = machine["ram_gb"]
    apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"

    if size is None or ram is None:
        placement = "unknown"
    elif vram is not None and vram >= size + VRAM_OVERHEAD_GB:
        placement = "gpu"
    elif apple_silicon and ram >= size + RAM_OVERHEAD_GB:
        placement = "gpu_unified_memory"
    elif ram >= size + RAM_OVERHEAD_GB:
        placement = "cpu_only"
    else:
        placement = "insufficient"
    return {
        "installed": tag in installed,
        "model_size_gb": size,
        "size_source": source,
        "vram_gb": vram,
        "required_vram_gb": round(size + VRAM_OVERHEAD_GB, 1) if size else None,
        "required_ram_gb": round(size + RAM_OVERHEAD_GB, 1) if size else None,
        "placement": placement,
    }


def generate(host, model, prompt):
    body = json.dumps({"model": model, "prompt": prompt, "stream": False, "options": OLLAMA_OPTIONS}).encode()
    req = urllib.request.Request(f"{host}/api/generate", data=body, headers={"Content-Type": "application/json"})
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read())
    wall = time.perf_counter() - start
    eval_s = data.get("eval_duration", 0) / 1e9
    return data.get("response", ""), {
        "wall_seconds": round(wall, 2),
        "output_tokens": data.get("eval_count"),
        "tokens_per_second": round(data["eval_count"] / eval_s, 1) if eval_s and data.get("eval_count") else None,
    }


def check_json_task(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return False, "no JSON object found"
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        return False, f"invalid JSON: {e}"
    subtasks = data.get("subtasks")
    if not isinstance(subtasks, list) or not 3 <= len(subtasks) <= 8:
        return False, "subtasks missing or count not in 3-8"
    ids = {t.get("id") for t in subtasks if isinstance(t, dict)}
    for t in subtasks:
        if not isinstance(t, dict) or not {"id", "title", "category", "depends_on"} <= t.keys():
            return False, "subtask missing required keys"
        if t["category"] not in ALLOWED_CATEGORIES:
            return False, f"invalid category {t['category']!r}"
        if not isinstance(t["depends_on"], list) or not set(t["depends_on"]) <= ids:
            return False, "depends_on references unknown id"
    return True, f"{len(subtasks)} valid subtasks"


def check_coding_task(text):
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    code = match.group(1) if match else text
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code + "\n" + CODING_ASSERTS)
        path = f.name
    try:
        out = subprocess.run([sys.executable, "-I", path], capture_output=True, text=True, timeout=15)
        if "ASSERTS_OK" in out.stdout:
            return True, "all asserts passed"
        return False, (out.stderr.strip().splitlines() or ["no output"])[-1]
    except subprocess.TimeoutExpired:
        return False, "timeout"
    finally:
        os.unlink(path)


def run_model(host, model, runs):
    results = []
    for name, prompt, checker in (("json_task", JSON_PROMPT, check_json_task),
                                  ("coding_task", CODING_PROMPT, check_coding_task)):
        for i in range(runs):
            try:
                text, timing = generate(host, model, prompt)
                ok, detail = checker(text)
                results.append({"task": name, "run": i + 1, "passed": ok, "detail": detail, **timing,
                                "response_excerpt": text[:500]})
            except Exception as e:  # record any failure as evidence instead of aborting
                results.append({"task": name, "run": i + 1, "passed": False, "detail": f"error: {e}"})
    return results


def summarize(results):
    summary = {}
    for task in ("json_task", "coding_task"):
        rows = [r for r in results if r["task"] == task]
        walls = sorted(r["wall_seconds"] for r in rows if "wall_seconds" in r)
        summary[task] = {
            "pass_rate": f"{sum(r['passed'] for r in rows)}/{len(rows)}",
            "median_wall_seconds": walls[len(walls) // 2] if walls else None,
        }
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--member", required=True, help="team member short name, e.g. kubra")
    parser.add_argument("--model", action="append", required=True, help="Ollama tag; repeat to compare models")
    parser.add_argument("--host", default="http://localhost:11434")
    parser.add_argument("--runs", type=int, default=3, help="runs per task (default 3)")
    parser.add_argument("--out-dir", default="docs/model_tests")
    parser.add_argument("--check-only", action="store_true",
                        help="only record hardware fit and `ollama list`, skip the test tasks")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    machine = machine_info()
    for model in args.model:
        fit = hardware_fit(model, machine)
        results = [] if args.check_only else run_model(args.host, model, args.runs)
        record = {
            "member": args.member,
            "model": model,
            "date_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "options": OLLAMA_OPTIONS,
            "machine": machine,
            "hardware_fit": fit,
            "summary": None if args.check_only else summarize(results),
            "results": results,
        }
        print(f"{model}: installed={fit['installed']} placement={fit['placement']} "
              f"(size {fit['model_size_gb']} GB, RAM {machine['ram_gb']} GB, VRAM {fit['vram_gb']} GB)")
        safe_model = re.sub(r"[^A-Za-z0-9.-]+", "_", model)
        path = os.path.join(args.out_dir, f"{args.member}_{safe_model}_{datetime.now():%Y%m%d}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        if record["summary"]:
            print(f"  summary: {record['summary']}")
        print(f"  evidence: {path}")


if __name__ == "__main__":
    main()
