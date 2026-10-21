"""Expansion roadmap: requests v2, revocation, multi-signer, VC/badges/DID,
bulk verify, public profile, explain, anomaly preflight, skill-gap, wallet."""
import pytest
from fastapi.testclient import TestClient

from app.assessments import QUIZZES
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh():
    assert client.post("/admin/reset").status_code == 200
    yield


def token(email="btu-t-0001@example.org"):
    code = client.post("/auth/request-code", json={"email": email}).json()["devCode"]
    return {"Authorization": f"Bearer {client.post('/auth/verify-code', json={'email': email, 'code': code}).json()['token']}"}


def passport(pid="BTU-AI-000125"):
    return client.get(f"/passports/{pid}").json()


def pick_skill(email="btu-t-0001@example.org", category=None):
    mine = client.get("/me/passport", headers=token(email)).json()
    owned = {s["skillId"] for v in mine["versions"] for s in v["skills"]}
    cat = client.get("/skills/catalogue").json()
    return next(s for s in cat if s["skillId"] not in owned
                and (category is None or s["skillCategory"] == category))


def correct(skill):
    return {q["id"]: q["correct"] for q in QUIZZES[skill["skillCategory"]]}


# Phase 1 -----------------------------------------------------------------
def test_proof_advanced_needs_test_then_pending_admin():
    skill = pick_skill(category="AI Advanced Skill")
    r = client.post("/skill-requests/proof", headers=token(),
                    data={"skillId": skill["skillId"], "description": "Built and deployed an ML pipeline project with evaluation",
                          "evidenceUrl": "https://example.org/cert"})
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["status"] == "NEEDS_TEST" and req["aiScore"] is not None and req["proofLinks"]
    assert req["reasoning"].startswith("Built and deployed")
    # cannot approve before the test
    assert client.post(f"/admin/skill-requests/{req['id']}/approve", json={}).status_code == 400
    done = client.post(f"/skill-requests/{req['id']}/test", headers=token(),
                       json={"answers": correct(skill)})
    assert done.status_code == 200 and done.json()["status"] == "PENDING_ADMIN"
    assert done.json()["testScore"] == 100


