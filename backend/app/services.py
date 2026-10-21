"""Core computation: seeding, version issuance, sheet sync, verification.
Pure Python — no web framework in here, so every rule is unit-testable.
Rules mirror the frontend mock (frontend/src/lib/api.ts) exactly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from . import canonical
from .models import (Issuer, Passport, PassportInfo, PassportSkill, PassportSummary,
                     PassportVersion, SkillRecord, SyncResult, SyncLogEntry,
                     VerifyResult, VerifyDocumentResult)
from .sheets import SheetSource

REQUIRED = ("studentId", "passportId", "recordId", "skillId", "skillName",
            "skillCategory", "badgeCode", "dateEarned")


class AppContext:
    """Everything issue/verify needs that endpoints shouldn't rebuild."""

    def __init__(self, settings, signer, anchor):
        self.settings, self.signer, self.anchor = settings, signer, anchor
        self.issuer_name, self.issuer_did = settings.issuer_name, settings.issuer_did
        self.issuer_wallet = settings.issuer_wallet


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sheet_timestamp(iso: str) -> str:
    """`2026-10-17 10:00 UTC` — the format written back to sheet column S."""
    return iso[:16].replace("T", " ") + " UTC"


def seed_synced_at(raw: Optional[str]) -> str:
    """Sheet `2026-10-17 10:00 UTC` -> ISO 8601 `2026-10-17T10:00:00Z`."""
    if not raw:
        return now_iso()
    s = raw.strip().removesuffix(" UTC").replace(" ", "T")
    if not s.endswith("Z"):
        s += "Z"
    return s[:-1] + ":00Z" if s.count(":") == 1 else s


# ---------------------------------------------------------------- seeding
def seed(store, records: list[dict], ctx) -> None:
    """Initial load: register every passport, then issue V1 from the rows
    already marked SYNCED (exactly what the frontend mock does)."""
    if store.list_passports():
        return
    for r in records:
        store.register_passport(r)
        store.upsert_record(r, r.get("_sheetRow"))
    by_passport: dict[str, list[dict]] = {}
    for r in records:
        if r.get("syncStatus") == "SYNCED":
            by_passport.setdefault(r["passportId"], []).append(r)
    for passport_id, recs in by_passport.items():
        issued = seed_synced_at(recs[0].get("syncedAt"))
        issue_version(store, store.get_passport(passport_id), 1,
                      [to_skill(r) for r in recs], issued, ctx)


def to_skill(r: dict) -> dict:
    return {"recordId": r["recordId"], "skillId": r["skillId"], "skillName": r["skillName"],
            "skillCategory": r["skillCategory"], "badgeCode": r["badgeCode"],
            "skillDescription": r["skillDescription"], "dateEarned": r["dateEarned"]}


# ------------------------------------------------------------- versioning
def issue_version(store, passport: dict, version: int, skills: list[dict],
                  issued_at: str, ctx) -> PassportVersion:
    """Hash canonical content -> sign as BTU -> anchor on-chain -> persist.
    `ctx` carries issuer/anchor/settings (see main.make_context)."""
    doc_hash = canonical.document_hash(
        passport["passport_id"], passport["first_name"], passport["last_name"],
        passport["first_issued"], version, skills, ctx.issuer_did)
    anchor = ctx.anchor.anchor(doc_hash)
    code = canonical.verification_code(passport["passport_id"], version, doc_hash)
    signature = ctx.signer.sign(doc_hash)
    store.add_version(passport["passport_id"], version, issued_at, doc_hash, code,
                      anchor.tx_hash, anchor.network, anchor.block_number, signature, skills)
    return version_model(store.get_version(passport["passport_id"], version))


def version_model(v: dict) -> PassportVersion:
    return PassportVersion(
        version=v["version"], issuedAt=v["issued_at"],
        skills=[PassportSkill(recordId=s["record_id"], skillId=s["skill_id"],
                              skillName=s["skill_name"], skillCategory=s["skill_category"],
                              badgeCode=s["badge_code"], skillDescription=s["skill_description"],
                              dateEarned=s["date_earned"]) for s in v["skills"]],
        documentHash=v["document_hash"], verificationCode=v["verification_code"],
        txHash=v["tx_hash"], network=v["network"], blockNumber=v["block_number"])


