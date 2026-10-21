// Shared data shapes. The backend API should return exactly these shapes.
// See API_CONTRACT.md at the project root.

export type SkillCategory = "AI Skill" | "AI Applied Skill" | "AI Advanced Skill";

/** One row of the BTU Google Sheet ("Passport Skill Records"). */
export interface SkillRecord {
  studentId: string;
  firstName: string;
  lastName: string;
  email: string;
  program: string;
  educationLevel: string;
  passportId: string;
  firstIssued: string; // YYYY-MM-DD
  studentStatus: string;
  recordId: string;
  skillId: string;
  skillName: string;
  skillCategory: SkillCategory;
  badgeCode: string;
  skillDescription: string;
  dateEarned: string;
  syncStatus: "SYNCED" | "NOT SYNCED" | "DUPLICATE" | "ERROR" | null;
  syncedVersion: string | null;
  syncedAt: string | null;
  syncNotes: string | null;
}

export interface PassportSkill {
  recordId: string;
  skillId: string;
  skillName: string;
  skillCategory: SkillCategory;
  badgeCode: string;
  skillDescription: string;
  dateEarned: string;
}

export interface PassportVersion {
  version: number;
  issuedAt: string; // ISO
  skills: PassportSkill[];
  documentHash: string; // sha-256 of canonical passport content
  verificationCode: string;
  txHash: string;
  network: string;
  blockNumber: number;
  status?: "ACTIVE" | "SUPERSEDED" | "REVOKED_CONTENT";
  supersededReason?: string;
  revokedRecordIds?: string[];
  ipfsCid?: string;
  signerRoles?: string[];
}

export interface Passport {
  passportId: string;
  studentId: string;
  firstName: string;
  lastName: string;
  email: string;
  program: string;
  educationLevel: string;
  studentStatus: string;
  firstIssued: string;
  publicSlug?: string;
  versions: PassportVersion[]; // ascending; last = latest
}

export interface PublicProfile {
  slug: string;
  passportId: string;
  firstName: string;
  lastName: string;
  program: string;
  educationLevel: string;
  firstIssued: string;
  latestVersion: number | null;
  verificationCode: string | null;
  skills: PassportSkill[];
}

export interface PassportSummary {
  passportId: string;
  studentId: string;
  fullName: string;
  program: string;
  latestVersion: number | null;
  skillCount: number;
  pendingCount: number;
}

export interface Issuer {
  name: string;
  did: string;
  walletAddress: string;
}

export interface VerifyResult {
  found: boolean;
  documentAuthentic: boolean;
  issuerAuthentic: boolean;
  isLatest: boolean;
  latestVersion?: number;
  issuer?: Issuer;
  passport?: Omit<Passport, "versions">;
  version?: PassportVersion;
  recomputedHash?: string;
  issuerSignature?: string;
  versionStatus?: string;
  supersededReason?: string;
}

export interface SkillCatalogItem {
  skillId: string;
  skillName: string;
  skillCategory: SkillCategory;
  badgeCode: string;
  skillDescription: string;
}

export interface SkillTest {
  skillId: string;
  skillName: string;
  skillCategory: SkillCategory;
  passMark: number;
  questions: { id: string; question: string; options: string[] }[];
}

export interface SkillRequest {
  id: number;
  passportId: string;
  studentId: string;
  studentEmail: string;
  skillId: string;
  skillName: string;
  skillCategory: string;
  badgeCode: string;
  method: "TEST" | "PROOF";
  testScore: number | null;
  evidenceName: string;
  evidenceHash: string;
  evidenceUrl: string;
  description: string;
  reasoning?: string;
  proofLinks?: string[];
  aiSummary?: string;
  aiScore?: number | null;
  aiModel?: string;
  reviewer?: string;
  instructorApproval?: boolean;
  careerCenterApproval?: boolean;
  instructorApprover?: string;
  careerCenterApprover?: string;
  status: "SUBMITTED" | "AI_REVIEWED" | "NEEDS_TEST" | "PENDING_ADMIN" | "PENDING" | "APPROVED" | "REJECTED";
  adminNote: string;
  recordId: string;
  createdAt: string;
  decidedAt: string;
  recordSyncStatus: string | null;
}

export interface ReviewFlag {
  id: number;
  recordId: string;
  passportId: string;
  reason: string;
  status: string;
  createdAt: string;
  decidedAt: string;
}

export interface SkillGapResult {
  matched: SkillCatalogItem[];
  missing: SkillCatalogItem[];
  suggestions: { skill: SkillCatalogItem; learnVia: string }[];
  model: string;
}

export interface PassportRequest {
  id: number;
  email: string;
  studentId: string;
  firstName: string;
  lastName: string;
  status: "READY" | "PENDING_STAFF" | "REJECTED";
  passportId: string;
  note: string;
  createdAt: string;
  decidedAt: string;
}

export interface AppNotification {
  id: number;
  email: string;
  message: string;
  createdAt: string;
  isRead: number;
}

export interface ExcelUploadResult {
  rows: number;
  imported: number;
  updated: number;
  skipped: number;
  sync: SyncResult | null;
}

export interface SyncResult {
  processed: number;
  synced: number;
  duplicates: number;
  errors: number;
  flagged?: number;
  passportsUpdated: { passportId: string; newVersion: number }[];
  log: { recordId: string; status: string; note: string }[];
}
