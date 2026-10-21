"""Issuer Registry: which BTU roles may attest a skill, and with which
public identity. Admin is BTU's live Ed25519 signing key (GET /issuer);
Instructor / Career Center are registered roles whose approvals are
recorded on skill requests and surfaced in the anchor proof bundle.
"""
from __future__ import annotations


def issuer_registry(ctx) -> list[dict]:
    return [
        {"role": "Admin", "name": ctx.issuer_name, "did": ctx.issuer_did,
         "walletAddress": ctx.issuer_wallet,
         "publicKey": ctx.signer.public_key_b64(), "algorithm": "Ed25519",
         "canAttest": True},
        {"role": "Instructor", "name": "BTU Instructor / Mentor",
         "did": ctx.issuer_did, "walletAddress": "0x1NS7RUC70R00000000000000000000000000000",
         "publicKey": "", "algorithm": "Ed25519", "canAttest": True},
        {"role": "CareerCenter", "name": "BTU Career Center",
         "did": ctx.issuer_did, "walletAddress": "0xCAREERCE07ER000000000000000000000000000",
         "publicKey": "", "algorithm": "Ed25519", "canAttest": True},
    ]


ATTEST_ROLES = {"Instructor": "instructor", "CareerCenter": "career_center"}
