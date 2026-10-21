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
def _json_list(raw) -> list:
    import json as _json
    if isinstance(raw, list):
        return raw
    try:
        v = _json.loads(raw or "[]")
        return v if isinstance(v, list) else []
    except Exception:
        return []


def issue_version(store, passport: dict, version: int, skills: list[dict],
                  issued_at: str, ctx, status: str = "ACTIVE", superseded_reason: str = "",
                  revoked_record_ids: list[str] | None = None,
                  signer_roles: list[str] | None = None) -> PassportVersion:
    """Hash canonical content -> sign as BTU -> anchor on-chain -> persist.
    Canonical payload is unchanged (golden-hash parity); status/revocation/
    signer metadata is stored alongside, never inside the hashed payload."""
    import json as _json
    doc_hash = canonical.document_hash(
        passport["passport_id"], passport["first_name"], passport["last_name"],
        passport["first_issued"], version, skills, ctx.issuer_did)
    anchor = ctx.anchor.anchor(doc_hash)
    code = canonical.verification_code(passport["passport_id"], version, doc_hash)
    signature = ctx.signer.sign(doc_hash)
    store.add_version(passport["passport_id"], version, issued_at, doc_hash, code,
                      anchor.tx_hash, anchor.network, anchor.block_number, signature, skills,
                      status=status, superseded_reason=superseded_reason,
                      revoked_record_ids=_json.dumps(revoked_record_ids or []),
                      signer_roles=_json.dumps(signer_roles or ["Admin"]))
    return version_model(store.get_version(passport["passport_id"], version))


def version_model(v: dict) -> PassportVersion:
    return PassportVersion(
        version=v["version"], issuedAt=v["issued_at"],
        skills=[PassportSkill(recordId=s["record_id"], skillId=s["skill_id"],
                              skillName=s["skill_name"], skillCategory=s["skill_category"],
                              badgeCode=s["badge_code"], skillDescription=s["skill_description"],
                              dateEarned=s["date_earned"]) for s in v["skills"]],
        documentHash=v["document_hash"], verificationCode=v["verification_code"],
        txHash=v["tx_hash"], network=v["network"], blockNumber=v["block_number"],
        status=v.get("status") or "ACTIVE", supersededReason=v.get("superseded_reason") or "",
        revokedRecordIds=_json_list(v.get("revoked_record_ids")),
        ipfsCid=v.get("ipfs_cid") or "", signerRoles=_json_list(v.get("signer_roles")))


