"""BTU AI Skills Digital Passport — backend API.

Implements frontend/API_CONTRACT.md 1:1. Run:
    uvicorn app.main:app --app-dir backend --port 8000   (or: python -m app)
Interactive docs at /docs.
"""
from __future__ import annotations

import re
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import services
from .anchor import make_anchor
from .config import settings
from .issuer import IssuerSigner
from .models import (AttestRequest, BulkVerifyRequest, CompleteTestRequest, DecisionRequest,
                     ExplainRequest, IssuerPublic, LoginResponse, NotificationOut, Passport,
                     PassportRequestCreate, PassportRequestOut, PassportSummary, RequestCodeRequest,
                     RequestCodeResponse, ReviewFlagOut, RevokeRequest, SkillCatalogItem, SkillGapRequest,
                     SkillRecord, SkillRequestOut, SkillTest,
                     SyncResult, TestQuestion, TestRequestSubmit, VerifyCodeRequest,
                     VerifyDocumentRequest, VerifyDocumentResult, VerifyResult)
from .security import Auth, make_token
from .sheets import make_sheet_source
from .store import Store, load_seed

store = Store(settings.database_path, settings.database_url)
ctx = services.AppContext(settings, IssuerSigner(settings.issuer_key_file),
                          make_anchor(settings.anchor_mode, settings.network,
                                      settings.web3_rpc_url, settings.web3_private_key))
auth = Auth(settings)


def seed_if_empty() -> None:
    if not store.list_passports():
        services.seed(store, load_seed(settings.seed_file), ctx)


@asynccontextmanager
async def lifespan(_: FastAPI):
    seed_if_empty()
    yield


app = FastAPI(title="BTU AI Skills Digital Passport API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok", "passports": len(store.list_passports()),
            "database": store.kind,
            "sheetSource": settings.sheet_source, "anchorMode": settings.anchor_mode,
            "network": settings.network}


@app.get("/")
def root():
    return {"service": "BTU AI Skills Digital Passport API", "docs": "/docs",
            "issuer": services.issuer_model(ctx).model_dump(by_alias=True)}


@app.get("/issuer", response_model=IssuerPublic)
def issuer():
    i = services.issuer_model(ctx)
    return IssuerPublic(**i.model_dump(), publicKey=ctx.signer.public_key_b64())


@app.get("/issuer/registry")
def issuer_registry():
    from .registry import issuer_registry as _registry
    return _registry(ctx)


@app.get("/.well-known/did.json")
def did_document():
    return services.did_document(ctx)


@app.get("/issuer/did")
def did_document_alias():
    return services.did_document(ctx)


# ------------------------------------------------------------- passports
@app.get("/passports", response_model=list[PassportSummary], dependencies=[Depends(auth.require_admin)])
def list_passports():
    return services.summaries(store)


@app.get("/passports/{passport_id}", response_model=Passport)
def get_passport(passport_id: str):
    row = store.get_passport(passport_id)
    if not row:
        raise HTTPException(404, f"Passport {passport_id} not found")
    return services.passport_model(store, row)


@app.get("/me/passport", response_model=Passport)
def my_passport(email: str = Depends(auth.student_email)):
    row = store.get_passport_by_email(email)
    if not row:
        raise HTTPException(404, "No passport is linked to this BTU email")
    return services.passport_model(store, row)


def _code_hash(email: str, code: str) -> str:
    from .canonical import sha256_hex
    return sha256_hex(f"{email.lower()}:{code}:{settings.app_secret}")


