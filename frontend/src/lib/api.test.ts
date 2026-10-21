import { describe, expect, it } from "vitest";
import { getPassport, syncFromSheet, verifyByCode, verifyDocumentContent } from "./api";

describe("passport rules", () => {
  it("sync adds skills as a new version, keeping the same Passport ID", async () => {
    const before = await getPassport("BTU-AI-000125");
    const v1 = before!.versions.length;
    await syncFromSheet();
    const after = await getPassport("BTU-AI-000125");
    expect(after!.passportId).toBe("BTU-AI-000125");
    expect(after!.versions.length).toBe(v1 + 1);
  });

  it("a second sync adds nothing (no duplicate skills)", async () => {
    const r = await syncFromSheet();
    expect(r.synced).toBe(0);
  });

  it("an edited name fails verification", async () => {
    const p = (await getPassport("BTU-AI-000125"))!;
    const v = p.versions.at(-1)!;
    expect((await verifyByCode(v.verificationCode)).documentAuthentic).toBe(true);
    const res = await verifyDocumentContent({ ...p, firstName: "Giorgii" }, v.version, v.skills);
    expect(res.matches).toBe(false);
  });

  it("an old version is genuine but not latest", async () => {
    const p = (await getPassport("BTU-AI-000125"))!;
    const r = await verifyByCode(p.versions[0]!.verificationCode);
    expect(r.found && !r.isLatest).toBe(true);
  });
});
