"""Environment-driven settings. No secrets are hard-coded for production:
set them via backend/.env (see .env.example) or real environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    # storage: PostgreSQL when DATABASE_URL is set (production), else SQLite file
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    database_path: Path = field(default_factory=lambda: Path(os.getenv("DATABASE_PATH", BACKEND_DIR / "data" / "passports.db")))
    seed_file: Path = field(default_factory=lambda: Path(os.getenv("SEED_FILE", REPO_DIR / "frontend" / "src" / "data" / "records.json")))

    # issuer (BTU)
    issuer_name: str = field(default_factory=lambda: os.getenv("ISSUER_NAME", "Business and Technology University (BTU)"))
    issuer_did: str = field(default_factory=lambda: os.getenv("ISSUER_DID", "did:web:btu.edu.ge"))
    issuer_wallet: str = field(default_factory=lambda: os.getenv("ISSUER_WALLET_ADDRESS", "0xB7U0000000000000000000000000000000A15C"))
    issuer_key_file: Path = field(default_factory=lambda: Path(os.getenv("ISSUER_KEY_FILE", BACKEND_DIR / "data" / "issuer_key.pem")))

    # blockchain anchoring: "simulated" (deterministic, offline, demo) | "web3" (real chain)
    anchor_mode: str = field(default_factory=lambda: os.getenv("ANCHOR_MODE", "simulated"))
    network: str = field(default_factory=lambda: os.getenv("ANCHOR_NETWORK", "Polygon Amoy (testnet)"))
    web3_rpc_url: str = field(default_factory=lambda: os.getenv("WEB3_RPC_URL", ""))
    web3_private_key: str = field(default_factory=lambda: os.getenv("WEB3_PRIVATE_KEY", ""))

    # sheet source: "seed" (local JSON) | "xlsx" | "google"
    sheet_source: str = field(default_factory=lambda: os.getenv("SHEET_SOURCE", "seed"))
    xlsx_path: Path = field(default_factory=lambda: Path(os.getenv("XLSX_PATH", REPO_DIR / "BTU AI Skills Digital Passport Hackathon_Test Data.xlsx")))
    google_spreadsheet_id: str = field(default_factory=lambda: os.getenv("GOOGLE_SPREADSHEET_ID", ""))
    google_credentials_file: str = field(default_factory=lambda: os.getenv("GOOGLE_CREDENTIALS_FILE", ""))
    google_sheet_range: str = field(default_factory=lambda: os.getenv("GOOGLE_SHEET_RANGE", "Passport Skill Records!A4:T"))
    sheet_writeback: bool = field(default_factory=lambda: _bool("SHEET_WRITEBACK", False))

    # auth. Empty admin key = open admin API (local hackathon demo ONLY).
    admin_api_key: str = field(default_factory=lambda: os.getenv("ADMIN_API_KEY", ""))
    app_secret: str = field(default_factory=lambda: os.getenv("APP_SECRET", "dev-only-change-me"))
    token_ttl_hours: int = field(default_factory=lambda: int(os.getenv("TOKEN_TTL_HOURS", "12")))
    allow_dev_email_auth: bool = field(default_factory=lambda: _bool("ALLOW_DEV_EMAIL_AUTH", True))
    allow_reset: bool = field(default_factory=lambda: _bool("ALLOW_RESET", True))

    cors_origins: list[str] = field(default_factory=lambda: [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,http://localhost:8080,http://127.0.0.1:5173,http://127.0.0.1:8080").split(",") if o.strip()
    ])


settings = Settings()