@app.post("/auth/request-code", response_model=RequestCodeResponse)
def request_code(body: RequestCodeRequest):
    """Step 1 of sign-in: email a 6-digit verification code. The account
    must prove control of the email before any passport access/request."""
    import secrets
    from datetime import datetime, timedelta, timezone
    from .mailer import delivery_mode, send_email
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Enter a valid email address")
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.verification_ttl_minutes)
    store.save_code(email, _code_hash(email, code),
                    expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    mode = delivery_mode(settings)
    if mode == "smtp":
        send_email(settings, email, "BTU AI Skills Passport — verification code",
                   f"Your verification code is {code}. "
                   f"It expires in {settings.verification_ttl_minutes} minutes.")
        return RequestCodeResponse(sent=True, delivery=mode,
                                   expiresInMinutes=settings.verification_ttl_minutes)
    if settings.allow_dev_verification_codes:
        print(f"[dev-mail] verification code for {email}: {code}")
        return RequestCodeResponse(sent=True, delivery="dev",
                                   expiresInMinutes=settings.verification_ttl_minutes,
                                   devCode=code)
    raise HTTPException(503, "Email delivery is not configured on this server. "
                             "Set SMTP_HOST/SMTP_USER/SMTP_PASSWORD/SMTP_FROM and restart the API.")


@app.post("/auth/verify-code", response_model=LoginResponse)
def verify_code(body: VerifyCodeRequest):
    """Step 2: exchange the code for a *verified* session token."""
    import hmac as _hmac
    from datetime import datetime, timezone
    email = body.email.strip().lower()
    row = store.get_code(email)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not row or row["expires_at"] < now or row["attempts"] >= 5:
        raise HTTPException(400, "Code expired or too many attempts — request a new code")
    if not _hmac.compare_digest(row["code_hash"], _code_hash(email, body.code.strip())):
        store.bump_code_attempts(email)
        raise HTTPException(400, "Incorrect verification code")
    store.delete_code(email)
    return LoginResponse(email=email, token=make_token(
        email, settings.app_secret, settings.token_ttl_hours, verified=True))


# --------------------------------------------------------- passport requests
@app.post("/passport-requests", response_model=PassportRequestOut, status_code=201)
def request_passport(body: PassportRequestCreate, email: str = Depends(auth.student_email)):
    sheet = make_sheet_source(settings) if settings.sheet_source != "seed" else None
    req = services.submit_passport_request(store, email, body.student_id.strip(),
                                           body.first_name.strip(), body.last_name.strip(),
                                           ctx, sheet)
    return PassportRequestOut.model_validate(req)


@app.get("/me/passport-request", response_model=PassportRequestOut | None)
def my_passport_request(email: str = Depends(auth.student_email)):
    req = store.latest_passport_request(email)
    return PassportRequestOut.model_validate(req) if req else None


@app.get("/me/notifications", response_model=list[NotificationOut])
def my_notifications(email: str = Depends(auth.student_email)):
    return store.list_notifications(email)


@app.get("/admin/passport-requests", response_model=list[PassportRequestOut],
         dependencies=[Depends(auth.require_admin)])
def admin_passport_requests():
    return store.list_passport_requests()


@app.post("/admin/passport-requests/{request_id}/approve", response_model=PassportRequestOut,
          dependencies=[Depends(auth.require_admin)])
def approve_passport_request(request_id: int, body: DecisionRequest):
    try:
        sheet = make_sheet_source(settings) if settings.sheet_source != "seed" else None
        req = services.fulfil_passport_request(store, request_id, body.note, ctx, sheet)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return PassportRequestOut.model_validate(req)


@app.post("/admin/passport-requests/{request_id}/reject", response_model=PassportRequestOut,
          dependencies=[Depends(auth.require_admin)])
def reject_passport_request_ep(request_id: int, body: DecisionRequest):
    try:
        req = services.reject_passport_request(store, request_id, body.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return PassportRequestOut.model_validate(req)


# ---------------------------------------------------------------- records
@app.get("/records", response_model=list[SkillRecord], dependencies=[Depends(auth.require_admin)])
def list_records():
    return services.record_models(store)


@app.post("/admin/records/upload", dependencies=[Depends(auth.require_admin)])
async def upload_excel(file: UploadFile = File(...), sync: str = Form("true")):
    """Upload a .xlsx workbook (same layout as the BTU test data: human
    headers on row 4, columns A-T, or camelCase headers on any of the
    first 10 rows). Rows are ingested like a sheet pull, then synced."""
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(400, "Only .xlsx files are supported")
    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 10 MB)")
    if not raw:
        raise HTTPException(400, "Empty file")
    try:
        result = services.import_excel(store, ctx, raw,
                                       do_sync=str(sync).lower() in {"1", "true", "yes", "on"})
    except Exception as e:
        raise HTTPException(400, f"Could not parse Excel file: {e}")
    # keep an audit copy of every import
    try:
        from datetime import datetime, timezone
        dest = settings.upload_dir / "excel-imports"
        dest.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename)
        (dest / f"{stamp}-{safe}").write_bytes(raw)
    except Exception:
        pass
    return result


