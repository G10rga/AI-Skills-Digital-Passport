"""SQLite store (stdlib sqlite3 — scales fine to 5,000+ passports/year;
swap the DSN for Postgres later without touching services).

Invariants enforced here + in services.sync:
- one passport per student (passports.student_id UNIQUE, passport_id PK)
- passport identity (name, passportId, firstIssued) written once, never updated
- versions are append-only; skills of a version are immutable once issued
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS passports(
  passport_id TEXT PRIMARY KEY, student_id TEXT NOT NULL UNIQUE,
  first_name TEXT NOT NULL, last_name TEXT NOT NULL, email TEXT DEFAULT '',
  program TEXT DEFAULT '', education_level TEXT DEFAULT '',
  student_status TEXT DEFAULT '', first_issued TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS versions(
  id INTEGER PRIMARY KEY, passport_id TEXT NOT NULL REFERENCES passports(passport_id),
  version INT NOT NULL, issued_at TEXT NOT NULL, document_hash TEXT NOT NULL UNIQUE,
  verification_code TEXT NOT NULL UNIQUE, tx_hash TEXT NOT NULL, network TEXT NOT NULL,
  block_number INT NOT NULL, issuer_signature TEXT NOT NULL DEFAULT '',
  UNIQUE(passport_id, version));
CREATE TABLE IF NOT EXISTS version_skills(
  version_id INT NOT NULL REFERENCES versions(id), record_id TEXT NOT NULL,
  skill_id TEXT NOT NULL, skill_name TEXT DEFAULT '', skill_category TEXT DEFAULT '',
  badge_code TEXT DEFAULT '', skill_description TEXT DEFAULT '', date_earned TEXT DEFAULT '',
  PRIMARY KEY(version_id, record_id));
CREATE TABLE IF NOT EXISTS records(
  record_id TEXT PRIMARY KEY, student_id TEXT DEFAULT '', first_name TEXT DEFAULT '',
  last_name TEXT DEFAULT '', email TEXT DEFAULT '', program TEXT DEFAULT '',
  education_level TEXT DEFAULT '', passport_id TEXT DEFAULT '', first_issued TEXT DEFAULT '',
  student_status TEXT DEFAULT '', skill_id TEXT DEFAULT '', skill_name TEXT DEFAULT '',
  skill_category TEXT DEFAULT '', badge_code TEXT DEFAULT '', skill_description TEXT DEFAULT '',
  date_earned TEXT DEFAULT '', sync_status TEXT, synced_version TEXT, synced_at TEXT,
  sync_notes TEXT, sheet_row INT);
CREATE INDEX IF NOT EXISTS idx_versions_passport ON versions(passport_id, version);
CREATE INDEX IF NOT EXISTS idx_records_passport ON records(passport_id, sync_status);
"""