def passport_model(store, row: dict) -> Passport:
    versions = [version_model(v) for v in store.get_versions(row["passport_id"])]
    for vm in versions[:-1]:  # derived, so issued versions stay immutable
        if vm.status == "ACTIVE":
            vm.status = "SUPERSEDED"
    return Passport(
        passportId=row["passport_id"], studentId=row["student_id"],
        firstName=row["first_name"], lastName=row["last_name"], email=row["email"],
        program=row["program"], educationLevel=row["education_level"],
        studentStatus=row["student_status"], firstIssued=row["first_issued"],
        publicSlug=row.get("public_slug") or "",
        versions=versions)


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

    # --- anomaly preflight: hold suspicious batches out of issuance ---
    threshold = getattr(ctx.settings, "anomaly_batch_threshold", 5) if ctx and ctx.settings else 5
    for passport_id in list(by_passport):
        recs = by_passport[passport_id]
        reasons: dict[str, str] = {}
        if len(recs) > threshold:
            for r in recs:
                if not store.flag_for(r["recordId"], "RELEASED"):
                    reasons[r["recordId"]] = (f"{len(recs)} skills for one student in one sync "
                                              f"batch (threshold {threshold})")
        for r in recs:
            req = next((q for q in store.list_requests()
                        if q.get("record_id") == r["recordId"] and q["status"] == "REJECTED"), None)
            if req and not store.flag_for(r["recordId"], "RELEASED"):
                reasons[r["recordId"]] = "Record matches a REJECTED skill request"
        if reasons:
            kept = []
            for r in recs:
                if r["recordId"] in reasons:
                    store.add_flag(r["recordId"], passport_id, reasons[r["recordId"]], now)
                    result.flagged += 1
                    result.log.append(SyncLogEntry(recordId=r["recordId"], status="NEEDS_REVIEW",
                                                   note=reasons[r["recordId"]]))
                else:
                    kept.append(r)
            if kept:
                by_passport[passport_id] = kept
            else:
                del by_passport[passport_id]

    for passport_id, recs in by_passport.items():
        passport = store.get_passport(passport_id)
        prev = store.get_versions(passport_id)
        next_num = (prev[-1]["version"] + 1) if prev else 1
        prev_skills = [ {  # db shape -> camel dict for canonical/to_skill parity
            "recordId": s["record_id"], "skillId": s["skill_id"], "skillName": s["skill_name"],
            "skillCategory": s["skill_category"], "badgeCode": s["badge_code"],
            "skillDescription": s["skill_description"], "dateEarned": s["date_earned"]}
            for s in (prev[-1]["skills"] if prev else [])]
        roles = ["Admin"]
        for r in recs:
            q = next((x for x in store.list_requests() if x.get("record_id") == r["recordId"]), None)
            if q:
                if q.get("instructor_approval") and "Instructor" not in roles:
                    roles.append("Instructor")
                if q.get("career_center_approval") and "CareerCenter" not in roles:
                    roles.append("CareerCenter")
        issue_version(store, passport, next_num,
                      prev_skills + [to_skill(r) for r in recs], now, ctx, signer_roles=roles)
        for r in recs:
            mark(r, "SYNCED", f"V{next_num}", None, f"{passport_id} → V{next_num}")
            result.synced += 1
        result.passports_updated.append({"passportId": passport_id, "newVersion": next_num})
        if passport.get("email"):
            store.add_notification(passport["email"],
                                   f"Your AI Skills Digital Passport {passport_id} was updated to V{next_num}.", now)
            try:
                from .mailer import send_email
                send_email(ctx.settings, passport["email"],
                           "Your BTU AI Skills Passport was updated",
                           f"Your AI Skills Digital Passport {passport_id} is now at version V{next_num}.")
            except Exception:
                pass

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
    latest_v = versions[-1]
    reason = None
    if v["version"] != latest:
        revoked_here = set(_json_list(latest_v.get("revoked_record_ids")))
        mine = {s["record_id"] for s in v["skills"]}
        if latest_v.get("status") == "REVOKED_CONTENT" and revoked_here & mine:
            names = [s["skill_name"] for s in v["skills"] if s["record_id"] in revoked_here]
            reason = (f"outdated because a skill was later revoked: {', '.join(names)}"
                      + (f" ({latest_v.get('superseded_reason')})" if latest_v.get("superseded_reason") else ""))
        else:
            reason = f"Superseded by V{latest}"
    return VerifyResult(
        found=True, documentAuthentic=recomputed == v["document_hash"],
        issuerAuthentic=issuer_ok, isLatest=v["version"] == latest, latestVersion=latest,
        issuer=issuer_model(ctx), passport=passport_info(passport),
        version=version_model(v), recomputedHash=recomputed,
        issuerSignature=v["issuer_signature"],
        versionStatus=latest_v.get("status") if v["version"] == latest else v.get("status"),
        supersededReason=reason)


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
               if q["skill_id"] == skill_id and q["status"] in PENDING_STATUSES]
    if pending:
        raise ValueError("You already have a pending request for this skill")
    return item


PENDING_STATUSES = ("SUBMITTED", "AI_REVIEWED", "NEEDS_TEST", "PENDING_ADMIN", "PENDING")


def _ai_review(item: dict, reasoning: str, proof_links: list[str], method: str,
               test_score: int | None = None) -> dict:
    from .ai import StubReviewer
    return StubReviewer().review(item, reasoning, proof_links, method, test_score)