@app.post("/sync", response_model=SyncResult, dependencies=[Depends(auth.require_admin)])
def sync():
    """Pull the sheet (Google / XLSX / seed), validate, append new
    versions, anchor them, write Q-T back to the sheet."""
    # All sources are (re-)read live; ingest never overwrites Q-T, so
    # re-reading the seed/Google Sheet can't undo a previous sync.
    return services.sync(store, ctx, make_sheet_source(settings))


@app.post("/admin/reset", dependencies=[Depends(auth.require_admin)])
def reset():
    if not settings.allow_reset:
        raise HTTPException(403, "Reset disabled (ALLOW_RESET=false)")
    store.reset()
    services.seed(store, load_seed(settings.seed_file), ctx)
    return {"reset": True, "passports": len(store.list_passports())}


# ---------------------------------------------------------- skill requests
@app.get("/skills/catalogue", response_model=list[SkillCatalogItem])
def skill_catalogue():
    return services.skill_catalogue(store)


@app.get("/skills/{skill_id}/test", response_model=SkillTest)
def skill_test(skill_id: str):
    from .assessments import PASS_MARK, QUIZZES
    item = services.catalogue_item(store, skill_id)
    if not item:
        raise HTTPException(404, f"Unknown skill {skill_id}")
    return SkillTest(
        skillId=item["skillId"], skillName=item["skillName"],
        skillCategory=item["skillCategory"], passMark=PASS_MARK,
        questions=[TestQuestion(id=q["id"], question=q["question"], options=q["options"])
                   for q in QUIZZES[item["skillCategory"]]])


def _student_passport(email: str) -> dict:
    row = store.get_passport_by_email(email)
    if not row:
        raise HTTPException(404, "No passport is linked to this BTU email")
    return row


@app.post("/skill-requests/test", response_model=SkillRequestOut, status_code=201)
def submit_test(body: TestRequestSubmit, email: str = Depends(auth.student_email)):
    try:
        req = services.submit_test_request(store, _student_passport(email),
                                           body.skill_id, body.answers, body.description)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return services.request_out(store, req)


@app.post("/skill-requests/proof", response_model=SkillRequestOut, status_code=201)
async def submit_proof(skillId: str = Form(...), description: str = Form(""),
                       evidenceUrl: str = Form(""),
                       file: UploadFile | None = File(default=None),
                       email: str = Depends(auth.student_email)):
    passport = _student_passport(email)
    evidence_name, evidence_hash = "", ""
    if file is not None and file.filename:
        raw = await file.read()
        if len(raw) > 10 * 1024 * 1024:
            raise HTTPException(400, "Proof file too large (max 10 MB)")
        from .canonical import sha256_hex
        evidence_hash = sha256_hex(raw)
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename)
        (settings.upload_dir / f"{passport['passport_id']}-{skillId}-{safe}").write_bytes(raw)
        evidence_name = file.filename
    try:
        req = services.submit_proof_request(store, passport, skillId, description,
                                            evidence_name, evidence_hash, evidenceUrl)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return services.request_out(store, req)


@app.get("/me/skill-requests", response_model=list[SkillRequestOut])
def my_skill_requests(email: str = Depends(auth.student_email)):
    return [services.request_out(store, r) for r in store.list_requests(email)]


@app.get("/admin/skill-requests", response_model=list[SkillRequestOut],
         dependencies=[Depends(auth.require_admin)])
def admin_skill_requests():
    return [services.request_out(store, r) for r in store.list_requests()]


@app.post("/skill-requests/{request_id}/test", response_model=SkillRequestOut)
def complete_request_test(request_id: int, body: CompleteTestRequest,
                          email: str = Depends(auth.student_email)):
    try:
        req = services.complete_request_test(store, request_id, email, body.answers)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return services.request_out(store, req)


@app.post("/admin/skill-requests/{request_id}/attest", response_model=SkillRequestOut,
          dependencies=[Depends(auth.require_admin)])
def attest_skill_request(request_id: int, body: AttestRequest):
    try:
        req = services.attest_request(store, request_id, body.role, body.approver)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return services.request_out(store, req)


@app.post("/admin/skill-requests/{request_id}/approve", response_model=SkillRequestOut,
          dependencies=[Depends(auth.require_admin)])
