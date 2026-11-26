"""수령 절차, 상태 알림, 건물 거리 테스트 (키 없이 실행)."""
from datetime import datetime, timedelta, timezone

from app import pickup, pipeline
from app.alerts import should_push

NOW = datetime(2026, 10, 30, 3, 0, tzinfo=timezone.utc)   # 한국 12:00


# ---------------- 수령 코드 ----------------
def test_code_rotates_every_10_minutes():
    t = 1_000_000_200.0
    a = pickup.current_code("m1", t)
    assert len(a["code"]) == 6 and a["display"] == f"{a['code'][:3]} {a['code'][3:]}"
    assert pickup.code_matches("m1", a["code"], t + 600)          # 바로 다음 창까지 인정
    assert not pickup.code_matches("m1", a["code"], t + 1200)
    assert not pickup.code_matches("m2", a["code"], t)            # 다른 매칭 코드로는 안 됨
    assert 0 < a["expires_in"] <= 600


# ---------------- 가짜 DB ----------------
class FakeDB:
    def __init__(self):
        self.updates, self.inbox, self.pickups, self.closed = [], [], [], []
        self.found_status, self.lost_status = {}, {}
        self.settings = {}
        self.claimed = []
        self.due = []

    def update_match(self, mid, f): self.updates.append((mid, f))
    def add_notification(self, uid, kind, title, body, data): self.inbox.append((uid, kind, title, body))
    def get_settings(self, uid): return self.settings.get(uid, {})
    def get_tokens(self, uid): return []
    def delete_token(self, t): pass
    def get_staff_lockers(self, uid): return ["LK1"] if uid == "staff" else []
    def list_claimed_for_lockers(self, ids): return self.claimed
    def create_pickup(self, row): self.pickups.append(row); return row
    def set_found_status(self, fid, s): self.found_status[fid] = s
    def set_lost_status(self, lid, s): self.lost_status[lid] = s
    def close_other_matches(self, fid, keep): self.closed.append((fid, keep))
    def list_due_reminders(self, before): return self.due


MATCH = {"id": "m1", "status": "candidate",
         "found_items": {"id": "F1", "finder_id": "finder", "locker_id": "LK1",
                         "attrs": {"category": "지갑", "color": "검정", "brand": "확인 불가"},
                         "lockers": {"name": "중앙도서관 1층 안내데스크"}},
         "lost_reports": {"id": "L1", "owner_id": "owner"}}


def test_claim_notifies_finder(monkeypatch):
    fdb = FakeDB(); monkeypatch.setattr(pipeline, "db", fdb)
    r = pickup.claim(MATCH, NOW)
    assert r["status"] == "claimed" and r["pickup_deadline"].startswith("2026-11-06")
    assert fdb.inbox == [("finder", "owner_found", "주인이 확인했어요",
                          "등록하신 검정 지갑의 주인을 찾았어요. 감사해요!")]


def test_staff_verify_completes_pickup(monkeypatch):
    fdb = FakeDB(); fdb.claimed = [MATCH]; monkeypatch.setattr(pipeline, "db", fdb)
    code = pickup.current_code("m1")["code"]
    assert pickup.verify("student", code) is None                     # 담당자 아니면 불가
    assert pickup.verify("staff", "000000" if code != "000000" else "111111") is None
    rec = pickup.verify("staff", f"AIFOUND:m1:{code}")                # QR 로도 가능
    assert rec["receiver_id"] == "owner" and rec["verified_by"] == "staff"
    assert ("m1", {"status": "received"}) in fdb.updates
    assert fdb.found_status == {"F1": "returned"} and fdb.lost_status == {"L1": "closed"}
    assert fdb.closed == [("F1", "m1")]
    assert {(u, t) for u, k, t, b in fdb.inbox} == {("finder", "수령 완료"), ("owner", "수령 완료")}


def test_reminders_respect_setting(monkeypatch):
    fdb = FakeDB(); fdb.due = [MATCH]; monkeypatch.setattr(pipeline, "db", fdb)
    assert pickup.send_reminders(NOW) == 1
    assert fdb.inbox[0][2] == "수령 기한이 하루 남았어요" and "중앙도서관 1층 안내데스크" in fdb.inbox[0][3]
    assert ("m1", {"reminded": True}) in fdb.updates
    # 리마인드는 기본 OFF -> 알림함엔 남지만 푸시는 켠 사람만
    assert should_push({}, kind="reminder") is False
    assert should_push({"pickup_reminder": True}, NOW, kind="reminder") is True
    assert should_push({"owner_alert": False}, NOW, kind="owner_found") is False


