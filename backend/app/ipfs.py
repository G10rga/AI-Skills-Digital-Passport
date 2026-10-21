"""IPFS upload behind one interface. StubIpfs derives a deterministic
CID-shaped identifier from the content hash — no network, no pinning
service. A real uploader (Pinata / web3.storage) drops in behind upload().
Personal data stays off-chain either way: only {cid, sha256} is anchored.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .canonical import sha256_hex


@dataclass
class IpfsRecord:
    cid: str
    sha256: str
    gateway_url: str


class IpfsUploader(Protocol):
    def upload(self, data: bytes, filename: str = "") -> IpfsRecord: ...


class StubIpfs:
    def upload(self, data: bytes, filename: str = "") -> IpfsRecord:
        digest = sha256_hex(data)
        # CIDv1-shaped (base32-ish) deterministic stub identifier.
        cid = "bafy" + digest[:52]
        return IpfsRecord(cid=cid, sha256=digest,
                          gateway_url=f"https://ipfs.io/ipfs/{cid}")


def make_ipfs(mode: str = "stub"):
    return StubIpfs()  # future: IPFS_MODE=pinata returns a real uploader