def approve_skill_request(request_id: int, body: DecisionRequest,
                          x_reviewer: str | None = Header(default=None, alias="X-Reviewer")):
    try:
        sheet = make_sheet_source(settings) if settings.sheet_source != "seed" else None
        req = services.approve_request(store, request_id, body.note, sheet,
                                       reviewer=x_reviewer or "Admin", ctx=ctx)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return services.request_out(store, req)


@app.post("/admin/skill-requests/{request_id}/reject", response_model=SkillRequestOut,
          dependencies=[Depends(auth.require_admin)])
def reject_skill_request(request_id: int, body: DecisionRequest,
                         x_reviewer: str | None = Header(default=None, alias="X-Reviewer")):
    try:
        req = services.reject_request(store, request_id, body.note,
                                      reviewer=x_reviewer or "Admin", ctx=ctx)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return services.request_out(store, req)


# ------------------------------------------------------------ verification
@app.get("/verify/{code}", response_model=VerifyResult)  # public, no login
def verify_by_code(code: str):
    return services.verify_by_code(store, code, ctx)


@app.post("/verify/document", response_model=VerifyDocumentResult)  # public
def verify_document(body: VerifyDocumentRequest):
    return services.verify_document(store, body.passport, body.version, body.skills, ctx)


@app.post("/verify/document/pdf", response_model=VerifyResult)  # public
async def verify_document_pdf(file: UploadFile = File(...)):
    """Upload a passport PDF: extracts its printed verification code (or
    document hash) from the PDF text and verifies it like /verify/{code}."""
    raw = await file.read()
    text = raw.decode("latin-1", errors="ignore")
    code = re.search(r"\b\d{6}-V\d+-[0-9A-Fa-f]{8}\b", text)
    if code:
        return services.verify_by_code(store, code.group(0), ctx)
    digest = re.search(r"\b[0-9a-f]{64}\b", text)
    anchored = store.find_anchor(digest.group(0)) if digest else None
    if anchored:
        return services.verify_by_code(store, anchored["verification_code"], ctx)
    return VerifyResult(found=False, documentAuthentic=False, issuerAuthentic=False, isLatest=False)


@app.get("/anchors/{document_hash}")
def anchor_proof(document_hash: str):
    """Independent proof bundle: on-chain anchor + BTU's signature, so a
    third party can verify without trusting this API's /verify answer."""
    v = store.find_anchor(document_hash.lower())
    if not v:
        raise HTTPException(404, "No anchored version with this document hash")
    return {"documentHash": v["document_hash"], "txHash": v["tx_hash"],
            "network": v["network"], "blockNumber": v["block_number"],
            "passportId": v["passport_id"], "version": v["version"],
            "status": v.get("status") or "ACTIVE",
            "supersededReason": v.get("superseded_reason") or "",
            "revokedRecordIds": services._json_list(v.get("revoked_record_ids")),
            "signerRoles": services._json_list(v.get("signer_roles")),
            "ipfsCid": v.get("ipfs_cid") or "",
            "issuer": services.issuer_model(ctx).model_dump(by_alias=True),
            "issuerSignature": v["issuer_signature"],
            "issuerPublicKey": ctx.signer.public_key_b64(), "algorithm": "Ed25519"}


# ------------------------------------------------------- revocation
@app.post("/admin/passports/{passport_id}/skills/{record_id}/revoke",
          dependencies=[Depends(auth.require_admin)])
def revoke_skill(passport_id: str, record_id: str, body: RevokeRequest):
    try:
        sheet = make_sheet_source(settings) if settings.sheet_source != "seed" else None
        v = services.revoke_skill(store, passport_id, record_id, body.reason, ctx, sheet)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return v.model_dump(by_alias=True)


# ------------------------------------------- credentials / badges / IPFS
def _passport_and_version(passport_id: str, version: int):
    row = store.get_passport(passport_id)
    if not row:
        raise HTTPException(404, f"Passport {passport_id} not found")
    v = store.get_version(passport_id, version)
    if not v:
        raise HTTPException(404, f"Version {version} not found")
    return row, v


@app.get("/passports/{passport_id}/versions/{version}/credential")
def credential(passport_id: str, version: int):
    row, v = _passport_and_version(passport_id, version)
    return services.build_credential(store, row, v, ctx)


