"""API 끝-끝 테스트 (MOCK 모드). FastAPI 가 설치돼 있어야 실행된다."""
import io
import json
import os

os.environ["MOCK"] = "true"
os.environ["MATCH_API_URL"] = ""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services import auth

client = TestClient(app)


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (200, 200, 200)).save(buf, format="JPEG")
    return buf.getvalue()


def _login(local="apitest01") -> dict:
    auth.gate._pending.clear()
    r = client.post("/auth/request-code", json={"email": local})
    assert r.status_code == 200, r.text
    email = r.json()["email"]
    code = auth.gate._pending[email].code
    r = client.post("/auth/verify", json={"email": email, "code": code})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_full_found_flow():
    h = _login()
    assert client.get("/found").status_code == 401
    assert client.patch("/me", json={"name": "홍길동", "department": "AI융합학부"}, headers=h).json()["name"] == "홍길동"

    attrs = client.post("/found/analyze", files={"image": ("a.jpg", _jpeg(), "image/jpeg")}, headers=h).json()["attributes"]
    assert "형남공학관" in client.get("/buildings").json()
    lockers = client.get("/lockers", params={"building": "중앙도서관"}).json()
    assert lockers[0]["building"] == "중앙도서관" and lockers[0]["same_building"] is True

    data = {"attributes": attrs, "building": "형남공학관", "location_detail": "3층",
            "found_at": "2026-10-29T14:00:00+09:00", "locker_id": lockers[-1]["id"], "mask_boxes": []}
    r = client.post("/found", files={"image": ("a.jpg", _jpeg(), "image/jpeg")},
                    data={"data": json.dumps(data)}, headers=h)
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    assert client.get(f"/found/{fid}", headers=h).json()["attrs"]["color"] == attrs["color"]
    assert len(client.get("/me/found", headers=h).json()) == 1
    assert client.get(r.json()["photo_url"]).status_code == 200


def test_lost_report_edit_close():
    h = _login("apitest02")
    body = {"category": "이어폰", "brand": "Apple", "color": "검정", "buildings": ["형남공학관", "중앙도서관"],
            "lost_from": "2026-10-29T12:00:00+09:00", "lost_to": "2026-10-29T15:00:00+09:00"}
    r = client.post("/lost", json=body, headers=h)
    assert r.status_code == 201, r.text
    lid = r.json()["id"]
    assert r.json()["match"] is None                         # 매칭 서버 미설정
    assert client.post("/lost", json={**body, "category": "가방"}, headers=h).status_code == 422

    r = client.patch(f"/lost/{lid}", json={"color": "흰색", "description": "이니셜 각인"}, headers=h)
    assert r.status_code == 200 and r.json()["attrs"]["color"] == "흰색"
    assert client.post(f"/lost/{lid}/close", headers=h).json()["status"] == "closed"
    assert client.patch(f"/lost/{lid}", json={"color": "검정"}, headers=h).status_code == 409

    other = _login("apitest03")
    assert client.get(f"/lost/{lid}", headers=other).status_code == 404   # 남의 신고는 안 보임


def test_summary_filters_and_delete():
    h = _login("apitest04")
    s = client.get("/me/summary", headers=h).json()
    assert s == {"lost_count": 0, "lost_open_count": 0, "found_count": 0, "returned_count": 0, "received_count": 0}
    r = client.get("/found", params={"q": "에어팟", "color": "흰색", "date_from": "2026-01-01T00:00:00+09:00"},
                   headers=h)
    assert r.status_code == 200
    assert client.get("/me/lost", params={"tab": "open"}, headers=h).status_code == 200
    assert client.delete("/me", headers=h).json() == {"ok": True}
