"""Student skill-request pipeline: test / proof -> admin -> sheet -> sync."""
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
    return client.post("/auth/verify-code", json={"email": email, "code": code}).json()["token"]


def auth(email="btu-t-0001@example.org"):
    return {"Authorization": f"Bearer {token(email)}"}


def catalogue():
    return client.get("/skills/catalogue").json()


def pick_new_skill(email="btu-t-0001@example.org"):
    mine = client.get("/me/passport", headers=auth(email)).json()
    owned = {s["skillId"] for v in mine["versions"] for s in v["skills"]}
    return next(s for s in catalogue() if s["skillId"] not in owned)


def correct_answers(skill):
    quiz = QUIZZES[skill["skillCategory"]]
    return {q["id"]: q["correct"] for q in quiz}


def submit_passing_test(email="btu-t-0001@example.org"):
    skill = pick_new_skill(email)
    r = client.post("/skill-requests/test", headers=auth(email),
                    json={"skillId": skill["skillId"], "answers": correct_answers(skill)})
    assert r.status_code == 201, r.text
    return skill, r.json()


def test_catalogue_and_test_shape_hide_answers():
    cat = catalogue()
    assert len(cat) == 16
    t = client.get(f"/skills/{cat[0]['skillId']}/test").json()
    assert t["passMark"] == 70 and len(t["questions"]) == 5
    assert all("correct" not in q for q in t["questions"])


def test_failing_test_creates_no_request():
    skill = pick_new_skill()
    wrong = {qid: 99 for qid in correct_answers(skill)}
    r = client.post("/skill-requests/test", headers=auth(),
                    json={"skillId": skill["skillId"], "answers": wrong})
    assert r.status_code == 400 and "not passed" in r.json()["detail"]
    assert client.get("/me/skill-requests", headers=auth()).json() == []


def test_full_pipeline_test_request_approve_sync_new_version():
    before = client.get("/passports/BTU-AI-000125").json()
    skill, req = submit_passing_test()
    assert req["status"] == "PENDING_ADMIN" and req["testScore"] == 100 and req["method"] == "TEST"
    assert req["aiScore"] is not None and req["aiSummary"] and req["aiModel"]

    if skill["skillCategory"] == "AI Advanced Skill":
        for role in ("Instructor", "CareerCenter"):
            r = client.post(f"/admin/skill-requests/{req['id']}/attest", json={"role": role})
            assert r.status_code == 200, r.text
    approved = client.post(f"/admin/skill-requests/{req['id']}/approve", json={}).json()
    assert approved["status"] == "APPROVED" and approved["recordSyncStatus"] == "NOT SYNCED"
    rec = next(r for r in client.get("/records").json() if r["recordId"] == approved["recordId"])
    assert rec["skillId"] == skill["skillId"] and rec["passportId"] == "BTU-AI-000125"

    result = client.post("/sync").json()
    assert {"passportId": "BTU-AI-000125",
            "newVersion": len(before["versions"]) + 1} in result["passportsUpdated"]
    after = client.get("/passports/BTU-AI-000125").json()
    assert after["passportId"] == "BTU-AI-000125"
    assert skill["skillId"] in {s["skillId"] for s in after["versions"][-1]["skills"]}
    mine = client.get("/me/skill-requests", headers=auth()).json()
    assert mine[0]["recordSyncStatus"] == "SYNCED"


def test_duplicate_rules():
    skill, _ = submit_passing_test()
    again = client.post("/skill-requests/test", headers=auth(),
                        json={"skillId": skill["skillId"], "answers": correct_answers(skill)})
    assert again.status_code == 400  # already pending
    owned = client.get("/me/passport", headers=auth()).json()["versions"][0]["skills"][0]
    r = client.post("/skill-requests/test", headers=auth(),
                    json={"skillId": owned["skillId"],
                          "answers": correct_answers({"skillCategory": owned["skillCategory"]})})
    assert r.status_code == 400 and "already on your passport" in r.json()["detail"]


def test_proof_upload_hash_and_reject():
    skill = pick_new_skill()
    r = client.post("/skill-requests/proof", headers=auth(),
                    data={"skillId": skill["skillId"], "description": "Course certificate"},
                    files={"file": ("cert.pdf", b"%PDF-fake-certificate", "application/pdf")})
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["method"] == "PROOF" and len(req["evidenceHash"]) == 64
    rejected = client.post(f"/admin/skill-requests/{req['id']}/reject",
                           json={"note": "Certificate does not show the skill name"}).json()
    assert rejected["status"] == "REJECTED"
    assert rejected["adminNote"].startswith("Certificate does not")
    # rejected request creates no sheet record
    assert all(x["skillId"] != skill["skillId"] or x["passportId"] != "BTU-AI-000125"
               for x in client.get("/records").json() if x["syncStatus"] == "NOT SYNCED"
               and x["recordId"] >= "REC-0061")


def test_requests_require_student_auth():
    assert client.get("/me/skill-requests").status_code == 401
    assert client.post("/skill-requests/test", json={"skillId": "SKL-001", "answers": {}}).status_code == 401