def submit_test_request(store, passport: dict, skill_id: str,
                        answers: dict, description: str = "") -> dict:
    from .assessments import grade
    import json as _json
    item = _validate_new_request(store, passport, skill_id)
    score, passed, _ = grade(item["skillCategory"], answers)
    if not passed:
        raise ValueError(f"Test not passed: {score}% (need 70%). You can retake it.")
    ai = _ai_review(item, description, [], "TEST", score)
    return store.create_request({
        "passport_id": passport["passport_id"], "student_id": passport["student_id"],
        "student_email": passport["email"], "skill_id": item["skillId"],
        "skill_name": item["skillName"], "skill_category": item["skillCategory"],
        "badge_code": item["badgeCode"], "method": "TEST", "test_score": score,
        "description": description, "status": "PENDING_ADMIN", "created_at": now_iso(),
        "ai_summary": ai["summary"], "ai_score": ai["score"], "ai_model": ai["model"],
        "proof_links": _json.dumps([])})


def submit_proof_request(store, passport: dict, skill_id: str, description: str,
                         evidence_name: str = "", evidence_hash: str = "",
                         evidence_url: str = "") -> dict:
    import json as _json
    item = _validate_new_request(store, passport, skill_id)
    if not (evidence_name or evidence_url):
        raise ValueError("Upload a proof file or provide an evidence URL")
    links = [evidence_url] if evidence_url else []
    ai = _ai_review(item, description, links, "PROOF")
    status = "NEEDS_TEST" if item["skillCategory"] == "AI Advanced Skill" else "PENDING_ADMIN"
    return store.create_request({
        "passport_id": passport["passport_id"], "student_id": passport["student_id"],
        "student_email": passport["email"], "skill_id": item["skillId"],
        "skill_name": item["skillName"], "skill_category": item["skillCategory"],
        "badge_code": item["badgeCode"], "method": "PROOF", "test_score": None,
        "evidence_name": evidence_name, "evidence_hash": evidence_hash,
        "evidence_url": evidence_url, "description": description,
        "status": status, "created_at": now_iso(),
        "ai_summary": ai["summary"], "ai_score": ai["score"], "ai_model": ai["model"],
        "proof_links": _json.dumps(links)})


def complete_request_test(store, request_id: int, email: str, answers: dict) -> dict:
    from .assessments import grade
    req = store.get_request(request_id)
    if not req or req["student_email"].lower() != email.lower():
        raise ValueError("Request not found")
    if req["status"] != "NEEDS_TEST":
        raise ValueError(f"Request is {req['status'].lower()}, not waiting for a test")
    score, passed, _ = grade(req["skill_category"], answers)
    if not passed:
        raise ValueError(f"Test not passed: {score}% (need 70%). You can retake it.")
    ai = _ai_review(catalogue_item(store, req["skill_id"]) or {}, req["description"] or "",
                    _json_list(req.get("proof_links")), "PROOF", score)
    return store.update_request(request_id, test_score=score, status="PENDING_ADMIN",
                                ai_summary=ai["summary"], ai_score=ai["score"], ai_model=ai["model"])


def attest_request(store, request_id: int, role: str, approver: str = "") -> dict:
    from .registry import ATTEST_ROLES
    req = store.get_request(request_id)
    if not req:
        raise ValueError("Request not found")
    if req["status"] not in PENDING_STATUSES:
        raise ValueError(f"Request already {req['status'].lower()}")
    if role not in ATTEST_ROLES:
        raise ValueError("Role must be Instructor or CareerCenter")
    return store.attest_request(request_id, ATTEST_ROLES[role], approver or role)


def _notify_student(store, ctx, email: str, subject: str, body: str) -> None:
    if not email:
        return
    store.add_notification(email, body, now_iso())
    if ctx is not None:
        try:
            from .mailer import send_email
            send_email(ctx.settings, email, subject, body)
        except Exception:
            pass


def next_record_id(store) -> str:
    nums = []
    for r in store.list_records():
        rid = r["recordId"]
        if rid.startswith("REC-") and rid[4:].isdigit():
            nums.append(int(rid[4:]))
    return f"REC-{(max(nums) + 1) if nums else 1:04d}"