def passport_model(store, row: dict) -> Passport:
    return Passport(
        passportId=row["passport_id"], studentId=row["student_id"],
        firstName=row["first_name"], lastName=row["last_name"], email=row["email"],
        program=row["program"], educationLevel=row["education_level"],
        studentStatus=row["student_status"], firstIssued=row["first_issued"],
        versions=[version_model(v) for v in store.get_versions(row["passport_id"])])


def passport_info(row: dict) -> PassportInfo:
    return PassportInfo(
        passportId=row["passport_id"], studentId=row["student_id"],
        firstName=row["first_name"], lastName=row["last_name"], email=row["email"],
        program=row["program"], educationLevel=row["education_level"],
        studentStatus=row["student_status"], firstIssued=row["first_issued"])


# ------------------------------------------------------------------- sync
def ingest_sheet(store, sheet: SheetSource) -> list[dict]:
    """Pull rows from the sheet: register new passports, refresh A-P.
    Students appearing in the sheet get their (single) passport identity;
    sync itself never creates passports — see contract rule."""
    rows = sheet.fetch()
    for r in rows:
        if r.get("passportId") and r.get("studentId"):
            store.register_passport(r)
        store.upsert_record(r, r.get("_sheetRow"))
    return rows


def sync(store, ctx, sheet: Optional[SheetSource] = None) -> SyncResult:
    if sheet is not None:
        ingest_sheet(store, sheet)
    result = SyncResult(processed=0, synced=0, duplicates=0, errors=0,
                        passportsUpdated=[], log=[])
    now = now_iso()
    by_passport: dict[str, list[dict]] = {}
    write_back: list[dict] = []

    def mark(r: dict, status: str, version: Optional[str], notes: Optional[str], note: str):
        store.update_record_sync(r["recordId"], status, version,
                                 sheet_timestamp(now) if status == "SYNCED" else r.get("syncedAt"),
                                 notes)
        write_back.append({"recordId": r["recordId"], "_sheetRow": r.get("sheetRow"),
                           "syncStatus": status, "syncedVersion": version,
                           "syncedAt": sheet_timestamp(now) if status == "SYNCED" else r.get("syncedAt"),
                           "syncNotes": notes})
        result.log.append(SyncLogEntry(recordId=r["recordId"], status=status, note=note))

    for r in store.pending_records():
        result.processed += 1
        passport = store.get_passport(r["passportId"]) if r["passportId"] else None
        if any(not r.get(f) for f in REQUIRED) or passport is None or passport["student_id"] != r["studentId"]:
            note = ("Unknown Passport ID" if passport is None
                    else "Student ID does not match passport" if passport["student_id"] != r["studentId"]
                    else "Missing required field")
            mark(r, "ERROR", r.get("syncedVersion"), note, note)
            result.errors += 1
            continue
        current = store.get_versions(r["passportId"])
        current_skills = current[-1]["skills"] if current else []
        queued = by_passport.get(r["passportId"], [])
        known = {(s["record_id"], s["skill_id"]) for s in current_skills}
        known |= {(q["recordId"], q["skillId"]) for q in queued}
        if any(r["recordId"] == rid or r["skillId"] == sid for rid, sid in known):
            mark(r, "DUPLICATE", r.get("syncedVersion"), "Skill already on passport — skipped",
                 "Skill already on passport — skipped")
            result.duplicates += 1
            continue
        by_passport.setdefault(r["passportId"], []).append(r)

    for passport_id, recs in by_passport.items():
        passport = store.get_passport(passport_id)
        prev = store.get_versions(passport_id)
        next_num = (prev[-1]["version"] + 1) if prev else 1
        prev_skills = [ {  # db shape -> camel dict for canonical/to_skill parity
            "recordId": s["record_id"], "skillId": s["skill_id"], "skillName": s["skill_name"],
            "skillCategory": s["skill_category"], "badgeCode": s["badge_code"],
            "skillDescription": s["skill_description"], "dateEarned": s["date_earned"]}
            for s in (prev[-1]["skills"] if prev else [])]
        issue_version(store, passport, next_num,
                      prev_skills + [to_skill(r) for r in recs], now, ctx)
        for r in recs:
            mark(r, "SYNCED", f"V{next_num}", None, f"{passport_id} → V{next_num}")
            result.synced += 1
        result.passports_updated.append({"passportId": passport_id, "newVersion": next_num})

    if sheet is not None and write_back:
        try:
            sheet.write_back(write_back)
        except Exception as e:  # sheet write-back must not lose a completed sync
            result.log.append(SyncLogEntry(recordId="-", status="ERROR",
                                           note=f"Sheet write-back failed: {e}"))
    return result


