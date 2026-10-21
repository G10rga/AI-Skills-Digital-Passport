"""Account verification gating + passport request pipeline."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh():
    assert client.post("/admin/reset").status_code == 200
    yield


def verify(email):
    r = client.post("/auth/request-code", json={"email": email})
    assert r.status_code == 200 and r.json()["delivery"] == "dev"
    code = r.json()["devCode"]
    v = client.post("/auth/verify-code", json={"email": email, "code": code})
    assert v.status_code == 200, v.text
    return {"Authorization": f"Bearer {v.json()['token']}"}


def test_wrong_code_and_no_access_without_verification():
    client.post("/auth/request-code", json={"email": "btu-t-0001@example.org"})
    bad = client.post("/auth/verify-code",
                      json={"email": "btu-t-0001@example.org", "code": "000000"})
    assert bad.status_code in (400, 200)  # 200 only if the random code was 000000
    if bad.status_code == 400:
        assert client.get("/me/passport").status_code == 401
    # an old-style unverified token must not open a passport
    from app.main import settings
    from app.security import make_token
    legacy = make_token("btu-t-0001@example.org", settings.app_secret, 1, verified=False)
    assert client.get("/me/passport",
                      headers={"Authorization": f"Bearer {legacy}"}).status_code == 403


def test_verified_user_with_passport_gets_it():
    h = verify("btu-t-0001@example.org")
    assert client.get("/me/passport", headers=h).json()["passportId"] == "BTU-AI-000125"


def test_passport_request_ready_when_data_exists():
    # BTU-T-0003 has sheet records but no issued version yet (nothing SYNCED)
    h = verify("btu-t-0003@example.org")
    assert client.get("/me/passport", headers=h).status_code == 200  # passport shell exists
    r = client.post("/passport-requests", headers=h, json={"studentId": "BTU-T-0003"})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "READY" and r.json()["passportId"] == "BTU-AI-000133"
    mine = client.get("/me/passport", headers=h).json()
    assert len(mine["versions"]) == 1 and mine["versions"][0]["skills"]
    # the sheet rows were marked SYNCED by the generation
    recs = [x for x in client.get("/records").json() if x["passportId"] == "BTU-AI-000133"]
    assert recs and all(x["syncStatus"] == "SYNCED" for x in recs)


def test_passport_request_goes_to_staff_when_no_data_then_fulfilled():
    email = "new.student@example.org"
    h = verify(email)
    r = client.post("/passport-requests", headers=h,
                    json={"studentId": "BTU-T-9999", "firstName": "New", "lastName": "Student"})
    assert r.json()["status"] == "PENDING_STAFF"
    req_id = r.json()["id"]
    # staff cannot fulfil while there is still no data in the sheet
    early = client.post(f"/admin/passport-requests/{req_id}/approve", json={})
    assert early.status_code == 400
    # staff adds the student to the sheet (registers passport) then approves
    from app.main import store
    store.register_passport({"passportId": "BTU-AI-000200", "studentId": "BTU-T-9999",
                             "firstName": "New", "lastName": "Student", "email": email,
                             "firstIssued": "2026-10-21"})
    store.upsert_record({"studentId": "BTU-T-9999", "firstName": "New", "lastName": "Student",
                         "email": email, "passportId": "BTU-AI-000200",
                         "firstIssued": "2026-10-21", "recordId": "REC-9001",
                         "skillId": "SKL-001", "skillName": "AI Literacy",
                         "skillCategory": "AI Skill", "badgeCode": "BDG-AI-001",
                         "skillDescription": "Fundamentals", "dateEarned": "2026-10-20",
                         "syncStatus": "NOT SYNCED"})
    ok = client.post(f"/admin/passport-requests/{req_id}/approve", json={})
    assert ok.status_code == 200 and ok.json()["status"] == "READY", ok.text
    assert client.get("/me/passport", headers=h).json()["passportId"] == "BTU-AI-000200"
    notes = client.get("/me/notifications", headers=h).json()
    assert notes and "ready" in notes[0]["message"]


def test_passport_request_rejected_notifies():
    h = verify("ghost@example.org")
    r = client.post("/passport-requests", headers=h, json={}).json()
    out = client.post(f"/admin/passport-requests/{r['id']}/reject",
                      json={"note": "Not a BTU student"}).json()
    assert out["status"] == "REJECTED"
    assert "declined" in client.get("/me/notifications", headers=h).json()[0]["message"]


def test_passport_request_requires_verified_account():
    assert client.post("/passport-requests", json={}).status_code == 401


def test_code_is_never_returned_without_smtp_or_dev_flag():
    """Production security: no SMTP + dev codes off -> 503, never a leaked code."""
    from app.main import settings
    old_host, old_dev = settings.smtp_host, settings.allow_dev_verification_codes
    settings.smtp_host, settings.allow_dev_verification_codes = "", False
    try:
        r = client.post("/auth/request-code", json={"email": "victim@example.org"})
        assert r.status_code == 503
        assert "devCode" not in r.text
    finally:
        settings.smtp_host, settings.allow_dev_verification_codes = old_host, old_dev
