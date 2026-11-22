"""핵심 로직 테스트 (FastAPI 없이 실행 가능).  실행: pytest -q"""
import io
import json
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

os.environ["MOCK"] = "true"

import pytest
from PIL import Image

from app.repo import MemoryRepo
from app.schemas import CATEGORIES, FoundCreateIn, ItemAttributes, LostCreateIn
from app.services import auth, found, gemini, images, match_client
from app.services.attributes import pii_warning_text

LOCKER = "00000000-0000-0000-0000-000000000001"


def _jpeg(w=800, h=600, color=(240, 240, 240)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="JPEG")
    return buf.getvalue()


# ---------------- 팀 합의 값 ----------------
def test_categories_are_team_five():
    assert CATEGORIES == ["이어폰", "지갑", "학생증·카드", "휴대폰", "기타"]


# ---------------- 로그인 ----------------
def test_school_email_normalize():
    assert auth.normalize_school_email("20231234", "soongsil.ac.kr") == "20231234@soongsil.ac.kr"
    assert auth.normalize_school_email("A.b@Soongsil.ac.kr", "soongsil.ac.kr") == "a.b@soongsil.ac.kr"
    with pytest.raises(auth.AuthError):
        auth.normalize_school_email("me@gmail.com", "soongsil.ac.kr")
    with pytest.raises(auth.AuthError):
        auth.normalize_school_email("x y", "soongsil.ac.kr")


def test_mock_otp_flow_and_token():
    auth.gate._pending.clear()
    email = auth.request_code("student01")
    code = auth.gate._pending[email].code
    with pytest.raises(auth.AuthError):          # 재전송 대기
        auth.request_code("student01")
    with pytest.raises(auth.AuthError):          # 틀린 코드
        auth.verify_code("student01", "000000" if code != "000000" else "111111")
    res = auth.verify_code("student01", code)
    uid, em = auth.user_from_token(res.access_token)
    assert uid == res.user_id and em == email
    with pytest.raises(auth.AuthError):          # 한 번 쓴 코드는 재사용 불가
        auth.verify_code("student01", code)


def test_otp_expiry_and_attempt_limit():
    g = auth.OtpGate()
    g.issue("a@x", now=1000.0)
    with pytest.raises(auth.AuthError, match="만료"):
        g.verify_local("a@x", "123456", now=1000.0 + 301)
    code = g.issue("b@x", now=0.0)
    for _ in range(5):
        with pytest.raises(auth.AuthError):
            g.verify_local("b@x", "xxxxxx", now=1.0)
    with pytest.raises(auth.AuthError, match="시도 횟수"):
        g.verify_local("b@x", code, now=1.0)


def test_bad_token_rejected():
    with pytest.raises(auth.AuthError):
        auth.user_from_token("not-a-token")


# ---------------- Gemini 결과 정리 ----------------
def test_normalize_fixes_rule_breaks():
    raw = {
        "is_item": True, "title": "검정 가방", "category": "가방",            # 목록 밖 → 기타
        "brand": "확인 불가", "colors": ["black", "검정"],                   # 옛 형식 colors[] 도 처리
        "features": ["카드 몇 장"], "confidence": {"category": 1.4, "brand": 0.1, "color": 0.9},
        "pii_detected": False,
        "pii_regions": [{"type": "name", "box": [500, 100, 400, 300]}, {"type": "x", "box": [1, 2, 3, 4]}],
    }
    a = gemini.normalize(raw)
    assert a.category == "기타" and a.brand is None and a.color == "검정"
    assert a.confidence.category == 1.0
    assert len(a.pii_regions) == 1 and a.pii_regions[0].box == [400, 100, 500, 300]
    assert a.pii_detected is True


def test_attrs_shape_matches_matching_server():
    attrs = gemini.mock_result().to_attrs()
    assert set(attrs) == {"category", "subcategory", "brand", "model", "color", "features", "title"}
    assert attrs["color"] == "흰색" and attrs["category"] == "이어폰"