def test_without_coords_only_same_building_counts(monkeypatch):
    from app import config
    from app.scoring import place_ratio
    monkeypatch.setattr(config, "BUILDING_COORDS", {})
    assert place_ratio("형남공학관", ["형남공학관"]) == 1.0
    assert place_ratio("형남공학관", ["중앙도서관"]) == 0.0


# ---------------- 08 '내 물건이에요' 바로 수령 요청 (매칭 없이) ----------------
class DirectDB(FakeDB):
    def __init__(self, existing=None):
        super().__init__()
        self.existing, self.lost_rows, self.match_rows = existing, [], []

    def find_owner_match_for_found(self, fid, uid): return self.existing

    def create_lost_report(self, row):
        row = {**row, "id": "L-direct"}; self.lost_rows.append(row); return row

    def create_match(self, row):
        row = {**row, "id": "m-direct", "status": "candidate"}; self.match_rows.append(row); return row

    def get_match_for_owner(self, mid, uid):
        return {"id": mid, "status": "candidate", "found_items": FOUND,
                "lost_reports": {"id": "L-direct", "owner_id": uid}}


FOUND = {"id": "F1", "finder_id": "finder", "category": "지갑", "building": "중앙도서관",
         "found_at": NOW, "status": "stored", "attrs": {"category": "지갑", "color": "검정"}}


def test_direct_claim_without_match(monkeypatch):
    fdb = DirectDB(); monkeypatch.setattr(pipeline, "db", fdb)
    r = pickup.direct_claim(FOUND, "owner", NOW)
    assert r["match_id"] == "m-direct" and r["status"] == "claimed" and r["direct"] is True
    lost = fdb.lost_rows[0]
    assert lost["owner_id"] == "owner" and lost["buildings"] == ["중앙도서관"]
    assert lost["attrs"]["direct_claim"] is True and lost["category"] == "지갑"
    assert fdb.match_rows[0]["score"] == 0 and fdb.match_rows[0]["detail"] == {"direct": True}
    assert ("m-direct", {"status": "claimed", "claimed_at": NOW.isoformat(),
                         "pickup_deadline": (NOW + timedelta(days=7)).isoformat()}) in fdb.updates
    assert fdb.inbox[0][:3] == ("finder", "owner_found", "주인이 확인했어요")


def test_direct_claim_reuses_existing_match(monkeypatch):
    fdb = DirectDB(existing=MATCH); monkeypatch.setattr(pipeline, "db", fdb)
    r = pickup.direct_claim(FOUND, "owner", NOW)
    assert r["match_id"] == "m1" and r["direct"] is False and fdb.lost_rows == []


def test_direct_claim_already_claimed(monkeypatch):
    fdb = DirectDB(existing={**MATCH, "status": "claimed", "pickup_deadline": "2026-11-06"})
    monkeypatch.setattr(pipeline, "db", fdb)
    r = pickup.direct_claim(FOUND, "owner", NOW)
    assert r == {"match_id": "m1", "status": "claimed", "pickup_deadline": "2026-11-06", "direct": False}
    assert fdb.updates == []


# ---------- 푸시: 키 파일이 없거나 일시 오류여도 토큰을 지우지 않음 ----------
class TokenDB:
    def __init__(self):
        self.deleted, self.saved = [], []

    def add_notification(self, *a): self.saved.append(a)
    def get_settings(self, user_id): return None
    def get_tokens(self, user_id): return ["tok-ok", "tok-expired", "tok-later"]
    def delete_token(self, token): self.deleted.append(token)


def test_notify_only_deletes_expired_tokens(monkeypatch):
    from app import pipeline

    fake = TokenDB()
    results = {"tok-ok": True, "tok-expired": False, "tok-later": None}

    class N:
        @staticmethod
        def send_match_push(token, *a): return results[token]

    monkeypatch.setattr(pipeline, "db", fake)
    monkeypatch.setattr(pipeline, "notify", N)
    monkeypatch.setattr(pipeline.alerts, "should_push", lambda *a, **k: True)
    assert pipeline.notify_user("u1", "match", "t", "b", {"type": "match"}) is True
    assert fake.deleted == ["tok-expired"]
    assert len(fake.saved) == 1


def test_push_skipped_without_credentials(monkeypatch):
    from app import notify

    monkeypatch.setattr(notify.config, "FIREBASE_CREDENTIALS", "/no/such/file.json")
    assert notify.send_match_push("tok", "t", "b", {}) is None
