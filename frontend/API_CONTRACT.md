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
