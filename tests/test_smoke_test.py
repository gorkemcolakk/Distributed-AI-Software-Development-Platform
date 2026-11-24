"""
S5 (Eren Görkem Çolak): the Master's smoke test starts the generated FastAPI backend in a child
process and calls the contract's endpoints. Small hand-written backends stand in for generated code;
no network, no Ollama, no real state.db.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.master import smoke_test
from src.master.orchestrator import MasterOrchestrator

GOOD = '''
import sqlite3, hashlib, secrets
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
db = sqlite3.connect("app.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT)")
db.execute("CREATE TABLE IF NOT EXISTS dishes (id INTEGER PRIMARY KEY, name TEXT, price REAL)")

class Auth(BaseModel):
    username: str
    password: str

class Dish(BaseModel):
    id: Optional[int] = None
    name: str
    price: float

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/register", status_code=201)
def register(a: Auth):
    db.execute("INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
               (a.username, hashlib.sha256(a.password.encode()).hexdigest()))
    return {"username": a.username}

@app.post("/login")
def login(a: Auth):
    row = db.execute("SELECT password_hash FROM users WHERE username = ?", (a.username,)).fetchone()
    if not row or row[0] != hashlib.sha256(a.password.encode()).hexdigest():
        raise HTTPException(401, "bad credentials")
    return {"token": secrets.token_hex(8)}

@app.post("/dishes", status_code=201)
def add(d: Dish):
    cur = db.execute("INSERT INTO dishes (name, price) VALUES (?, ?)", (d.name, d.price))
    return {"id": cur.lastrowid, "name": d.name, "price": d.price}

@app.get("/dishes")
def dishes():
    return [{"id": r[0], "name": r[1], "price": r[2]} for r in db.execute("SELECT id, name, price FROM dishes")]
'''

CRASHES_ON_POST = '''
from fastapi import FastAPI
from pydantic import BaseModel
app = FastAPI()
class Dish(BaseModel):
    name: str
@app.get("/health")
def health():
    return {"status": "ok"}
@app.post("/dishes")
def add(d: Dish):
    d.id = 1  # the 24 Nov bug: assigning a field the model does not have
    return d
@app.get("/dishes")
def dishes():
    return []
'''

BROKEN_IMPORT = '''
from fastapi import FastAPI
import module_that_does_not_exist
app = FastAPI()
'''

CONTRACT = {"endpoints": [
    {"method": "POST", "path": "/register", "request": ["username", "password"]},
    {"method": "POST", "path": "/login", "request": ["username", "password"]},
    {"method": "POST", "path": "/dishes", "request": ["name", "price"]},
    {"method": "GET", "path": "/dishes"},
]}


def workspace(files):
    tmp = tempfile.TemporaryDirectory()
    for name, text in files.items():
        path = Path(tmp.name) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp


class TestSmokeTest(unittest.TestCase):

    def test_working_app_passes_and_login_returns_a_token(self):
        with workspace({"backend_task_be_1.py": GOOD, "test_task_qa_1.py": "def test_x(): pass\n"}) as ws:
            result = smoke_test.run_smoke_test(ws, CONTRACT)
            self.assertEqual(result["status"], "PASSED", result)
            self.assertEqual(result["backend_file"], "backend_task_be_1.py")
            codes = {(c["method"], c["path"]): c["status_code"] for c in result["checks"]}
            self.assertEqual(codes[("GET", "/health")], 200)
            self.assertEqual(codes[("POST", "/login")], 200)  # the registered user really logs in
            self.assertEqual(codes[("POST", "/dishes")], 201)
            self.assertFalse((Path(ws) / "app.db").exists())  # ran on a copy, workspace untouched

    def test_endpoint_that_crashes_fails_the_smoke_test(self):
        with workspace({"backend.py": CRASHES_ON_POST}) as ws:
            result = smoke_test.run_smoke_test(ws, {"endpoints": [
                {"method": "POST", "path": "/dishes", "request": ["name"]}, {"method": "GET", "path": "/dishes"}]})
            self.assertEqual(result["status"], "FAILED")
            bad = [c for c in result["checks"] if not c["ok"]]
            self.assertEqual([(c["method"], c["path"]) for c in bad], [("POST", "/dishes")])

    def test_app_that_does_not_start_fails_with_the_reason(self):
        with workspace({"backend.py": BROKEN_IMPORT}) as ws:
            result = smoke_test.run_smoke_test(ws, CONTRACT)
            self.assertEqual(result["status"], "FAILED")
            self.assertIn("uygulama başlamadı", result["reason"])
            self.assertIn("module_that_does_not_exist", result["reason"])

    def test_contract_route_that_was_never_written_fails(self):
        with workspace({"backend.py": GOOD}) as ws:
            result = smoke_test.run_smoke_test(ws, {"endpoints": [
                {"method": "GET", "path": "/orders"},           # not in the app -> missing
                {"method": "GET", "path": "/dishes/{dish_id}"},  # param path: a 404 is allowed
                {"method": "GET", "path": "/dishes/:id"}]})
            self.assertEqual(result["status"], "FAILED")
            ok = {c["path"]: c["ok"] for c in result["checks"]}
            self.assertFalse(ok["/orders"])
            self.assertTrue(ok["/dishes/{dish_id}"])
            self.assertTrue(ok["/dishes/:id"])

    def test_no_backend_is_skipped(self):
        with workspace({"ui.html": "<html></html>", "test_api.py": "from fastapi import FastAPI\napp = FastAPI()\n"}) as ws:
            self.assertEqual(smoke_test.run_smoke_test(ws, CONTRACT)["status"], "SKIPPED")
        self.assertEqual(smoke_test.run_smoke_test(None, CONTRACT)["status"], "SKIPPED")

    def test_it_is_off_unless_switched_on(self):
        with patch.dict(os.environ, {"MASTER_SMOKE_TEST": ""}):
            self.assertFalse(smoke_test.is_enabled())
        with patch.dict(os.environ, {"MASTER_SMOKE_TEST": "true"}):
            self.assertTrue(smoke_test.is_enabled())

    def test_report_has_no_smoke_test_when_off(self):
        with patch.dict(os.environ, {"MASTER_SMOKE_TEST": "false"}):
            report = MasterOrchestrator(persist=False).process_requirement("Small app", "Small")
        self.assertIsNone(report["smoke_test"])


if __name__ == "__main__":
    unittest.main()