def approve_request(store, request_id: int, note: str = "",
                    sheet: Optional[SheetSource] = None, reviewer: str = "",
                    ctx=None) -> dict:
    """Approval writes a NOT SYNCED row into the sheet dataset (and the
    real sheet when a live source is configured). The existing Sync then
    turns it into a new anchored passport version — same pipeline as
    admin-entered skills, nothing bypasses the sheet."""
    req = store.get_request(request_id)
    if not req:
        raise ValueError("Request not found")
    if req["status"] not in ("PENDING", "PENDING_ADMIN"):
        raise ValueError(f"Request already {req['status'].lower()}" if req["status"] != "NEEDS_TEST"
                         else "Request still needs a passing test before approval")
    if req["skill_category"] == "AI Advanced Skill" and not (
            req.get("instructor_approval") and req.get("career_center_approval")):
        raise ValueError("AI Advanced Skill requires Instructor + Career Center attestation before approval")
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
        mirror = getattr(sheet, "mirror_request", None)
        if mirror:
            try:
                mirror({**req, "status": "APPROVED", "record_id": record["recordId"]})
            except Exception:
                pass
    out = store.decide_request(request_id, "APPROVED", note, now_iso(), record["recordId"], reviewer)
    _notify_student(store, ctx, req["student_email"], "Skill request approved",
                    f"Your request for {req['skill_name']} was approved. It will appear on your "
                    f"passport at the next sync.")
    return out


def reject_request(store, request_id: int, note: str = "", reviewer: str = "", ctx=None) -> dict:
    req = store.get_request(request_id)
    if not req:
        raise ValueError("Request not found")
    if req["status"] not in PENDING_STATUSES:
        raise ValueError(f"Request already {req['status'].lower()}")
    out = store.decide_request(request_id, "REJECTED", note, now_iso(), "", reviewer)
    _notify_student(store, ctx, req["student_email"], "Skill request rejected",
                    f"Your request for {req['skill_name']} was rejected. {note}".strip())
    return out


# ------------------------------------------------------------ revocation
def revoke_skill(store, passport_id: str, record_id: str, reason: str, ctx,
                 sheet: Optional[SheetSource] = None) -> PassportVersion:
    passport = store.get_passport(passport_id)
    if not passport:
        raise ValueError("Passport not found")
    versions = store.get_versions(passport_id)
    if not versions:
        raise ValueError("Passport has no issued versions")
    latest = versions[-1]
    target = next((s for s in latest["skills"] if s["record_id"] == record_id), None)
    if not target:
        raise ValueError("Skill is not on the latest passport version")
    kept = [{"recordId": s["record_id"], "skillId": s["skill_id"], "skillName": s["skill_name"],
             "skillCategory": s["skill_category"], "badgeCode": s["badge_code"],
             "skillDescription": s["skill_description"], "dateEarned": s["date_earned"]}
            for s in latest["skills"] if s["record_id"] != record_id]
    next_num = latest["version"] + 1
    version = issue_version(store, passport, next_num, kept, now_iso(), ctx,
                            status="REVOKED_CONTENT",
                            superseded_reason=reason or "Skill revoked by BTU",
                            revoked_record_ids=[record_id], signer_roles=["Admin"])
    store.update_record_sync(record_id, "SYNCED", f"V{next_num}", sheet_timestamp(now_iso()),
                             f"REVOKED: {reason or 'revoked by BTU'}")
    if sheet is not None:
        try:
            sheet.write_back([{"recordId": record_id, "_sheetRow": None, "syncStatus": "SYNCED",
                               "syncedVersion": f"V{next_num}", "syncedAt": sheet_timestamp(now_iso()),
                               "syncNotes": f"REVOKED: {reason or 'revoked by BTU'}"}])
        except Exception:
            pass
    _notify_student(store, ctx, passport.get("email", ""), "A skill was revoked",
                    f"The skill {target['skill_name']} was removed from your passport "
                    f"{passport_id} (now V{next_num}). Reason: {reason or 'revoked by BTU'}")
    return version


