"""Mirrors frontend/src/lib/api.test.ts (same 4 rules) + backend-only
rules: duplicates, unknown passports, issuer signature, student auth."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_demo():
    assert client.post("/admin/reset").status_code == 200
    yield


def get(pid="BTU-AI-000125"):
    r = client.get(f"/passports/{pid}")
    assert r.status_code == 200
    return r.json()


# --- the four rules from the frontend test suite -------------------------
def test_sync_adds_skills_as_new_version_keeping_passport_id():
    before = get()
    r = client.post("/sync").json()
    after = get()
    assert after["passportId"] == "BTU-AI-000125"
    assert len(after["versions"]) == len(before["versions"]) + 1
    assert r["synced"] > 0 and {"passportId": "BTU-AI-000125",
                                "newVersion": len(after["versions"])} in r["passportsUpdated"]


def test_second_sync_adds_nothing():
    client.post("/sync")
    assert client.post("/sync").json()["synced"] == 0


def test_edited_name_fails_verification():
    client.post("/sync")
    p, v = get(), get()["versions"][-1]
    assert client.get(f"/verify/{v['verificationCode']}").json()["documentAuthentic"] is True
    body = {"passport": {**{k: p[k] for k in
            ("passportId", "studentId", "firstName", "lastName", "email", "program",
             "educationLevel", "studentStatus", "firstIssued")}, "firstName": "Giorgii"},
            "version": v["version"], "skills": v["skills"]}
    assert client.post("/verify/document", json=body).json()["matches"] is False


def test_old_version_is_genuine_but_not_latest():
    client.post("/sync")
    code = get()["versions"][0]["verificationCode"]
    r = client.get(f"/verify/{code}").json()
    assert r["found"] is True and r["isLatest"] is False
    assert r["documentAuthentic"] is True and r["issuerAuthentic"] is True


# --- backend rules -------------------------------------------------------
def test_unknown_code_and_unknown_passport():
    assert client.get("/verify/000000-V1-DEADBEEF").json()["found"] is False
    assert client.get("/passports/BTU-AI-999999").status_code == 404


def test_duplicate_and_error_rows_never_touch_passport():
    from app.main import store
    base = get()
    store.upsert_record({  # same skillId as an existing skill, new recordId
        "studentId": "BTU-T-0001", "firstName": "Giorgi", "lastName": "Kapanadze",
        "email": "btu-t-0001@example.org", "passportId": "BTU-AI-000125",
        "firstIssued": "2026-09-15", "recordId": "REC-9001", "skillId": "SKL-001",
        "skillName": "AI Literacy", "skillCategory": "AI Skill", "badgeCode": "BDG-AI-001",
        "skillDescription": "dup", "dateEarned": "2026-10-19", "syncStatus": "NOT SYNCED"})
    store.upsert_record({  # unknown passport
        "studentId": "BTU-T-9999", "passportId": "BTU-AI-999999", "recordId": "REC-9002",
        "skillId": "SKL-001", "skillName": "X", "skillCategory": "AI Skill",
        "badgeCode": "B", "dateEarned": "2026-10-19", "syncStatus": "NOT SYNCED"})
    r = client.post("/sync").json()
    statuses = {e["recordId"]: e["status"] for e in r["log"]}
    assert statuses["REC-9001"] == "DUPLICATE" and statuses["REC-9002"] == "ERROR"
    recs = {x["recordId"]: x for x in client.get("/records").json()}
    assert recs["REC-9002"]["syncNotes"] == "Unknown Passport ID"
    # existing skills unchanged apart from the legitimate new-version sync
    assert get()["versions"][0] == base["versions"][0]


def test_issuer_signature_verifiable_independently():
    v = get()["versions"][0]
    proof = client.get(f"/anchors/{v['documentHash']}").json()
    assert proof["txHash"] == v["txHash"]
    from app.issuer import IssuerSigner
    assert IssuerSigner.verify(proof["issuerPublicKey"], proof["issuerSignature"],
                               v["documentHash"]) is True
    assert IssuerSigner.verify(proof["issuerPublicKey"], proof["issuerSignature"],
                               "0" * 64) is False
    assert client.get("/issuer").json()["did"] == "did:web:btu.edu.ge"


def test_student_login_and_my_passport():
    bad = client.post("/auth/login", json={"email": "nobody@example.org"})
    assert bad.status_code == 404
    ok = client.post("/auth/login", json={"email": "btu-t-0001@example.org"}).json()
    mine = client.get("/me/passport", headers={"Authorization": f"Bearer {ok['token']}"})
    assert mine.status_code == 200 and mine.json()["passportId"] == "BTU-AI-000125"
    assert client.get("/me/passport").status_code == 401


def test_admin_lists_match_frontend_shapes():
    summaries = client.get("/passports").json()
    assert summaries and {"passportId", "studentId", "fullName", "program",
                          "latestVersion", "skillCount", "pendingCount"} <= summaries[0].keys()
    records = client.get("/records").json()
    assert len(records) == 60 and records[0]["recordId"] == "REC-0001"


def test_canonical_hash_parity_with_frontend():
    """Golden value produced by the frontend's canonicalPassport()+sha256()
    (frontend/src/lib/api.ts) for BTU-AI-000125 V1 — see README."""
    v = get()["versions"][0]
    assert v["documentHash"] == GOLDEN_V1_HASH
    assert v["verificationCode"] == f"000125-V1-{GOLDEN_V1_HASH[:8].upper()}"


GOLDEN_V1_HASH = "8c757f04f4e9264acbfa0042cdefc9508524c350990acfdffc935c32995f35ea"