# ------------------------------------------------------------ verification
def issuer_model(ctx) -> Issuer:
    return Issuer(name=ctx.issuer_name, did=ctx.issuer_did, walletAddress=ctx.issuer_wallet)


def verify_by_code(store, code: str, ctx) -> VerifyResult:
    found = store.find_version_by_code(code.strip().upper())
    if not found:
        return VerifyResult(found=False, documentAuthentic=False,
                            issuerAuthentic=False, isLatest=False)
    passport, v = found
    skills = [{"recordId": s["record_id"], "skillId": s["skill_id"], "skillName": s["skill_name"],
               "skillCategory": s["skill_category"], "badgeCode": s["badge_code"],
               "skillDescription": s["skill_description"], "dateEarned": s["date_earned"]}
              for s in v["skills"]]
    recomputed = canonical.document_hash(
        passport["passport_id"], passport["first_name"], passport["last_name"],
        passport["first_issued"], v["version"], skills, ctx.issuer_did)
    versions = store.get_versions(passport["passport_id"])
    latest = versions[-1]["version"]
    from .issuer import IssuerSigner
    issuer_ok = IssuerSigner.verify(ctx.signer.public_key_b64(), v["issuer_signature"], v["document_hash"])
    return VerifyResult(
        found=True, documentAuthentic=recomputed == v["document_hash"],
        issuerAuthentic=issuer_ok, isLatest=v["version"] == latest, latestVersion=latest,
        issuer=issuer_model(ctx), passport=passport_info(passport),
        version=version_model(v), recomputedHash=recomputed,
        issuerSignature=v["issuer_signature"])


def verify_document(store, passport: PassportInfo, version: int,
                    skills: list[PassportSkill], ctx) -> VerifyDocumentResult:
    anchored = store.get_version(passport.passport_id, version)
    recomputed = canonical.document_hash(
        passport.passport_id, passport.first_name, passport.last_name,
        passport.first_issued, version, [s.model_dump(by_alias=True) for s in skills],
        ctx.issuer_did)
    anchored_hash = anchored["document_hash"] if anchored else None
    return VerifyDocumentResult(recomputedHash=recomputed,
                                matches=recomputed == anchored_hash,
                                anchoredHash=anchored_hash)


def summaries(store) -> list[PassportSummary]:
    out = []
    for p in store.list_passports():
        versions = store.get_versions(p["passport_id"])
        latest = versions[-1] if versions else None
        out.append(PassportSummary(
            passportId=p["passport_id"], studentId=p["student_id"],
            fullName=f"{p['first_name']} {p['last_name']}", program=p["program"],
            latestVersion=latest["version"] if latest else None,
            skillCount=len(latest["skills"]) if latest else 0,
            pendingCount=store.pending_count(p["passport_id"])))
    return out


def record_models(store) -> list[SkillRecord]:
    return [SkillRecord.model_validate(r) for r in store.list_records()]


# ---------------------------------------------------------- skill requests
def skill_catalogue(store) -> list[dict]:
    """Distinct skills BTU already awards (from the sheet), by skillId."""
    seen: dict[str, dict] = {}
    for r in store.list_records():
        seen.setdefault(r["skillId"], {
            "skillId": r["skillId"], "skillName": r["skillName"],
            "skillCategory": r["skillCategory"], "badgeCode": r["badgeCode"],
            "skillDescription": r["skillDescription"]})
    return sorted(seen.values(), key=lambda s: (s["skillCategory"], s["skillName"]))


def catalogue_item(store, skill_id: str) -> Optional[dict]:
    return next((s for s in skill_catalogue(store) if s["skillId"] == skill_id), None)


def _validate_new_request(store, passport: dict, skill_id: str) -> dict:
    item = catalogue_item(store, skill_id)
    if not item:
        raise ValueError(f"Unknown skill {skill_id}")
    versions = store.get_versions(passport["passport_id"])
    owned = {s["skill_id"] for v in versions for s in v["skills"]}
    if skill_id in owned:
        raise ValueError("Skill already on your passport")
    pending = [q for q in store.list_requests(passport["email"])
               if q["skill_id"] == skill_id and q["status"] == "PENDING"]
    if pending:
        raise ValueError("You already have a pending request for this skill")
    return item