def test_pii_warning_text():
    a = gemini.mock_result()
    assert pii_warning_text(a) is None
    a = ItemAttributes.model_validate({**a.model_dump(), "pii_detected": True, "pii_regions": [
        {"type": "name", "box": [0, 0, 10, 10]}, {"type": "face", "box": [0, 0, 10, 10]}]})
    assert pii_warning_text(a) == "개인정보(이름·얼굴 사진)가 감지됐어요. 가린 뒤에 등록돼요."


# ---------------- 사진 ----------------
def test_image_validation_and_exif_strip():
    with pytest.raises(images.ImageError):
        images.load_image(b"hello", 10_000_000)
    with pytest.raises(images.ImageError):
        images.load_image(_jpeg(), 10)
    img = images.shrink(images.load_image(_jpeg(4000, 3000), 10_000_000), 1600)
    assert max(img.size) == 1600
    out = Image.open(io.BytesIO(images.to_jpeg(img)))
    assert not out.getexif()


def test_mask_covers_region():
    img = Image.new("RGB", (1000, 1000), (255, 255, 255))
    masked = images.apply_masks(img, [[100, 100, 300, 500]], pad_ratio=0)
    assert masked.getpixel((300, 200)) == (40, 40, 40)
    assert masked.getpixel((800, 800)) == (255, 255, 255)
    assert images.unmasked_regions([[100, 100, 300, 500]], [[90, 90, 310, 510]]) == []
    assert images.unmasked_regions([[100, 100, 300, 500]], [[100, 100, 200, 500]]) != []


# ---------------- 습득물 등록 ----------------
def _create_in(**kw) -> FoundCreateIn:
    base = dict(attributes=gemini.mock_result(), building="형남공학관", location_detail="3층 302호 앞",
                found_at=datetime(2026, 10, 29, 14, 0, tzinfo=timezone.utc), locker_id=LOCKER)
    base.update(kw)
    return FoundCreateIn(**base)


def test_analyze_mock():
    out = found.analyze(_jpeg())
    assert out.attributes.category == "이어폰" and out.pii_warning is None


def test_register_saves_team_schema_row():
    repo = MemoryRepo()
    row = found.register(repo, "user-1", _jpeg(), _create_in(description="케이스에 고양이 스티커"))
    # 주희선 schema.sql 의 found_items 컬럼 이름 그대로
    for col in ("finder_id", "category", "attrs", "description", "building", "location_detail",
                "found_at", "locker_id", "photo_path", "status", "match_status"):
        assert col in row
    assert row["status"] == "stored" and row["match_status"] == "pending"
    assert row["photo_path"].startswith("found/") and row["photo_path"] in repo.photos
    assert row["attrs"]["title"] == "흰색 Apple 에어팟 프로 케이스"
    out = found.to_found_out(repo, row)
    assert out.locker.name == "형남공학관 1층 행정실" and out.title.startswith("흰색")
    rows, total = repo.list_found(category="이어폰", building="형남공학관", status="stored",
                                  finder_id=None, offset=0, limit=10)
    assert total == 1


def test_register_blocks_unmasked_pii():
    repo = MemoryRepo()
    attrs = ItemAttributes.model_validate({**gemini.mock_result().model_dump(), "pii_detected": True,
                                           "pii_regions": [{"type": "student_id", "box": [100, 100, 200, 400]}]})
    with pytest.raises(found.FoundError, match="가리지 않은"):
        found.register(repo, "u", _jpeg(), _create_in(attributes=attrs))
    row = found.register(repo, "u", _jpeg(), _create_in(attributes=attrs, mask_boxes=[{"box": [100, 100, 200, 400]}]))
    assert row["photo_path"]


def test_register_rejects_unknown_locker():
    with pytest.raises(found.FoundError):
        found.register(MemoryRepo(), "u", _jpeg(), _create_in(locker_id="nope"))


def test_lost_attrs_shape():
    body = LostCreateIn(category="이어폰", brand="Apple", color="검정", buildings=["형남공학관"],
                        lost_from=datetime(2026, 10, 29, 12, tzinfo=timezone.utc),
                        lost_to=datetime(2026, 10, 29, 15, tzinfo=timezone.utc))
    assert body.to_attrs() == {"category": "이어폰", "brand": "Apple", "model": None, "color": "검정", "features": []}