RECORD_COLS = ["student_id", "first_name", "last_name", "email", "program", "education_level",
               "passport_id", "first_issued", "student_status", "record_id", "skill_id",
               "skill_name", "skill_category", "badge_code", "skill_description", "date_earned",
               "sync_status", "synced_version", "synced_at", "sync_notes", "sheet_row"]


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def reset(self) -> None:
        self.db.executescript("DELETE FROM version_skills; DELETE FROM versions;"
                              " DELETE FROM records; DELETE FROM passports;")
        self.db.commit()

    # ---- passports -------------------------------------------------
    def register_passport(self, r: dict) -> None:
        """Create the passport identity if absent. Existing identity is
        NEVER overwritten (name / Passport ID / firstIssued are frozen)."""
        self.db.execute(
            "INSERT OR IGNORE INTO passports VALUES (?,?,?,?,?,?,?,?,?)",
            (r.get("passportId", ""), r.get("studentId", ""), r.get("firstName", ""),
             r.get("lastName", ""), r.get("email", ""), r.get("program", ""),
             r.get("educationLevel", ""), r.get("studentStatus", ""), r.get("firstIssued", "")))
        self.db.commit()

    def get_passport(self, passport_id: str) -> Optional[dict]:
        row = self.db.execute("SELECT * FROM passports WHERE passport_id=?", (passport_id,)).fetchone()
        return dict(row) if row else None

    def get_passport_by_email(self, email: str) -> Optional[dict]:
        row = self.db.execute("SELECT * FROM passports WHERE lower(email)=lower(?)", (email,)).fetchone()
        return dict(row) if row else None

    def list_passports(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM passports ORDER BY passport_id")]

    # ---- versions --------------------------------------------------
    def get_versions(self, passport_id: str) -> list[dict]:
        out = []
        for v in self.db.execute("SELECT * FROM versions WHERE passport_id=? ORDER BY version", (passport_id,)):
            v = dict(v)
            v["skills"] = [dict(s) for s in self.db.execute(
                "SELECT record_id, skill_id, skill_name, skill_category, badge_code,"
                " skill_description, date_earned FROM version_skills WHERE version_id=?", (v["id"],))]
            out.append(v)
        return out

    def find_version_by_code(self, code: str) -> Optional[tuple[dict, dict]]:
        v = self.db.execute("SELECT * FROM versions WHERE verification_code=?", (code,)).fetchone()
        if not v:
            return None
        v = dict(v)
        v["skills"] = [dict(s) for s in self.db.execute(
            "SELECT record_id, skill_id, skill_name, skill_category, badge_code,"
            " skill_description, date_earned FROM version_skills WHERE version_id=?", (v["id"],))]
        return self.get_passport(v["passport_id"]), v

    def get_version(self, passport_id: str, version: int) -> Optional[dict]:
        rows = [v for v in self.get_versions(passport_id) if v["version"] == version]
        return rows[0] if rows else None

    def find_anchor(self, doc_hash: str) -> Optional[dict]:
        v = self.db.execute("SELECT * FROM versions WHERE document_hash=?", (doc_hash,)).fetchone()
        return dict(v) if v else None

    def add_version(self, passport_id: str, version: int, issued_at: str, doc_hash: str,
                    code: str, tx_hash: str, network: str, block_number: int,
                    signature: str, skills: list[dict]) -> None:
        cur = self.db.execute(
            "INSERT INTO versions(passport_id,version,issued_at,document_hash,verification_code,"
            "tx_hash,network,block_number,issuer_signature) VALUES (?,?,?,?,?,?,?,?,?)",
            (passport_id, version, issued_at, doc_hash, code, tx_hash, network, block_number, signature))
        self.db.executemany(
            "INSERT INTO version_skills VALUES (?,?,?,?,?,?,?,?)",
            [(cur.lastrowid, s["recordId"], s["skillId"], s["skillName"], s["skillCategory"],
              s["badgeCode"], s["skillDescription"], s["dateEarned"]) for s in skills])
        self.db.commit()

    # ---- sheet records (columns A-T) --------------------------------
    def upsert_record(self, r: dict, sheet_row: Optional[int] = None) -> None:
        """Insert a new sheet row, or refresh input columns A-P of an
        existing one. Q-T are system-managed: never overwritten on ingest,
        so a re-read of the sheet can't undo a sync."""
        existing = self.db.execute("SELECT record_id FROM records WHERE record_id=?",
                                   (r.get("recordId", ""),)).fetchone()
        if existing:
            self.db.execute(
                "UPDATE records SET student_id=?,first_name=?,last_name=?,email=?,program=?,"
                "education_level=?,passport_id=?,first_issued=?,student_status=?,skill_id=?,"
                "skill_name=?,skill_category=?,badge_code=?,skill_description=?,date_earned=?,"
                "sheet_row=COALESCE(?,sheet_row) WHERE record_id=?",
                (r.get("studentId", ""), r.get("firstName", ""), r.get("lastName", ""), r.get("email", ""),
                 r.get("program", ""), r.get("educationLevel", ""), r.get("passportId", ""),
                 r.get("firstIssued", ""), r.get("studentStatus", ""), r.get("skillId", ""),
                 r.get("skillName", ""), r.get("skillCategory", ""), r.get("badgeCode", ""),
                 r.get("skillDescription", ""), r.get("dateEarned", ""), sheet_row, r.get("recordId", "")))
        else:
            vals = [r.get(k, "") for k in
                    ["studentId", "firstName", "lastName", "email", "program", "educationLevel",
                     "passportId", "firstIssued", "studentStatus", "recordId", "skillId", "skillName",
                     "skillCategory", "badgeCode", "skillDescription", "dateEarned"]]
            vals += [r.get("syncStatus"), r.get("syncedVersion"), r.get("syncedAt"),
                     r.get("syncNotes"), sheet_row]
            cols = ["student_id", "first_name", "last_name", "email", "program", "education_level",
                    "passport_id", "first_issued", "student_status", "record_id", "skill_id",
                    "skill_name", "skill_category", "badge_code", "skill_description", "date_earned",
                    "sync_status", "synced_version", "synced_at", "sync_notes", "sheet_row"]
            self.db.execute(f"INSERT INTO records({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)
        self.db.commit()

    def list_records(self) -> list[dict]:
        keys = ["studentId", "firstName", "lastName", "email", "program", "educationLevel",
                "passportId", "firstIssued", "studentStatus", "recordId", "skillId", "skillName",
                "skillCategory", "badgeCode", "skillDescription", "dateEarned",
                "syncStatus", "syncedVersion", "syncedAt", "syncNotes"]
        return [dict(zip(keys, [row[c] for c in RECORD_COLS])) | {"sheetRow": row["sheet_row"]}
                for row in self.db.execute("SELECT * FROM records ORDER BY record_id")]

    def pending_records(self) -> list[dict]:
        return [r for r in self.list_records()
                if r["syncStatus"] not in ("SYNCED", "DUPLICATE")]

    def update_record_sync(self, record_id: str, status: str, version: Optional[str],
                           synced_at: Optional[str], notes: Optional[str]) -> None:
        self.db.execute("UPDATE records SET sync_status=?,synced_version=?,synced_at=?,sync_notes=?"
                        " WHERE record_id=?", (status, version, synced_at, notes, record_id))
        self.db.commit()

    def pending_count(self, passport_id: str) -> int:
        return self.db.execute(
            "SELECT COUNT(*) c FROM records WHERE passport_id=? AND sync_status NOT IN"
            " ('SYNCED','DUPLICATE')", (passport_id,)).fetchone()["c"]


def load_seed(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))