# ------------------------------------------- credentials / badges / DID
def did_document(ctx) -> dict:
    from .registry import issuer_registry
    return {
        "@context": ["https://www.w3.org/ns/did/v1", "https://w3id.org/security/suites/ed25519-2020/v1"],
        "id": ctx.issuer_did,
        "verificationMethod": [{
            "id": f"{ctx.issuer_did}#key-1", "type": "Ed25519VerificationKey2020",
            "controller": ctx.issuer_did, "publicKeyBase64": ctx.signer.public_key_b64()}],
        "assertionMethod": [f"{ctx.issuer_did}#key-1"],
        "service": [{"id": f"{ctx.issuer_did}#issuer-registry", "type": "IssuerRegistry",
                     "serviceEndpoint": "/issuer/registry"}],
        "roles": [r["role"] for r in issuer_registry(ctx)],
    }


def build_credential(store, passport: dict, v: dict, ctx) -> dict:
    vm = version_model(v)
    return {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "type": ["VerifiableCredential", "BTUAISkillsPassport"],
        "issuer": ctx.issuer_did,
        "issuanceDate": v["issued_at"],
        "credentialSubject": {
            "studentId": passport["student_id"], "passportId": passport["passport_id"],
            "skills": [{"skillId": s.skill_id, "skillName": s.skill_name,
                        "skillCategory": s.skill_category, "badgeCode": s.badge_code,
                        "dateEarned": s.date_earned} for s in vm.skills]},
        "proof": {"type": "Ed25519Signature2020", "verificationMethod": f"{ctx.issuer_did}#key-1",
                  "proofPurpose": "assertionMethod", "proofValue": v["issuer_signature"],
                  "documentHash": v["document_hash"], "verificationCode": v["verification_code"]},
    }


def build_badges(store, passport: dict, v: dict, ctx, base_url: str = "") -> list[dict]:
    out = []
    for s in version_model(v).skills:
        verify_url = f"{base_url}/verify?code={v['verification_code']}"
        out.append({
            "@context": ["https://www.w3.org/2018/credentials/v1",
                         "https://purl.imsglobal.org/spec/ob/v3p0/context-3.0.3.json"],
            "type": ["VerifiableCredential", "OpenBadgeCredential"],
            "issuer": {"id": ctx.issuer_did, "type": "Profile", "name": ctx.issuer_name},
            "issuanceDate": v["issued_at"],
            "credentialSubject": {"studentId": passport["student_id"],
                                  "achievement": {"id": s.badge_code, "type": "Achievement",
                                                  "name": s.skill_name, "description": s.skill_description,
                                                  "criteria": {"narrative": s.skill_category}}},
            "evidence": [{"id": verify_url, "type": "Evidence", "name": "BTU verification"}],
            "proof": {"type": "Ed25519Signature2020", "verificationMethod": f"{ctx.issuer_did}#key-1",
                      "proofValue": v["issuer_signature"], "documentHash": v["document_hash"]},
        })
    return out


def skill_gap(store, passport: dict, job_description: str) -> dict:
    from .ai import StubSkillExtractor
    catalogue = skill_catalogue(store)
    required = StubSkillExtractor().extract(job_description, catalogue)
    versions = store.get_versions(passport["passport_id"])
    owned = {s["skill_id"] for s in (versions[-1]["skills"] if versions else [])}
    matched = [i for i in required if i["skillId"] in owned]
    missing = [i for i in required if i["skillId"] not in owned]
    return {"matched": matched, "missing": missing,
            "suggestions": [{"skill": m, "learnVia": m.get("skillDescription", "")} for m in missing],
            "model": "stub-extractor-v1"}


def find_passport_for_student(store, email: str, student_id: str = "") -> Optional[dict]:
    return (store.get_passport_by_email(email)
            or (store.get_passport_by_student_id(student_id) if student_id else None))


