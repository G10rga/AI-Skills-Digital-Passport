"""Blockchain anchoring behind one interface.

SimulatedAnchor (default, hackathon demo): deterministic, offline, and
byte-identical to the frontend mock — txHash = 0x+sha256("tx:"+hash),
block = 18_400_000 + int(hash[:5], 16). It proves the *flow* (hash ->
anchor -> public re-check) without a funded testnet wallet.

Web3Anchor (ANCHOR_MODE=web3): sends a real 0-value transaction from
BTU's issuer wallet with the document hash as calldata on Polygon Amoy
(or any EVM RPC). Requires `pip install web3`, WEB3_RPC_URL and
WEB3_PRIVATE_KEY. Same interface — swapping it in changes nothing else.
"""
from __future__ import annotations

from dataclasses import dataclass

from .canonical import sha256_hex


@dataclass
class AnchorRecord:
    tx_hash: str
    network: str
    block_number: int


class SimulatedAnchor:
    def __init__(self, network: str):
        self.network = network

    def anchor(self, doc_hash: str) -> AnchorRecord:
        return AnchorRecord(
            tx_hash="0x" + sha256_hex("tx:" + doc_hash),
            network=self.network,
            block_number=18_400_000 + int(doc_hash[:5], 16),
        )


class Web3Anchor:
    def __init__(self, network: str, rpc_url: str, private_key: str):
        if not rpc_url or not private_key:
            raise RuntimeError("ANCHOR_MODE=web3 requires WEB3_RPC_URL and WEB3_PRIVATE_KEY")
        self.network, self.rpc_url, self.private_key = network, rpc_url, private_key

    def anchor(self, doc_hash: str) -> AnchorRecord:
        try:
            from web3 import Web3  # optional dependency, real-chain deployments only
        except ImportError as e:
            raise RuntimeError("ANCHOR_MODE=web3 requires `pip install web3`") from e
        w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        account = w3.eth.account.from_key(self.private_key)
        tx = {
            "from": account.address, "to": account.address, "value": 0,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": 30_000, "gasPrice": w3.eth.gas_price,
            "data": bytes.fromhex(doc_hash),
            "chainId": w3.eth.chain_id,
        }
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        return AnchorRecord(tx_hash=tx_hash.hex(), network=self.network,
                            block_number=int(receipt["blockNumber"]))


def make_anchor(mode: str, network: str, rpc_url: str = "", private_key: str = ""):
    return Web3Anchor(network, rpc_url, private_key) if mode == "web3" else SimulatedAnchor(network)
