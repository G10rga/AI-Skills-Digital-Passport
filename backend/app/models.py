"""Pydantic shapes — byte-for-byte the same JSON the frontend expects
(`frontend/src/lib/types.ts`). Field names are camelCase on the wire."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Cfg = ConfigDict(populate_by_name=True)
SkillCategory = Literal["AI Skill", "AI Applied Skill", "AI Advanced Skill"]
SyncStatus = Literal["SYNCED", "NOT SYNCED", "DUPLICATE", "ERROR"]


class SkillRecord(BaseModel):
    model_config = Cfg
    student_id: str = Field(default="", alias="studentId")
    first_name: str = Field(default="", alias="firstName")
    last_name: str = Field(default="", alias="lastName")
    email: str = ""
    program: str = ""
    education_level: str = Field(default="", alias="educationLevel")
    passport_id: str = Field(default="", alias="passportId")
    first_issued: str = Field(default="", alias="firstIssued")
    student_status: str = Field(default="", alias="studentStatus")
    record_id: str = Field(default="", alias="recordId")
    skill_id: str = Field(default="", alias="skillId")
    skill_name: str = Field(default="", alias="skillName")
    skill_category: str = Field(default="", alias="skillCategory")
    badge_code: str = Field(default="", alias="badgeCode")
    skill_description: str = Field(default="", alias="skillDescription")
    date_earned: str = Field(default="", alias="dateEarned")
    sync_status: Optional[SyncStatus] = Field(default=None, alias="syncStatus")
    synced_version: Optional[str] = Field(default=None, alias="syncedVersion")
    synced_at: Optional[str] = Field(default=None, alias="syncedAt")
    sync_notes: Optional[str] = Field(default=None, alias="syncNotes")


class PassportSkill(BaseModel):
    model_config = Cfg
    record_id: str = Field(alias="recordId")
    skill_id: str = Field(alias="skillId")
    skill_name: str = Field(alias="skillName")
    skill_category: str = Field(alias="skillCategory")
    badge_code: str = Field(alias="badgeCode")
    skill_description: str = Field(alias="skillDescription")
    date_earned: str = Field(alias="dateEarned")


class PassportVersion(BaseModel):
    model_config = Cfg
    version: int
    issued_at: str = Field(alias="issuedAt")
    skills: list[PassportSkill]
    document_hash: str = Field(alias="documentHash")
    verification_code: str = Field(alias="verificationCode")
    tx_hash: str = Field(alias="txHash")
    network: str
    block_number: int = Field(alias="blockNumber")


class Passport(BaseModel):
    model_config = Cfg
    passport_id: str = Field(alias="passportId")
    student_id: str = Field(alias="studentId")
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    email: str
    program: str
    education_level: str = Field(alias="educationLevel")
    student_status: str = Field(alias="studentStatus")
    first_issued: str = Field(alias="firstIssued")
    versions: list[PassportVersion]


class PassportInfo(BaseModel):
    """Passport without versions (embedded in VerifyResult)."""
    model_config = Cfg
    passport_id: str = Field(alias="passportId")
    student_id: str = Field(alias="studentId")
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    email: str
    program: str
    education_level: str = Field(alias="educationLevel")
    student_status: str = Field(alias="studentStatus")
    first_issued: str = Field(alias="firstIssued")


class PassportSummary(BaseModel):
    model_config = Cfg
    passport_id: str = Field(alias="passportId")
    student_id: str = Field(alias="studentId")
    full_name: str = Field(alias="fullName")
    program: str
    latest_version: Optional[int] = Field(alias="latestVersion")
    skill_count: int = Field(alias="skillCount")
    pending_count: int = Field(alias="pendingCount")


class Issuer(BaseModel):
    name: str
    did: str
    wallet_address: str = Field(alias="walletAddress")
    model_config = Cfg


class IssuerPublic(Issuer):
    public_key: str = Field(alias="publicKey")
    algorithm: str = "Ed25519"


class VerifyResult(BaseModel):
    model_config = Cfg
    found: bool
    document_authentic: bool = Field(alias="documentAuthentic")
    issuer_authentic: bool = Field(alias="issuerAuthentic")
    is_latest: bool = Field(alias="isLatest")
    latest_version: Optional[int] = Field(default=None, alias="latestVersion")
    issuer: Optional[Issuer] = None
    passport: Optional[PassportInfo] = None
    version: Optional[PassportVersion] = None
    recomputed_hash: Optional[str] = Field(default=None, alias="recomputedHash")
    # extra (ignored by the current UI): lets any third party check BTU's
    # Ed25519 signature over documentHash against GET /issuer's publicKey.
    issuer_signature: Optional[str] = Field(default=None, alias="issuerSignature")


class SyncLogEntry(BaseModel):
    model_config = Cfg
    record_id: str = Field(alias="recordId")
    status: str
    note: str


class SyncResult(BaseModel):
    model_config = Cfg
    processed: int
    synced: int
    duplicates: int
    errors: int
    passports_updated: list[dict] = Field(alias="passportsUpdated")
    log: list[SyncLogEntry]


class LoginRequest(BaseModel):
    email: str


class LoginResponse(BaseModel):
    model_config = Cfg
    email: str
    token: str
    token_type: str = Field(default="Bearer", alias="tokenType")


class VerifyDocumentRequest(BaseModel):
    """Body of POST /verify/document — content as printed on the PDF."""
    model_config = Cfg
    passport: PassportInfo
    version: int
    skills: list[PassportSkill]


class VerifyDocumentResult(BaseModel):
    model_config = Cfg
    recomputed_hash: str = Field(alias="recomputedHash")
    matches: bool
    anchored_hash: Optional[str] = Field(alias="anchoredHash")