def generate_passport_version(store, passport: dict, ctx,
                              sheet: Optional[SheetSource] = None) -> bool:
    """Issue a version from sheet records not yet on the passport.
    Used when a student requests a passport that BTU data already
    covers but that was never issued. Returns True if a version exists
    or was created."""
    versions = store.get_versions(passport["passport_id"])
    if versions:
        return True
    candidates, seen = [], set()
    for r in store.list_records():
        if r["passportId"] != passport["passport_id"]:
            continue
        if any(not r.get(f) for f in REQUIRED) or r["studentId"] != passport["student_id"]:
            continue
        if r["recordId"] in seen or r["skillId"] in {c["skillId"] for c in candidates}:
            continue
        seen.add(r["recordId"])
        candidates.append(r)
    if not candidates:
        return False
    now = now_iso()
    version = issue_version(store, passport, 1, [to_skill(r) for r in candidates], now, ctx)
    write_back = []
    for r in candidates:
        store.update_record_sync(r["recordId"], "SYNCED", "V1", sheet_timestamp(now), None)
        write_back.append({"recordId": r["recordId"], "_sheetRow": r.get("sheetRow"),
                           "syncStatus": "SYNCED", "syncedVersion": "V1",
                           "syncedAt": sheet_timestamp(now), "syncNotes": None})
    if sheet is not None:
        try:
            sheet.write_back(write_back)
        except Exception:
            pass
    return True


def submit_passport_request(store, email: str, student_id: str, first_name: str,
                            last_name: str, ctx, sheet: Optional[SheetSource] = None) -> dict:
    """Check the database first: passport ready (or generatable) ->
    READY immediately; no data at all -> PENDING_STAFF for BTU staff."""
    passport = find_passport_for_student(store, email, student_id)
    if passport and generate_passport_version(store, passport, ctx, sheet):
        req = store.create_passport_request({
            "email": email, "student_id": student_id or passport["student_id"],
            "first_name": first_name, "last_name": last_name, "status": "READY",
            "passport_id": passport["passport_id"], "note": "Passport found and ready",
            "created_at": now_iso(), "decided_at": now_iso()})
        return req
    pending = store.latest_passport_request(email)
    if pending and pending["status"] == "PENDING_STAFF":
        return pending
    return store.create_passport_request({
        "email": email, "student_id": student_id, "first_name": first_name,
        "last_name": last_name, "status": "PENDING_STAFF", "passport_id": "",
        "note": "", "created_at": now_iso(), "decided_at": ""})


def fulfil_passport_request(store, request_id: int, note: str, ctx,
                            sheet: Optional[SheetSource] = None) -> dict:
    req = store.get_passport_request(request_id)
    if not req:
        raise ValueError("Request not found")
    if req["status"] != "PENDING_STAFF":
        raise ValueError(f"Request already {req['status'].lower()}")
    passport = find_passport_for_student(store, req["email"], req["student_id"])
    if not passport or not generate_passport_version(store, passport, ctx, sheet):
        raise ValueError("No student data in the sheet yet — add/verify the student's "
                         "records first, then approve again")
    store.add_notification(req["email"],
                           f"Your AI Skills Digital Passport {passport['passport_id']} is ready.",
                           now_iso())
    from .mailer import send_email
    send_email(ctx.settings, req["email"], "Your BTU AI Skills Passport is ready",
               f"Your AI Skills Digital Passport {passport['passport_id']} is ready. "
               "Sign in to view and download it.")
    return store.decide_passport_request(request_id, "READY", note, now_iso(),
                                         passport["passport_id"])


def reject_passport_request(store, request_id: int, note: str = "") -> dict:
    req = store.get_passport_request(request_id)
    if not req:
        raise ValueError("Request not found")
    if req["status"] != "PENDING_STAFF":
        raise ValueError(f"Request already {req['status'].lower()}")
    store.add_notification(req["email"],
                           "Your passport request was declined. "
                           + (note or "Please contact BTU staff."), now_iso())
    return store.decide_passport_request(request_id, "REJECTED", note, now_iso())


def request_out(store, r: dict):
    from .models import SkillRequestOut
    sync_status = None
    if r.get("record_id"):
        rec = next((x for x in store.list_records() if x["recordId"] == r["record_id"]), None)
        sync_status = rec["syncStatus"] if rec else None
    status = "PENDING_ADMIN" if r.get("status") == "PENDING" else r.get("status")
    return SkillRequestOut.model_validate({
        **r, "status": status, "record_sync_status": sync_status,
        "reasoning": r.get("description", ""),
        "proof_links": _json_list(r.get("proof_links")) or ([r["evidence_url"]] if r.get("evidence_url") else []),
        "instructor_approval": bool(r.get("instructor_approval")),
        "career_center_approval": bool(r.get("career_center_approval"))})