def submit_test_request(store, passport: dict, skill_id: str,
                        answers: dict, description: str = "") -> dict:
    from .assessments import grade
    item = _validate_new_request(store, passport, skill_id)
    score, passed, _ = grade(item["skillCategory"], answers)
    if not passed:
        raise ValueError(f"Test not passed: {score}% (need 70%). You can retake it.")
    return store.create_request({
        "passport_id": passport["passport_id"], "student_id": passport["student_id"],
        "student_email": passport["email"], "skill_id": item["skillId"],
        "skill_name": item["skillName"], "skill_category": item["skillCategory"],
        "badge_code": item["badgeCode"], "method": "TEST", "test_score": score,
        "description": description, "status": "PENDING", "created_at": now_iso()})


def submit_proof_request(store, passport: dict, skill_id: str, description: str,
                         evidence_name: str = "", evidence_hash: str = "",
                         evidence_url: str = "") -> dict:
    item = _validate_new_request(store, passport, skill_id)
    if not (evidence_name or evidence_url):
        raise ValueError("Upload a proof file or provide an evidence URL")
    return store.create_request({
        "passport_id": passport["passport_id"], "student_id": passport["student_id"],
        "student_email": passport["email"], "skill_id": item["skillId"],
        "skill_name": item["skillName"], "skill_category": item["skillCategory"],
        "badge_code": item["badgeCode"], "method": "PROOF", "test_score": None,
        "evidence_name": evidence_name, "evidence_hash": evidence_hash,
        "evidence_url": evidence_url, "description": description,
        "status": "PENDING", "created_at": now_iso()})


def next_record_id(store) -> str:
    nums = []
    for r in store.list_records():
        rid = r["recordId"]
        if rid.startswith("REC-") and rid[4:].isdigit():
            nums.append(int(rid[4:]))
    return f"REC-{(max(nums) + 1) if nums else 1:04d}"


def approve_request(store, request_id: int, note: str = "",
                    sheet: Optional[SheetSource] = None) -> dict:
    """Approval writes a NOT SYNCED row into the sheet dataset (and the
    real sheet when a live source is configured). The existing Sync then
    turns it into a new anchored passport version — same pipeline as
    admin-entered skills, nothing bypasses the sheet."""
    req = store.get_request(request_id)
    if not req:
        raise ValueError("Request not found")
    if req["status"] != "PENDING":
        raise ValueError(f"Request already {req['status'].lower()}")
    passport = store.get_passport(req["passport_id"])
    item = catalogue_item(store, req["skill_id"]) or {}
    record = {
        "studentId": passport["student_id"], "firstName": passport["first_name"],
        "lastName": passport["last_name"], "email": passport["email"],
        "program": passport["program"], "educationLevel": passport["education_level"],
        "passportId": passport["passport_id"], "firstIssued": passport["first_issued"],
        "studentStatus": passport["student_status"], "recordId": next_record_id(store),
        "skillId": req["skill_id"], "skillName": req["skill_name"],
        "skillCategory": req["skill_category"], "badgeCode": req["badge_code"],
        "skillDescription": item.get("skillDescription", ""),
        "dateEarned": now_iso()[:10], "syncStatus": "NOT SYNCED",
        "syncedVersion": None, "syncedAt": None, "syncNotes": None}
    store.upsert_record(record)
    if sheet is not None:
        try:
            sheet.append_record(record)
        except Exception:
            pass  # DB mirror already holds the row; sheet append is best-effort
    return store.decide_request(request_id, "APPROVED", note, now_iso(), record["recordId"])


def reject_request(store, request_id: int, note: str = "") -> dict:
    req = store.get_request(request_id)
    if not req:
        raise ValueError("Request not found")
    if req["status"] != "PENDING":
        raise ValueError(f"Request already {req['status'].lower()}")
    return store.decide_request(request_id, "REJECTED", note, now_iso())


def request_out(store, r: dict):
    from .models import SkillRequestOut
    sync_status = None
    if r.get("record_id"):
        rec = next((x for x in store.list_records() if x["recordId"] == r["record_id"]), None)
        sync_status = rec["syncStatus"] if rec else None
    return SkillRequestOut.model_validate({**r, "record_sync_status": sync_status})
