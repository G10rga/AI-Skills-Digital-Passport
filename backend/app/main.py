"""BTU AI Skills Digital Passport — backend API.

Implements frontend/API_CONTRACT.md 1:1. Run:
    uvicorn app.main:app --app-dir backend --port 8000   (or: python -m app)
Interactive docs at /docs.
"""
from __future__ import annotations

import re
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import services
from .anchor import make_anchor
from .config import settings
from .issuer import IssuerSigner
from .models import (IssuerPublic, LoginRequest, LoginResponse, Passport,
                     PassportSummary, SkillRecord, SyncResult, VerifyDocumentRequest,
                     VerifyDocumentResult, VerifyResult)
from .security import Auth, make_token
from .sheets import make_sheet_source
from .store import Store, load_seed

store = Store(settings.database_path)
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


@app.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest):
    row = store.get_passport_by_email(body.email.strip())
    if not row:
        raise HTTPException(404, "No passport is linked to this BTU email")
    return LoginResponse(email=row["email"],
                         token=make_token(row["email"], settings.app_secret, settings.token_ttl_hours))


# ---------------------------------------------------------------- records
@app.get("/records", response_model=list[SkillRecord], dependencies=[Depends(auth.require_admin)])
def list_records():
    return services.record_models(store)


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
            "issuer": services.issuer_model(ctx).model_dump(by_alias=True),
            "issuerSignature": v["issuer_signature"],
            "issuerPublicKey": ctx.signer.public_key_b64(), "algorithm": "Ed25519"}
