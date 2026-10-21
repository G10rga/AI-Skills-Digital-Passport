"""Issuer authenticity: BTU signs every issued version's documentHash
with an Ed25519 key. Anyone can fetch the public key (GET /issuer) and
check the signature (returned by GET /verify/{code} and
GET /anchors/{documentHash}) — no BTU server trust required.

The private key lives only on the backend (ISSUER_KEY_FILE, git-ignored
data dir). In production this key belongs in a KMS/HSM and the DID
document at did:web:btu.edu.ge should publish the same public key.
"""
from __future__ import annotations

import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature


class IssuerSigner:
    def __init__(self, key_file: Path):
        key_file.parent.mkdir(parents=True, exist_ok=True)
        if key_file.exists():
            self._key = serialization.load_pem_private_key(key_file.read_bytes(), password=None)
        else:
            self._key = Ed25519PrivateKey.generate()
            key_file.write_bytes(self._key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()))
            key_file.chmod(0o600)

    def public_key_b64(self) -> str:
        raw = self._key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return base64.b64encode(raw).decode()

    def sign(self, document_hash: str) -> str:
        return base64.b64encode(self._key.sign(document_hash.encode())).decode()

    @staticmethod
    def verify(public_key_b64: str, signature_b64: str, document_hash: str) -> bool:
        try:
            pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
            pub.verify(base64.b64decode(signature_b64), document_hash.encode())
            return True
        except (InvalidSignature, ValueError, Exception):  # malformed input == not authentic
            return False