# ---------------- 매칭 서버 호출 ----------------
class _FakeMatch(BaseHTTPRequestHandler):
    seen: list = []

    def do_POST(self):  # noqa: N802
        _FakeMatch.seen.append((self.path, self.headers.get("X-Internal-Key")))
        body = json.dumps({"count": 1, "matches": [{"score": 88}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def test_match_client_calls_internal_api(monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), _FakeMatch)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(match_client, "settings", type("S", (), {
            "match_api_url": f"http://127.0.0.1:{srv.server_port}", "internal_key": "k123"})())
        monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
        monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
        assert match_client.match_lost("abc")["count"] == 1
        match_client.match_found("f1")
        assert _FakeMatch.seen == [("/internal/match/lost/abc", "k123"), ("/internal/match/found/f1", "k123")]
    finally:
        srv.shutdown()


def test_match_client_skips_without_url(monkeypatch):
    monkeypatch.setattr(match_client, "settings", type("S", (), {"match_api_url": "", "internal_key": ""})())
    assert match_client.match_found("x") is None


# ---------------- S07 검색·필터 ----------------
def test_found_search_and_filters():
    repo = MemoryRepo()
    black = ItemAttributes.model_validate({**gemini.mock_result().model_dump(), "title": "검정 가죽 지갑",
                                           "category": "지갑", "brand": None, "model": None, "color": "검정"})
    found.register(repo, "u", _jpeg(), _create_in())                                   # 흰색 에어팟 10/29
    found.register(repo, "u", _jpeg(), _create_in(attributes=black, building="중앙도서관",
                                                  found_at=datetime(2026, 11, 5, 9, tzinfo=timezone.utc)))
    lf = lambda **kw: repo.list_found(category=None, building=None, status="stored", finder_id=None,
                                      offset=0, limit=10, **kw)[1]
    assert lf() == 2
    assert lf(color="검정") == 1
    assert lf(q="에어팟") == 1 and lf(q="apple") == 1 and lf(q="가죽") == 1
    assert lf(date_from=datetime(2026, 11, 1, tzinfo=timezone.utc)) == 1
    assert lf(date_to=datetime(2026, 11, 1, tzinfo=timezone.utc)) == 1
    assert lf(q="(,%*)") == 2          # 특수문자만 있으면 검색어 없음으로 처리


# ---------------- S23·S24·S22 상태 ----------------
from app.services.status import build_summary, found_display, lost_stage  # noqa: E402


def _lost(repo, owner="u"):
    return repo.insert_lost({"owner_id": owner, "category": "이어폰", "attrs": {}, "buildings": ["형남공학관"],
                             "lost_from": datetime(2026, 10, 29, 12, tzinfo=timezone.utc),
                             "lost_to": datetime(2026, 10, 29, 15, tzinfo=timezone.utc)})


def test_lost_stage_progression():
    repo = MemoryRepo()
    lost = _lost(repo)
    assert lost_stage(lost, repo.matches) == ("waiting", 0)
    repo.matches += [{"lost_report_id": lost["id"], "found_item_id": "f1", "status": "candidate"},
                     {"lost_report_id": lost["id"], "found_item_id": "f2", "status": "candidate"},
                     {"lost_report_id": lost["id"], "found_item_id": "f3", "status": "rejected"}]
    assert lost_stage(lost, repo.matches) == ("candidates", 2)          # '후보 2건'
    repo.matches[0]["status"] = "claimed"
    assert lost_stage(lost, repo.matches)[0] == "claimed"               # 수령 대기
    repo.matches[0]["status"] = "received"
    assert lost_stage(lost, repo.matches)[0] == "received"              # 수령 완료
    other = _lost(repo)
    other["status"] = "closed"
    assert lost_stage(other, repo.matches)[0] == "closed"               # '찾았어요'로 종료


def test_found_display_and_summary():
    repo = MemoryRepo()
    a = found.register(repo, "me", _jpeg(), _create_in())
    b = found.register(repo, "me", _jpeg(), _create_in())
    c = found.register(repo, "me", _jpeg(), _create_in())
    repo.matches.append({"lost_report_id": "x", "found_item_id": b["id"], "status": "claimed"})
    c["status"] = "returned"
    assert found_display(a, repo.matches) == "stored"
    assert found_display(b, repo.matches) == "owner_confirmed"
    assert found_display(c, repo.matches) == "returned"
    assert found.to_found_out(repo, b).display_label == "주인 확인됨"

    _lost(repo, "me")
    closed = _lost(repo, "me")
    closed["status"] = "closed"
    s = build_summary(repo, "me")
    assert (s.lost_count, s.lost_open_count, s.found_count, s.returned_count) == (2, 1, 3, 1)


# ---------------- S28 회원 탈퇴 ----------------
def test_delete_account_keeps_found_items():
    repo = MemoryRepo()
    repo.ensure_profile("me", "me@soongsil.ac.kr")
    f = found.register(repo, "me", _jpeg(), _create_in())
    lost = _lost(repo, "me")
    keep = _lost(repo, "other")
    repo.matches += [{"lost_report_id": lost["id"], "found_item_id": "z", "status": "candidate"},
                     {"lost_report_id": keep["id"], "found_item_id": f["id"], "status": "candidate"}]
    repo.pickups += [{"receiver_id": "me", "finder_id": "x"}, {"receiver_id": "y", "finder_id": "me"}]
    repo.delete_account("me")
    assert repo.get_profile("me") is None and repo.list_lost("me") == []
    assert repo.get_found(f["id"])["finder_id"] is None                  # 물건은 남고 등록자만 비움
    assert repo.get_lost(keep["id"]) is not None                         # 남의 신고는 그대로
    assert [m["lost_report_id"] for m in repo.matches] == [keep["id"]]
    assert repo.pickups == [{"receiver_id": "y", "finder_id": None}]


# ---------------- 정확도 측정 도구 ----------------
def test_eval_brand_rule_and_summary():
    from tools.eval_attributes import brand_ok, summarize
    assert brand_ok("Apple", "apple") and brand_ok("Samsung", "Samsung Galaxy") and brand_ok("", None)
    assert not brand_ok("", "Apple") and not brand_ok("Apple", None)
    rows = [dict(error="", seconds=1.0, exp_pii=1, ok_category=1, ok_color=1, ok_brand=1, ok_all3=1, ok_pii=1),
            dict(error="", seconds=3.0, exp_pii=0, ok_category=1, ok_color=0, ok_brand=1, ok_all3=0, ok_pii=0),
            dict(error="파일 없음", seconds=0, exp_pii=0, ok_category=0, ok_color=0, ok_brand=0, ok_all3=0, ok_pii=0)]
    s = summarize(rows)
    assert (s["evaluated"], s["errors"], s["category"], s["color"], s["pii_recall"], s["pii_specificity"]) == \
           (2, 1, 100.0, 50.0, 100.0, 0.0)
    assert s["avg_seconds"] == 2.0


# ---------------- 설정 진단 ----------------
def test_real_mode_without_gemini_key_errors(monkeypatch):
    monkeypatch.setattr(gemini, "settings", type("S", (), {"mock": False, "gemini_api_key": "", "mock_pii": False,
                                                            "gemini_model": "x"})())
    with pytest.raises(gemini.GeminiError, match="GEMINI_API_KEY"):
        gemini.extract_attributes(b"")


def test_supabase_key_kind():
    import base64 as b64
    from app.diagnostics import supabase_key_kind
    jwt_of = lambda role: "x." + b64.urlsafe_b64encode(json.dumps({"role": role}).encode()).decode().rstrip("=") + ".y"
    assert "정상" in supabase_key_kind("sb_secret_abc")
    assert "앱용" in supabase_key_kind("sb_publishable_abc")
    assert "정상" in supabase_key_kind(jwt_of("service_role"))
    assert "앱용" in supabase_key_kind(jwt_of("anon"))
    assert supabase_key_kind("") == "없음"
