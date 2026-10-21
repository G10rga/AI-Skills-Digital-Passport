# BTU AI Skills Digital Passport — API contract for the backend

The frontend currently runs on a mock (`src/lib/api.ts`) seeded from the hackathon test sheet.
Each function there maps to one endpoint below. To connect the real backend:

1. Set `VITE_API_BASE_URL` (e.g. `https://api.example.com`).
2. Replace each mock function body with a `fetch()` to the endpoint. Return shapes must match `src/lib/types.ts`.

All responses are JSON. Dates: `YYYY-MM-DD`; timestamps: ISO 8601 UTC.

## Data shapes (see `src/lib/types.ts`)
- `SkillRecord` — one row of the Google Sheet (columns A–T).
- `Passport` — `{ passportId, studentId, firstName, lastName, email, program, educationLevel, studentStatus, firstIssued, versions: PassportVersion[] }`. Name, Passport ID and `firstIssued` never change.
- `PassportVersion` — `{ version, issuedAt, skills: PassportSkill[], documentHash, verificationCode, txHash, network, blockNumber }`. Versions ascending; last = latest.
- `VerifyResult` — `{ found, documentAuthentic, issuerAuthentic, isLatest, latestVersion, issuer, passport, version, recomputedHash }`.
- `SyncResult` — `{ processed, synced, duplicates, errors, passportsUpdated[], log[] }`.

## Endpoints

| Mock function | Method & path | Auth | Returns |
|---|---|---|---|
| `listPassports` | `GET /passports` | admin | `PassportSummary[]` |
| `getPassport` | `GET /passports/{passportId}` | public | `Passport` or 404 |
| `getMyPassport` | `GET /me/passport` | student | `Passport` |
| `listRecords` | `GET /records` | admin | `SkillRecord[]` |
| `syncFromSheet` | `POST /sync` | admin | `SyncResult` |
| `verifyByCode` | `GET /verify/{code}` | **public, no login** | `VerifyResult` |
| `verifyDocumentContent` | `POST /verify/document` body `{ passport, version, skills }` (or a PDF upload) | public | `{ recomputedHash, matches, anchoredHash }` |
| `loginStudent` | BTU SSO / OAuth redirect | — | session |

## Rules the backend must enforce (frontend mock mirrors them)
- One passport per student; new skills create a **new version**, never a new passport.
- Skip duplicates: same `recordId` or same `skillId` already on the passport → status `DUPLICATE`.
- Reject rows with missing required fields, unknown Passport ID, or Student ID not matching the passport → status `ERROR` with a note. Never touch existing data on error.
- Write sync status, version and timestamp back to sheet columns Q–T.
- `documentHash` = SHA-256 of canonical content (see `canonicalPassport()` in `src/lib/api.ts`); anchor it on-chain from BTU's issuer wallet. Any changed field must fail verification.
- Verification must also prove the issuer is BTU (signature / issuer DID `did:web:btu.edu.ge`) and say whether the version is the latest.
- `verificationCode` format used by the UI: `{passport digits}-V{n}-{first 8 hash chars}`; any unique code works.
- Must scale to 5,000+ passports with batch sync.

## Student skill requests (added after the initial contract)

Students can request a skill BTU has not recorded yet. Nothing reaches a
passport without **admin approval + a normal sync** — approval only writes
a `NOT SYNCED` row into the sheet dataset (and appends to the live Google
Sheet when configured), exactly like an admin-entered row.

| Function | Method & path | Auth | Notes |
|---|---|---|---|
| `getSkillCatalogue` | `GET /skills/catalogue` | public | distinct skills from the sheet |
| `getSkillTest` | `GET /skills/{skillId}/test` | public | questions only; grading is server-side, pass = 70% |
| `submitTestRequest` | `POST /skill-requests/test` `{skillId, answers}` | student | creates a PENDING request only if the test passes |
| `submitProofRequest` | `POST /skill-requests/proof` (multipart: file and/or evidenceUrl + description) | student | file SHA-256 stored as evidence fingerprint (max 10 MB) |
| `listMySkillRequests` | `GET /me/skill-requests` | student | includes live sheet sync status once approved |
| `listSkillRequests` / `decideSkillRequest` | `GET /admin/skill-requests`, `POST /admin/skill-requests/{id}/approve\|reject` `{note}` | admin | approve creates the sheet record (`REC-…`, `NOT SYNCED`) |

Rules: a student cannot request a skill already on their passport or
with another PENDING request; rejected requests create no sheet record.

## Expansion (stub-first: LLM/IPFS/wallet behind interfaces)

Request statuses widened to `SUBMITTED | AI_REVIEWED | NEEDS_TEST |
PENDING_ADMIN | APPROVED | REJECTED` (legacy `PENDING` reads as
`PENDING_ADMIN`). Every request carries `reasoning` (= description),
`proofLinks[]`, `aiSummary`, `aiScore`, `aiModel` (deterministic stub
reviewer `app/ai.py`), `reviewer`, and — for the top `AI Advanced Skill`
tier — `instructorApproval`/`careerCenterApproval`. Advanced PROOF
requests land in `NEEDS_TEST`; `POST /skill-requests/{id}/test` completes
the test. `POST /admin/skill-requests/{id}/attest {role}` records a
signer; approval of an Advanced request is refused until both roles
attest. Approval still only writes the `NOT SYNCED` row (Trigger A).
The DB is canonical for requests; the Google source mirrors decided
requests into a `Skill Requests` sheet tab as a read-model.

New endpoints:

- `GET /issuer/registry`, `GET /.well-known/did.json` (+ `/issuer/did`) —
  BTU role registry and the resolvable `did:web:btu.edu.ge` document
  publishing the same Ed25519 key that signs versions.
- `POST /admin/passports/{id}/skills/{recordId}/revoke {reason}` —
  issues Vn+1 without the skill, `status=REVOKED_CONTENT`,
  `revokedRecordIds[]`; old codes verify with `supersededReason`
  ("outdated because a skill was later revoked: …"). Version status /
  revocation / signer-role metadata lives **outside** the canonical
  hashed payload (golden-hash parity is pinned by test).
- `GET /passports/{id}/versions/{n}/credential` — W3C VC wrapping;
  `.../badges` — Open Badges 3.0 `AchievementCredential` per skill;
  `POST .../publish` (PDF upload) — IPFS stub CID stored on the version.
- `POST /verify/bulk {codes[]}` (max 100, per-IP rate limit),
  `POST /verify/explain {skillId, question}` (stub explainer),
  `GET /public/{slug}` — shareable profile behind `/p/<slug>`;
  `Passport.publicSlug` is generated at registration.
- `GET /admin/needs-review`, `POST /admin/needs-review/{id}/release|reject` —
  anomaly preflight inside `sync()` (batch > `ANOMALY_BATCH_THRESHOLD`,
  or a record matching a REJECTED request) holds rows out of issuance as
  `NEEDS_REVIEW` log entries with `SyncResult.flagged`.
- `POST /me/skill-gap {jobDescription}` — stub keyword extractor diffed
  against the student's latest skills; read-only.
- `GET /me/passport/wallet` — Google/Apple wallet-pass stub JSON.
- Email + in-app notifications fire on request APPROVED/REJECTED, on
  revocation, and on each passport updated by a sync.
