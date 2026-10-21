# BTU AI Skills Digital Passport — Python backend

Pure-Python core (FastAPI + PostgreSQL/SQLite, all computation in `app/`) implementing
[`frontend/API_CONTRACT.md`](../frontend/API_CONTRACT.md) 1:1. Response shapes
match `frontend/src/lib/types.ts` exactly.

## Run

There is ONE virtualenv for the whole project, at the repo root (`.venv`) —
PyCharm's project interpreter should point at `.venv/bin/python`.

```bash
# from the repo root, once:
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt

# run (PyCharm: right-click backend/run.py -> Run), or from a terminal:
.venv/bin/python backend/run.py                   # http://127.0.0.1:8000/docs
```

Open http://localhost:8000/docs. On first start the database is seeded from
`frontend/src/data/records.json`: one passport per student, V1 issued from
rows already marked `SYNCED`.

Connect the frontend: copy `frontend/.env.example` → `frontend/.env`
(`VITE_API_BASE_URL=http://localhost:8000`), restart the frontend.
Unset = the frontend keeps using its local mock.

## Test

```bash
.venv/bin/python -m pytest backend/tests   # 10 tests, incl. the 4 rules from
                                           # frontend/src/lib/api.test.ts
```

**Hash parity is pinned by a golden test**: `BTU-AI-000125` V1 must hash to
`8c757f04…f35ea` — the exact value the frontend's JS `canonicalPassport()` +
SHA-256 produces. If canonicalization ever drifts, that test fails before a
real passport does.

## How it maps to the hackathon requirements

| Requirement | Where |
|---|---|
| One permanent passport per student; name / Passport ID / firstIssued frozen | `app/store.py` (`INSERT OR IGNORE` identity, append-only versions) |
| Google Sheets = source of truth (A–P in, Q–T written back) | `app/sheets.py` — `GoogleSheetsSheet` (service account), `XlsxSheet`, `LocalJsonSheet`; select with `SHEET_SOURCE` |
| Sync: new skills → **new version**, never a new passport; duplicates skipped; bad rows → `ERROR`, existing data untouched | `app/services.py:sync` (mirrors the frontend mock rule-for-rule) |
| Document authenticity: SHA-256 of canonical content, any changed field fails | `app/canonical.py` (byte-identical to the frontend's canonical JSON) |
| Issuer authenticity: BTU signs every version (Ed25519); public key at `GET /issuer`, proof bundle at `GET /anchors/{hash}` | `app/issuer.py` |
| Blockchain anchoring per version | `app/anchor.py` — `SimulatedAnchor` (default, deterministic & offline, same tx/block derivation as the mock) or `Web3Anchor` (`ANCHOR_MODE=web3`, real Polygon Amoy tx with the hash as calldata) |
| Public verification, no login | `GET /verify/{code}`, `POST /verify/document`, `POST /verify/document/pdf` (extracts the printed code/hash from an uploaded PDF) |
| Student access | `POST /auth/login {email}` → signed bearer token → `GET /me/passport`. This is the one seam to swap for real BTU SSO/OAuth |
| Scale (5,000+/yr) | Batched per-passport versioning in one sync pass, indexed store; PostgreSQL in production via `DATABASE_URL` (SQLite locally) |

## Endpoints

| Method & path | Auth | Contract function |
|---|---|---|
| `GET /passports` | admin | `listPassports` |
| `GET /passports/{passportId}` | public | `getPassport` (404 if unknown) |
| `GET /me/passport` | student token | `getMyPassport` |
| `POST /auth/login` `{email}` | public | `loginStudent` (SSO placeholder) |
| `GET /records` | admin | `listRecords` |
| `POST /sync` | admin | `syncFromSheet` |
| `GET /verify/{code}` | **public** | `verifyByCode` |
| `POST /verify/document` | public | `verifyDocumentContent` |
| `POST /verify/document/pdf` | public | PDF upload variant |
| `GET /anchors/{documentHash}`, `GET /issuer`, `GET /health` | public | independent issuer/anchor proof |
| `POST /admin/reset` | admin | `resetDemoData` (demo; `ALLOW_RESET=false` disables) |

Auth: admin via `X-Admin-Key: $ADMIN_API_KEY` (open when unset — local demo
only). Config is all env vars, see `.env.example`.

## Layout

```
app/config.py     env settings          app/anchor.py   chain anchoring (simulated | web3)
app/models.py     wire shapes (= types.ts)  app/issuer.py  Ed25519 BTU signing key
app/canonical.py  canonical JSON + SHA-256  app/sheets.py  Google / XLSX / JSON sheet sources
app/store.py      Postgres/SQLite store app/services.py sync / issue / verify (pure, tested)
app/security.py   admin key + student tokens
app/main.py       FastAPI endpoints     tests/          pytest suite
```

## Expansion (all stub-first, no second pipeline)

Everything below hooks into the same two trigger points: (a) an approved
skill becoming a `NOT SYNCED` row, and (b) `services.issue_version()`.
Canonical hashing is untouched (golden parity test guards it); version
status, revocation, signer roles and IPFS CID are stored alongside.

- Requests v2: stub AI review (`app/ai.py`, `AI_MODE=stub`) scores every
  submission (`aiSummary/aiScore/aiModel`); Advanced PROOF requests go
  `NEEDS_TEST` until the quiz is passed; Advanced approvals require
  Instructor + Career Center attestation (`/admin/skill-requests/{id}/attest`,
  `GET /issuer/registry` in `app/registry.py`) and the roles are recorded
  on the issued version. Google Sheets deployments mirror decided
  requests into a `Skill Requests` tab (DB stays canonical).
- Revocation: `POST /admin/passports/{id}/skills/{recordId}/revoke`
  issues a `REVOKED_CONTENT` version; verifiers see *why* an old version
  is outdated. The brief's Solidity `PassportVersion{ACTIVE,
  SUPERSEDED, REVOKED_CONTENT}` shape is the future `Web3Anchor`
  contract mirroring these stored fields.
- Standards: `GET /.well-known/did.json`, per-version W3C VC
  (`.../credential`) and Open Badges 3.0 (`.../badges`) exports, IPFS
  stub publish (`app/ipfs.py`, `IPFS_MODE=stub`).
- Employer side: `POST /verify/bulk` ( capped, rate-limited),
  `POST /verify/explain`, public profile `GET /public/{slug}` → `/p/<slug>`.
- Admin: anomaly preflight in `sync()` → `review_flags` / Needs Review
  (`ANOMALY_BATCH_THRESHOLD`), dashboard filters, `POST /me/skill-gap`.
- Polish: QR already on the passport cover; email + notifications on
  approve/reject/revoke/sync; wallet-pass stub (`app/wallet_pass.py`,
  `GET /me/passport/wallet`). Tests: `tests/test_expansion.py`.

## Student skill requests

`GET /skills/catalogue` + `GET /skills/{skillId}/test` (5 scenario
questions per stamp category in `app/assessments.py`, graded server-side,
pass 70%) or proof upload (`POST /skill-requests/proof`, SHA-256 evidence
fingerprint) create PENDING requests. Admins approve/reject in the Admin
→ Skill requests tab; approval writes a `NOT SYNCED` sheet record (and
appends to the live Google Sheet/XLSX when configured), so the normal
sync issues it as a new anchored version. Tests: `tests/test_skill_requests.py`.
