/**
 * Mock API. Every exported function maps 1:1 to a backend endpoint
 * documented in API_CONTRACT.md. To connect the real backend, replace the
 * body of each function with a fetch() to `${API_BASE}/...` — the
 * components never touch the mock store directly.
 */
import seed from "@/data/records.json";
import type {
  Issuer,
  Passport,
  PassportSkill,
  PassportSummary,
  PassportVersion,
  PassportRequest,
  AppNotification,
  SkillCatalogItem,
  SkillRecord,
  SkillRequest,
  SkillTest,
  SyncResult,
  VerifyResult,
} from "./types";

export const API_BASE = import.meta.env["VITE_API_BASE_URL"] ?? "/api";

/**
 * Real backend mode: set VITE_API_BASE_URL (e.g. http://localhost:8000) and
 * every function below talks to the Python backend (see API_CONTRACT.md).
 * Unset = local mock below, unchanged. Optional VITE_ADMIN_API_KEY is sent
 * as X-Admin-Key for the admin endpoints.
 */
// Tests always run against the mock, even if a developer .env points at a backend.
const REMOTE = import.meta.env["MODE"] === "test"
  ? undefined
  : (import.meta.env["VITE_API_BASE_URL"] as string | undefined)?.replace(/\/$/, "");
const TOKEN_KEY = "btu-passport-token";

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isForm = typeof FormData !== "undefined" && init.body instanceof FormData;
  const headers: Record<string, string> = { ...(isForm ? {} : { "Content-Type": "application/json" }), ...(init.headers as Record<string, string>) };
  const adminKey = import.meta.env["VITE_ADMIN_API_KEY"] as string | undefined;
  if (adminKey) headers["X-Admin-Key"] = adminKey;
  const token = typeof window !== "undefined" ? window.localStorage.getItem(TOKEN_KEY) : null;
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${REMOTE}${path}`, { ...init, headers });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const BTU_ISSUER: Issuer = {
  name: "Business and Technology University (BTU)",
  did: "did:web:btu.edu.ge",
  walletAddress: "0xB7U0000000000000000000000000000000A15C",
};
const NETWORK = "Polygon Amoy (testnet)";
const STORE_KEY = "btu-passport-mock-v1";

const wait = (ms = 250) => new Promise((r) => setTimeout(r, ms));

// ---------- hashing ----------
export async function sha256(input: string | ArrayBuffer): Promise<string> {
  const data = typeof input === "string" ? new TextEncoder().encode(input) : input;
  const buf = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** Canonical content that gets hashed and anchored on-chain. */
export function canonicalPassport(
  p: Pick<Passport, "passportId" | "firstName" | "lastName" | "firstIssued">,
  version: number,
  skills: PassportSkill[],
) {
  return JSON.stringify({
    passportId: p.passportId,
    firstName: p.firstName,
    lastName: p.lastName,
    firstIssued: p.firstIssued,
    version,
    issuer: BTU_ISSUER.did,
    skills: [...skills]
      .sort((a, b) => a.recordId.localeCompare(b.recordId))
      .map((s) => [s.skillId, s.skillName, s.skillCategory, s.badgeCode, s.dateEarned, s.skillDescription]),
  });
}

// ---------- mock store ----------
interface Store {
  records: SkillRecord[];
  passports: Record<string, Passport>;
}
let store: Store | null = null;

const toSkill = (r: SkillRecord): PassportSkill => ({
  recordId: r.recordId,
  skillId: r.skillId,
  skillName: r.skillName,
  skillCategory: r.skillCategory,
  badgeCode: r.badgeCode,
  skillDescription: r.skillDescription,
  dateEarned: r.dateEarned,
});

async function makeVersion(p: Passport, version: number, skills: PassportSkill[], issuedAt: string): Promise<PassportVersion> {
  const documentHash = await sha256(canonicalPassport(p, version, skills));
  const txHash = "0x" + (await sha256("tx:" + documentHash));
  return {
    version,
    issuedAt,
    skills,
    documentHash,
    verificationCode: `${p.passportId.replace("BTU-AI-", "")}-V${version}-${documentHash.slice(0, 8).toUpperCase()}`,
    txHash,
    network: NETWORK,
    blockNumber: 18_400_000 + parseInt(documentHash.slice(0, 5), 16),
    status: "ACTIVE",
    supersededReason: "",
    revokedRecordIds: [],
    ipfsCid: "",
    signerRoles: ["Admin"],
  };
}

async function getStore(): Promise<Store> {
  if (store) return store;
  if (typeof window !== "undefined") {
    const saved = window.localStorage.getItem(STORE_KEY);
    if (saved) return (store = JSON.parse(saved));
  }
  const records = (seed as SkillRecord[]).map((r) => ({ ...r }));
  const passports: Record<string, Passport> = {};
  for (const r of records) {
    passports[r.passportId] ??= {
      passportId: r.passportId,
      studentId: r.studentId,
      firstName: r.firstName,
      lastName: r.lastName,
      email: r.email,
      program: r.program,
      educationLevel: r.educationLevel,
      studentStatus: r.studentStatus,
      firstIssued: r.firstIssued,
      versions: [],
    };
  }
  for (const p of Object.values(passports)) {
    const synced = records.filter((r) => r.passportId === p.passportId && r.syncStatus === "SYNCED");
    if (synced.length) {
      p.versions.push(await makeVersion(p, 1, synced.map(toSkill), synced[0]?.syncedAt?.replace(" UTC", "Z").replace(" ", "T") ?? new Date().toISOString()));
    }
  }
  store = { records, passports };
  persist();
  return store;
}

function persist() {
  if (store && typeof window !== "undefined") window.localStorage.setItem(STORE_KEY, JSON.stringify(store));
}

export async function resetDemoData() {
  if (REMOTE) { await apiFetch("/admin/reset", { method: "POST" }); return; }
  store = null;
  if (typeof window !== "undefined") window.localStorage.removeItem(STORE_KEY);
  await getStore();
}

// ---------- endpoints ----------

/** GET /passports */
export async function listPassports(): Promise<PassportSummary[]> {
  if (REMOTE) return apiFetch<PassportSummary[]>("/passports");
  await wait();
  const s = await getStore();
  return Object.values(s.passports).map((p) => {
    const latest = p.versions.at(-1);
    return {
      passportId: p.passportId,
      studentId: p.studentId,
      fullName: `${p.firstName} ${p.lastName}`,
      program: p.program,
      latestVersion: latest?.version ?? null,
      skillCount: latest?.skills.length ?? 0,
      pendingCount: s.records.filter((r) => r.passportId === p.passportId && r.syncStatus !== "SYNCED" && r.syncStatus !== "DUPLICATE").length,
    };
  });
}

/** GET /passports/:passportId */
export async function getPassport(passportId: string): Promise<Passport | null> {
  if (REMOTE) return apiFetch<Passport>(`/passports/${passportId}`).catch(() => null);
  await wait();
  const s = await getStore();
  return s.passports[passportId] ?? null;
}

/** GET /me/passport  (student, authenticated) */
export async function getMyPassport(email: string): Promise<Passport | null> {
  if (REMOTE) return apiFetch<Passport>("/me/passport").catch(() => null);
  await wait();
  const s = await getStore();
  return Object.values(s.passports).find((p) => p.email.toLowerCase() === email.toLowerCase()) ?? null;
}

/** GET /records  (admin) — mirror of the Google Sheet */
export async function listRecords(): Promise<SkillRecord[]> {
  if (REMOTE) return apiFetch<SkillRecord[]>("/records");
  await wait();
  return (await getStore()).records;
}

/** POST /sync  (admin) — pull new rows from Google Sheets, update passports, anchor new versions */
export async function syncFromSheet(): Promise<SyncResult> {
  if (REMOTE) return apiFetch<SyncResult>("/sync", { method: "POST" });
  await wait(900);
  const s = await getStore();
  const result: SyncResult = { processed: 0, synced: 0, duplicates: 0, errors: 0, passportsUpdated: [], log: [] };
  const now = new Date().toISOString();
  const pending = s.records.filter((r) => r.syncStatus !== "SYNCED" && r.syncStatus !== "DUPLICATE");
  const byPassport = new Map<string, SkillRecord[]>();

  for (const r of pending) {
    result.processed++;
    const p = s.passports[r.passportId];
    const required = [r.studentId, r.passportId, r.recordId, r.skillId, r.skillName, r.skillCategory, r.badgeCode, r.dateEarned];
    if (required.some((v) => !v) || !p || p.studentId !== r.studentId) {
      r.syncStatus = "ERROR";
      r.syncNotes = !p ? "Unknown Passport ID" : p.studentId !== r.studentId ? "Student ID does not match passport" : "Missing required field";
      result.errors++;
      result.log.push({ recordId: r.recordId, status: "ERROR", note: r.syncNotes });
      continue;
    }
    const current = p.versions.at(-1)?.skills ?? [];
    const queued = byPassport.get(p.passportId) ?? [];
    const dup = [...current, ...queued.map(toSkill)].some((x) => x.recordId === r.recordId || x.skillId === r.skillId);
    if (dup) {
      r.syncStatus = "DUPLICATE";
      r.syncNotes = "Skill already on passport — skipped";
      result.duplicates++;
      result.log.push({ recordId: r.recordId, status: "DUPLICATE", note: r.syncNotes });
      continue;
    }
    queued.push(r);
    byPassport.set(p.passportId, queued);
  }

  for (const [pid, recs] of byPassport) {
    const p = s.passports[pid]!;
    const prev = p.versions.at(-1);
    const nextNum = (prev?.version ?? 0) + 1;
    const v = await makeVersion(p, nextNum, [...(prev?.skills ?? []), ...recs.map(toSkill)], now);
    p.versions.push(v);
    for (const r of recs) {
      r.syncStatus = "SYNCED";
      r.syncedVersion = `V${nextNum}`;
      r.syncedAt = now.slice(0, 16).replace("T", " ") + " UTC";
      r.syncNotes = null;
      result.synced++;
      result.log.push({ recordId: r.recordId, status: "SYNCED", note: `${pid} → V${nextNum}` });
    }
    result.passportsUpdated.push({ passportId: pid, newVersion: nextNum });
  }
  persist();
  return result;
}

/** GET /verify/:code  (public, no login) */
export async function verifyByCode(code: string): Promise<VerifyResult> {
  if (REMOTE) return apiFetch<VerifyResult>(`/verify/${encodeURIComponent(code.trim())}`);
  await wait(500);
  const s = await getStore();
  const c = code.trim().toUpperCase();
  for (const p of Object.values(s.passports)) {
    const v = p.versions.find((x) => x.verificationCode === c);
    if (v) {
      const recomputed = await sha256(canonicalPassport(p, v.version, v.skills));
      const { versions, ...info } = p;
      const latest = versions.at(-1)!.version;
      return {
        found: true,
        documentAuthentic: recomputed === v.documentHash,
        issuerAuthentic: true,
        isLatest: v.version === latest,
        latestVersion: latest,
        issuer: BTU_ISSUER,
        passport: info,
        version: v,
        recomputedHash: recomputed,
        versionStatus: v.status ?? "ACTIVE",
        ...(v.version === latest ? {} : { supersededReason: `Superseded by V${latest}` }),
      };
    }
  }
  return { found: false, documentAuthentic: false, issuerAuthentic: false, isLatest: false };
}

/** POST /verify/document  (public) — body: the passport content as printed on a PDF */
export async function verifyDocumentContent(
  passport: Pick<Passport, "passportId" | "firstName" | "lastName" | "firstIssued">,
  version: number,
  skills: PassportSkill[],
): Promise<{ recomputedHash: string; matches: boolean; anchoredHash: string | null }> {
  if (REMOTE) return apiFetch("/verify/document", { method: "POST", body: JSON.stringify({ passport, version, skills }) });
  await wait(400);
  const s = await getStore();
  const anchored = s.passports[passport.passportId]?.versions.find((v) => v.version === version)?.documentHash ?? null;
  const recomputedHash = await sha256(canonicalPassport(passport, version, skills));
  return { recomputedHash, matches: recomputedHash === anchored, anchoredHash: anchored };
}

// ---------- student auth: email verification code (backend), mock fallback ----------
const AUTH_KEY = "btu-passport-session";

/** POST /auth/request-code — sends a 6-digit code; in dev delivery the code is returned. */
export async function requestVerificationCode(email: string): Promise<{ devCode: string | null }> {
  if (!REMOTE) return { devCode: "123456" }; // mock mode: any 6-digit-looking flow, code below accepts it
  const r = await apiFetch<{ devCode: string | null }>("/auth/request-code", { method: "POST", body: JSON.stringify({ email }) });
  return { devCode: r.devCode };
}

/** POST /auth/verify-code — verified token; only verified accounts open/request passports. */
export async function verifyAccountCode(email: string, code: string): Promise<{ email: string } | null> {
  if (!REMOTE) {
    if (!/^[0-9]{6}$/.test(code)) return null;
    const p = await getMyPassport(email);
    if (!p) return null;
    window.localStorage.setItem(AUTH_KEY, p.email);
    return { email: p.email };
  }
  try {
    const r = await apiFetch<{ email: string; token: string }>("/auth/verify-code", { method: "POST", body: JSON.stringify({ email, code }) });
    window.localStorage.setItem(TOKEN_KEY, r.token);
    window.localStorage.setItem(AUTH_KEY, r.email);
    return { email: r.email };
  } catch { return null; }
}

export function currentStudentEmail(): string | null {
  return typeof window === "undefined" ? null : window.localStorage.getItem(AUTH_KEY);
}
export function logoutStudent() {
  window.localStorage.removeItem(AUTH_KEY);
  window.localStorage.removeItem(TOKEN_KEY);
}

// ---------- passport requests ----------
/** POST /passport-requests — checks the DB by your verified account email only */
export async function requestPassport(): Promise<PassportRequest> {
  requireRemote();
  return apiFetch<PassportRequest>("/passport-requests", { method: "POST", body: JSON.stringify({}) });
}

export async function getMyPassportRequest(): Promise<PassportRequest | null> {
  requireRemote();
  return apiFetch<PassportRequest | null>("/me/passport-request");
}

export async function listNotifications(): Promise<AppNotification[]> {
  requireRemote();
  return apiFetch<AppNotification[]>("/me/notifications");
}

export async function listPassportRequests(): Promise<PassportRequest[]> {
  requireRemote();
  return apiFetch<PassportRequest[]>("/admin/passport-requests");
}

export async function decidePassportRequest(id: number, action: "approve" | "reject", note = ""): Promise<PassportRequest> {
  requireRemote();
  return apiFetch<PassportRequest>(`/admin/passport-requests/${id}/${action}`, { method: "POST", body: JSON.stringify({ note }) });
}

// ---------- skill requests (backend-only feature) ----------
const requireRemote = () => { if (!REMOTE) throw new Error("This feature needs the Python backend (set VITE_API_BASE_URL)"); };

/** GET /skills/catalogue */
export async function getSkillCatalogue(): Promise<SkillCatalogItem[]> {
  requireRemote();
  return apiFetch<SkillCatalogItem[]>("/skills/catalogue");
}

/** GET /skills/:skillId/test — questions only, answers graded server-side */
export async function getSkillTest(skillId: string): Promise<SkillTest> {
  requireRemote();
  return apiFetch<SkillTest>(`/skills/${skillId}/test`);
}

/** POST /skill-requests/test */
export async function submitTestRequest(skillId: string, answers: Record<string, number>): Promise<SkillRequest> {
  requireRemote();
  return apiFetch<SkillRequest>("/skill-requests/test", { method: "POST", body: JSON.stringify({ skillId, answers }) });
}

/** POST /skill-requests/proof (multipart) */
export async function submitProofRequest(skillId: string, description: string, evidenceUrl: string, file: File | null): Promise<SkillRequest> {
  requireRemote();
  const fd = new FormData();
  fd.set("skillId", skillId); fd.set("description", description); fd.set("evidenceUrl", evidenceUrl);
  if (file) fd.set("file", file);
  return apiFetch<SkillRequest>("/skill-requests/proof", { method: "POST", body: fd });
}

/** GET /me/skill-requests */
export async function listMySkillRequests(): Promise<SkillRequest[]> {
  requireRemote();
  return apiFetch<SkillRequest[]>("/me/skill-requests");
}

/** GET /admin/skill-requests */
export async function listSkillRequests(): Promise<SkillRequest[]> {
  requireRemote();
  return apiFetch<SkillRequest[]>("/admin/skill-requests");
}

/** POST /admin/skill-requests/:id/approve|reject */
export async function decideSkillRequest(id: number, action: "approve" | "reject", note = ""): Promise<SkillRequest> {
  requireRemote();
  return apiFetch<SkillRequest>(`/admin/skill-requests/${id}/${action}`, { method: "POST", body: JSON.stringify({ note }) });
}

// ---------- expansion: revocation, credentials, employer, admin ----------
import type { PublicProfile, ReviewFlag, SkillGapResult } from "./types";

/** POST /admin/skill-requests/:id/attest {role} — multi-signer for Advanced tier */
export async function attestSkillRequest(id: number, role: "Instructor" | "CareerCenter", approver = ""): Promise<SkillRequest> {
  requireRemote();
  return apiFetch<SkillRequest>(`/admin/skill-requests/${id}/attest`, { method: "POST", body: JSON.stringify({ role, approver }) });
}

/** POST /skill-requests/:id/test — completes a NEEDS_TEST request */
export async function completeRequestTest(id: number, answers: Record<string, number>): Promise<SkillRequest> {
  requireRemote();
  return apiFetch<SkillRequest>(`/skill-requests/${id}/test`, { method: "POST", body: JSON.stringify({ answers }) });
}

/** POST /admin/passports/:id/skills/:recordId/revoke */
export async function revokeSkill(passportId: string, recordId: string, reason: string): Promise<unknown> {
  requireRemote();
  return apiFetch(`/admin/passports/${passportId}/skills/${recordId}/revoke`, { method: "POST", body: JSON.stringify({ reason }) });
}

/** GET /issuer/registry */
export async function getIssuerRegistry(): Promise<unknown[]> {
  requireRemote();
  return apiFetch<unknown[]>("/issuer/registry");
}

/** GET /.well-known/did.json */
export async function getDidDocument(): Promise<unknown> {
  requireRemote();
  return apiFetch<unknown>("/.well-known/did.json");
}

/** GET /passports/:id/versions/:n/credential (W3C VC) */
export async function getCredential(passportId: string, version: number): Promise<unknown> {
  requireRemote();
  return apiFetch<unknown>(`/passports/${passportId}/versions/${version}/credential`);
}

/** GET /passports/:id/versions/:n/badges (Open Badges 3.0) */
export async function getBadges(passportId: string, version: number): Promise<unknown[]> {
  requireRemote();
  return apiFetch<unknown[]>(`/passports/${passportId}/versions/${version}/badges`);
}

/** POST /passports/:id/versions/:n/publish (IPFS stub) */
export async function publishVersionPdf(passportId: string, version: number, file: File): Promise<{ cid: string; gatewayUrl: string }> {
  requireRemote();
  const fd = new FormData();
  fd.set("file", file);
  return apiFetch(`/passports/${passportId}/versions/${version}/publish`, { method: "POST", body: fd });
}

/** POST /verify/bulk — employer batch verification, no login */
export async function verifyBulk(codes: string[]): Promise<VerifyResult[]> {
  if (REMOTE) return apiFetch<VerifyResult[]>("/verify/bulk", { method: "POST", body: JSON.stringify({ codes }) });
  return Promise.all(codes.map((c) => verifyByCode(c)));
}

/** POST /verify/explain — plain-language skill explainer (stub LLM) */
export async function explainSkill(skillId: string, question = ""): Promise<{ answer: string; model: string }> {
  requireRemote();
  return apiFetch("/verify/explain", { method: "POST", body: JSON.stringify({ skillId, question }) });
}

/** GET /public/:slug — shareable verified profile */
export async function getPublicProfile(slug: string): Promise<PublicProfile> {
  requireRemote();
  return apiFetch<PublicProfile>(`/public/${slug}`);
}

/** POST /me/skill-gap — job description vs my verified skills */
export async function submitSkillGap(jobDescription: string): Promise<SkillGapResult> {
  requireRemote();
  return apiFetch<SkillGapResult>("/me/skill-gap", { method: "POST", body: JSON.stringify({ jobDescription }) });
}

/** GET /me/passport/wallet — wallet pass stub (Google/Apple shaped JSON) */
export async function getWalletPass(): Promise<unknown> {
  requireRemote();
  return apiFetch<unknown>("/me/passport/wallet");
}

/** GET /admin/needs-review + release/reject */
export async function listNeedsReview(): Promise<ReviewFlag[]> {
  requireRemote();
  return apiFetch<ReviewFlag[]>("/admin/needs-review");
}

export async function decideNeedsReview(id: number, action: "release" | "reject"): Promise<ReviewFlag> {
  requireRemote();
  return apiFetch<ReviewFlag>(`/admin/needs-review/${id}/${action}`, { method: "POST" });
}
