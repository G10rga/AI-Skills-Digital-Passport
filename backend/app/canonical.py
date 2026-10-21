"""Canonical passport content + SHA-256 — MUST byte-match the frontend.

Mirror of `canonicalPassport()` / `sha256()` in frontend/src/lib/api.ts:
JSON with keys in that exact order, no spaces, skills sorted by recordId,
each skill as [skillId, skillName, skillCategory, badgeCode, dateEarned,
skillDescription]. Changing any byte here breaks verification against
documents the frontend/mock already issued — there is a parity test.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _field(skill: Any, name: str) -> str:
    if isinstance(skill, Mapping):
        return str(skill.get(name, ""))
    return str(getattr(skill, name, ""))


def canonical_passport(passport_id: str, first_name: str, last_name: str,
                       first_issued: str, version: int, skills: Iterable[Any],
                       issuer_did: str) -> str:
    ordered = sorted(skills, key=lambda s: _field(s, "recordId"))
    payload = {
        "passportId": passport_id,
        "firstName": first_name,
        "lastName": last_name,
        "firstIssued": first_issued,
        "version": version,
        "issuer": issuer_did,
        "skills": [[
            _field(s, "skillId"), _field(s, "skillName"), _field(s, "skillCategory"),
            _field(s, "badgeCode"), _field(s, "dateEarned"), _field(s, "skillDescription"),
        ] for s in ordered],
    }
    # JS JSON.stringify: compact, non-ASCII kept raw.
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def document_hash(passport_id: str, first_name: str, last_name: str,
                  first_issued: str, version: int, skills: Iterable[Any],
                  issuer_did: str) -> str:
    return sha256_hex(canonical_passport(
        passport_id, first_name, last_name, first_issued, version, skills, issuer_did))


def verification_code(passport_id: str, version: int, doc_hash: str) -> str:
    """`{passport digits}-V{n}-{first 8 hash chars}` — same format as the UI."""
    return f"{passport_id.replace('BTU-AI-', '')}-V{version}-{doc_hash[:8].upper()}"