@app.get("/passports/{passport_id}/versions/{version}/badges")
def badges(passport_id: str, version: int):
    row, v = _passport_and_version(passport_id, version)
    return services.build_badges(store, row, v, ctx, settings.public_base_url)


@app.post("/passports/{passport_id}/versions/{version}/publish",
          dependencies=[Depends(auth.require_admin)])
async def publish_ipfs(passport_id: str, version: int, file: UploadFile = File(...)):
    row, v = _passport_and_version(passport_id, version)
    raw = await file.read()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    (settings.upload_dir / f"{passport_id}-V{version}.pdf").write_bytes(raw)
    from .ipfs import make_ipfs
    rec = make_ipfs(settings.ipfs_mode).upload(raw, file.filename or "")
    store.update_version_ipfs(passport_id, version, rec.cid)
    return {"cid": rec.cid, "sha256": rec.sha256, "gatewayUrl": rec.gateway_url,
            "passportId": passport_id, "version": version}


# ------------------------------------------------- employer / public
_bulk_hits: dict[str, list[float]] = {}


@app.post("/verify/bulk", response_model=list[VerifyResult])
def verify_bulk(body: BulkVerifyRequest, request: Request):
    import time as _time
    ip = request.client.host if request.client else "unknown"
    now = _time.time()
    hits = [t for t in _bulk_hits.get(ip, []) if now - t < 60]
    if len(hits) >= settings.bulk_rate_limit_per_minute:
        raise HTTPException(429, "Rate limit exceeded for bulk verification")
    hits.append(now)
    _bulk_hits[ip] = hits
    if len(body.codes) > settings.bulk_verify_limit:
        raise HTTPException(400, f"Too many codes (max {settings.bulk_verify_limit})")
    return [services.verify_by_code(store, c, ctx) for c in body.codes]


@app.post("/verify/explain")
def explain_skill(body: ExplainRequest):
    item = services.catalogue_item(store, body.skill_id)
    if not item:
        raise HTTPException(404, f"Unknown skill {body.skill_id}")
    from .ai import make_explainer
    return make_explainer(settings.ai_mode).explain(item, body.question)


@app.get("/public/{slug}")
def public_profile(slug: str):
    row = store.get_passport_by_slug(slug)
    if not row:
        raise HTTPException(404, "Profile not found")
    p = services.passport_model(store, row)
    latest = p.versions[-1] if p.versions else None
    return {"slug": slug, "passportId": p.passport_id, "firstName": p.first_name,
            "lastName": p.last_name, "program": p.program,
            "educationLevel": p.education_level, "firstIssued": p.first_issued,
            "latestVersion": latest.version if latest else None,
            "verificationCode": latest.verification_code if latest else None,
            "skills": [s.model_dump(by_alias=True) for s in (latest.skills if latest else [])]}


# ------------------------------------------------------------ student+
@app.post("/me/skill-gap")
def skill_gap(body: SkillGapRequest, email: str = Depends(auth.student_email)):
    return services.skill_gap(store, _student_passport(email), body.job_description)


@app.get("/me/passport/wallet")
def wallet_pass(email: str = Depends(auth.student_email)):
    row = _student_passport(email)
    versions = store.get_versions(row["passport_id"])
    if not versions:
        raise HTTPException(404, "Passport not issued yet")
    v = versions[-1]
    from .wallet_pass import build_wallet_pass
    url = f"{settings.public_base_url}/verify?code={v['verification_code']}"
    return build_wallet_pass(row, v, url)


# --------------------------------------------------------- needs review
@app.get("/admin/needs-review", response_model=list[ReviewFlagOut],
         dependencies=[Depends(auth.require_admin)])
def needs_review():
    return store.list_flags("FLAGGED")


@app.post("/admin/needs-review/{flag_id}/release", response_model=ReviewFlagOut,
          dependencies=[Depends(auth.require_admin)])
def release_flag(flag_id: int):
    out = store.decide_flag(flag_id, "RELEASED", services.now_iso())
    if not out:
        raise HTTPException(404, "Flag not found")
    return out


@app.post("/admin/needs-review/{flag_id}/reject", response_model=ReviewFlagOut,
          dependencies=[Depends(auth.require_admin)])
def reject_flag(flag_id: int):
    out = store.decide_flag(flag_id, "REJECTED", services.now_iso())
    if not out:
        raise HTTPException(404, "Flag not found")
    return out