def test_multi_signer_gates_advanced_approval():
    skill = pick_skill(category="AI Advanced Skill")
    req = client.post("/skill-requests/test", headers=token(),
                      json={"skillId": skill["skillId"], "answers": correct(skill)}).json()
    assert client.post(f"/admin/skill-requests/{req['id']}/approve", json={}).status_code == 400
    a = client.post(f"/admin/skill-requests/{req['id']}/attest", json={"role": "Instructor", "approver": "Dr X"})
    assert a.json()["instructorApproval"] is True
    assert client.post(f"/admin/skill-requests/{req['id']}/approve", json={}).status_code == 400
    client.post(f"/admin/skill-requests/{req['id']}/attest", json={"role": "CareerCenter"})
    ok = client.post(f"/admin/skill-requests/{req['id']}/approve", json={},
                     headers={"X-Reviewer": "Admin Jane"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "APPROVED" and ok.json()["reviewer"] == "Admin Jane"
    client.post("/sync")
    latest = passport()["versions"][-1]
    assert skill["skillId"] in {s["skillId"] for s in latest["skills"]}
    assert "Instructor" in latest["signerRoles"] and "CareerCenter" in latest["signerRoles"]


def test_rejection_notifies_and_shows_reason():
    skill = pick_skill(category="AI Skill")
    req = client.post("/skill-requests/test", headers=token(),
                      json={"skillId": skill["skillId"], "answers": correct(skill)}).json()
    out = client.post(f"/admin/skill-requests/{req['id']}/reject",
                      json={"note": "Evidence does not match"}).json()
    assert out["status"] == "REJECTED"
    notes = client.get("/me/notifications", headers=token()).json()
    assert any("rejected" in n["message"] for n in notes)


# Phase 2 -----------------------------------------------------------------
def test_revocation_issues_new_version_and_verifier_explains():
    p = passport()
    v1 = p["versions"][-1]
    target = v1["skills"][0]
    old_code = v1["verificationCode"]
    r = client.post(f"/admin/passports/{p['passportId']}/skills/{target['recordId']}/revoke",
                    json={"reason": "Awarded in error"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "REVOKED_CONTENT"
    after = passport()
    latest = after["versions"][-1]
    assert target["recordId"] not in {s["recordId"] for s in latest["skills"]}
    assert latest["revokedRecordIds"] == [target["recordId"]]
    check = client.get(f"/verify/{old_code}").json()
    assert check["found"] and check["documentAuthentic"] and not check["isLatest"]
    assert "revoked" in check["supersededReason"]


# Phase 3 -----------------------------------------------------------------
def test_did_vc_badges_ipfs_registry():
    did = client.get("/.well-known/did.json").json()
    assert did["id"] == "did:web:btu.edu.ge" and did["verificationMethod"]
    reg = client.get("/issuer/registry").json()
    assert {r["role"] for r in reg} == {"Admin", "Instructor", "CareerCenter"}
    p = passport()
    v = p["versions"][-1]
    vc = client.get(f"/passports/{p['passportId']}/versions/{v['version']}/credential").json()
    assert vc["issuer"] == "did:web:btu.edu.ge" and vc["proof"]["documentHash"] == v["documentHash"]
    assert vc["credentialSubject"]["skills"]
    badges = client.get(f"/passports/{p['passportId']}/versions/{v['version']}/badges").json()
    assert len(badges) == len(v["skills"]) and badges[0]["type"][-1] == "OpenBadgeCredential"
    pub = client.post(f"/passports/{p['passportId']}/versions/{v['version']}/publish",
                      files={"file": ("passport.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert pub.status_code == 200 and pub.json()["cid"].startswith("bafy")
    assert passport()["versions"][-1]["ipfsCid"] == pub.json()["cid"]


# Phase 4 -----------------------------------------------------------------
def test_bulk_verify_explain_and_public_profile():
    p = passport()
    code = p["versions"][-1]["verificationCode"]
    bulk = client.post("/verify/bulk", json={"codes": [code, "000000-V1-DEADBEEF"]}).json()
    assert [b["found"] for b in bulk] == [True, False] and bulk[0]["isLatest"]
    ex = client.post("/verify/explain", json={"skillId": p["versions"][-1]["skills"][0]["skillId"],
                                              "question": "relevant for a data analyst role?"})
    assert ex.status_code == 200 and "BTU" in ex.json()["answer"]
    assert p["publicSlug"]
    prof = client.get(f"/public/{p['publicSlug']}").json()
    assert prof["passportId"] == p["passportId"] and prof["verificationCode"] == code
    assert len(prof["skills"]) == len(p["versions"][-1]["skills"])


# Phase 5 -----------------------------------------------------------------
def test_anomaly_batch_flagged_then_released():
    from app.main import store
    rows = []
    for i in range(6):
        rid = f"REC-910{i}"
        store.upsert_record({"studentId": "BTU-T-0001", "firstName": "Giorgi", "lastName": "Kapanadze",
                             "email": "btu-t-0001@example.org", "passportId": "BTU-AI-000125",
                             "firstIssued": "2026-09-15", "recordId": rid, "skillId": f"SKL-9{i}",
                             "skillName": f"Extra {i}", "skillCategory": "AI Skill",
                             "badgeCode": f"B-{i}", "skillDescription": "x", "dateEarned": "2026-10-19",
                             "syncStatus": "NOT SYNCED"})
    before = len(passport()["versions"])
    result = client.post("/sync").json()
    assert result["flagged"] >= 6
    assert len(passport()["versions"]) == before  # nothing issued while flagged
    flags = client.get("/admin/needs-review").json()
    assert len(flags) >= 6
    for f in flags:
        client.post(f"/admin/needs-review/{f['id']}/release")
    assert client.get("/admin/needs-review").json() == []


def test_skill_gap_and_wallet():
    gap = client.post("/me/skill-gap", headers=token(),
                      json={"jobDescription": "We need AI literacy and prompt engineering for marketing analytics"})
    assert gap.status_code == 200 and "matched" in gap.json() and "missing" in gap.json()
    w = client.get("/me/passport/wallet", headers=token())
    assert w.status_code == 200 and w.json()["googleWallet"]["genericObject"]["barcode"]["value"]


# golden parity guard still holds through all of the above
def test_canonical_hash_parity_unchanged():
    assert passport()["versions"][0]["documentHash"] == \
        "8c757f04f4e9264acbfa0042cdefc9508524c350990acfdffc935c32995f35ea"
