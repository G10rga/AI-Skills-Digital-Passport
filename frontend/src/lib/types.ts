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
  versions: PassportVersion[]; // ascending; last = latest
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
}

export interface SyncResult {
  processed: number;
  synced: number;
  duplicates: number;
  errors: number;
  passportsUpdated: { passportId: string; newVersion: number }[];
  log: { recordId: string; status: string; note: string }[];
}
