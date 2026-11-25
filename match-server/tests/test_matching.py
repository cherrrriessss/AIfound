"""키 없이 돌아가는 테스트. 실행: pytest -q
Gemini, Supabase, FCM 은 가짜(Fake)로 바꿔서 매칭 흐름만 검증합니다."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app import pipeline
from app.alerts import should_push
from app.rerank import Judgement
from app.scoring import attr_ratio, item_name, place_ratio, time_ratio, total_score
from app.sentence import attrs_to_sentence

KST = ZoneInfo("Asia/Seoul")
NOON = datetime(2026, 10, 29, 12, 0, tzinfo=KST)       # 16 화면 예시: 10/29 12:00~15:00


# ---------------- 문장 / 이름 ----------------
def test_sentence_and_name():
    attrs = {"category": "이어폰", "brand": "Apple", "model": "에어팟 프로", "color": "검정",
             "features": ["스티커 부착", "케이스 스크래치"]}
    assert attrs_to_sentence(attrs) == "검정 Apple 에어팟 프로 이어폰. 특징: 스티커 부착, 케이스 스크래치"
    assert item_name(attrs) == "검정 에어팟 프로"
    assert item_name({"category": "지갑", "brand": "확인 불가", "color": "검정"}) == "검정 지갑"


# ---------------- 점수 ----------------
def test_attr_unknown_brand_is_skipped():
    r, keys = attr_ratio({"category": "지갑", "brand": "확인 불가", "color": "검정"},
                         {"category": "지갑", "brand": "MCM", "color": "검정"})
    assert r == 1.0 and keys == ["category", "color"]


def test_place_multi_buildings():
    assert place_ratio("형남공학관", ["중앙도서관", "형남공학관"]) == 1.0      # 여러 곳 중 하나 일치
    assert place_ratio("형남공학관", ["중앙도서관"]) == 0.5                # 가까운 건물
    assert place_ratio("형남공학관", ["베어드홀"]) == 0.0


def test_time_window():
    f, t = NOON, NOON + timedelta(hours=3)
    assert time_ratio(f, t, NOON + timedelta(hours=2)) == 1.0       # 시간대 안에서 주움
    assert time_ratio(f, t, NOON - timedelta(hours=3)) == 0.0       # 잃어버리기 전
    assert 0.9 < time_ratio(f, t, t + timedelta(hours=5)) < 1.0
    assert time_ratio(f, t, t + timedelta(days=4)) == 0.0


def test_breakdown_sums_to_score():
    found = {"attrs": {"category": "이어폰", "brand": "Apple", "model": "에어팟 프로", "color": "검정"},
             "building": "형남공학관", "found_at": NOON + timedelta(hours=2)}
    lost = {"attrs": {"category": "이어폰", "brand": "Apple", "color": "검정"}, "buildings": ["형남공학관", "중앙도서관"],
            "lost_from": NOON, "lost_to": NOON + timedelta(hours=3)}
    d = total_score(found, lost, 0.92)
    assert d.attr + d.semantic + d.place + d.time == d.total          # 19 화면 막대 합 = 일치율
    assert d.place == 20 and d.time == 15 and d.attr == 40


# ---------------- 알림 설정 ----------------
def test_quiet_hours_and_toggle():
    s = {"match_alert": True, "quiet_start": "23:00", "quiet_end": "08:00"}
    assert should_push(s, datetime(2026, 10, 29, 23, 30, tzinfo=KST)) is False
    assert should_push(s, datetime(2026, 10, 30, 7, 59, tzinfo=KST)) is False
    assert should_push(s, datetime(2026, 10, 30, 8, 0, tzinfo=KST)) is True
    assert should_push({"match_alert": False}, NOON) is False
    assert should_push(None, NOON) is True


# ---------------- 전체 흐름 (가짜 서비스) ----------------
class FakeDB:
    def __init__(self, found=None, losts=(), lost=None, founds=(), settings=None, rejected=()):
        self.found, self.losts, self.lost, self.founds = found, list(losts), lost, list(founds)
        self.settings, self.rejected = settings or {}, set(rejected)
        self.saved, self.notified, self.embedded, self.inbox, self.status = [], [], [], [], []

    def set_match_status(self, fid, s): self.status.append(s)
    def get_found(self, _id): return dict(self.found)
    def get_lost(self, _id): return dict(self.lost)
    def set_embedding(self, table, rid, vec): self.embedded.append((table, rid))
    def search_lost_for_found(self, _id): return [dict(l) for l in self.losts]
    def search_found_for_lost(self, _id): return [dict(f) for f in self.founds]
    def save_match(self, f, l, score, detail, reason, short, ai):
        st = "rejected" if (f, l) in self.rejected else "candidate"
        self.saved.append({"f": f, "l": l, "score": score, "detail": detail, "short": short, "ai": ai})
        return {"id": f"m-{f}-{l}", "status": st, "notified": False}
    def mark_notified(self, mid): self.notified.append(mid)
    def add_notification(self, uid, kind, title, body, data): self.inbox.append((uid, title, body, data))
    def get_settings(self, uid): return self.settings
    def get_tokens(self, uid): return [f"token-{uid}"]
    def delete_token(self, t): pass


class FakeEmbedding:
    @staticmethod
    def embed(text): return [1.0, 0.0]
    @staticmethod
    def to_pgvector(v): return "[1,0]"


class FakeRerank:
    def __init__(self, scores): self.scores, self.calls = scores, 0
    def rerank(self, anchor, cands):
        self.calls += 1
        return {c["id"]: Judgement(candidate_id=c["id"], likelihood=self.scores.get(c["id"], 0),
                                   reason=f"{c['id']} 긴 이유", short_reason=f"{c['id']} 짧은 이유")
                for c in cands}


class FakeNotify:
    def __init__(self): self.sent = []
    def send_match_push(self, token, title, body, data): self.sent.append((token, title, body)); return True


def _patch(monkeypatch, fdb, rerank, fn):
    monkeypatch.setattr(pipeline, "db", fdb)
    monkeypatch.setattr(pipeline, "embedding", FakeEmbedding)
    monkeypatch.setattr(pipeline, "rerank_mod", rerank)
    monkeypatch.setattr(pipeline, "notify", fn)


FOUND = {"id": "F1", "attrs": {"category": "이어폰", "brand": "Apple", "model": "에어팟 프로", "color": "검정"},
         "building": "형남공학관", "location_detail": "3층", "found_at": NOON + timedelta(hours=2), "embedding": None}


def _lost(i, color, buildings, sim, start=NOON):
    return {"id": f"L{i}", "owner_id": f"u{i}", "attrs": {"category": "이어폰", "brand": "Apple", "color": color},
            "buildings": buildings, "lost_from": start, "lost_to": start + timedelta(hours=3), "similarity": sim}


def test_found_flow_top3_threshold_ai_filter(monkeypatch):
    losts = [_lost(1, "검정", ["형남공학관"], 0.93), _lost(2, "검정", ["중앙도서관"], 0.90),
             _lost(3, "검정", ["베어드홀"], 0.88), _lost(4, "검정", ["형남공학관"], 0.86),
             _lost(5, "흰색", ["베어드홀"], 0.55, NOON - timedelta(days=5))]
    fdb, fn = FakeDB(found=FOUND, losts=losts), FakeNotify()
    fr = FakeRerank({"L1": 95, "L2": 80, "L3": 70, "L4": 10, "L5": 5})   # L4는 AI가 다른 물건으로 판단
    _patch(monkeypatch, fdb, fr, fn)

    res = pipeline.run_for_found("F1")
    ids = [r["lost_report_id"] for r in res]

    assert fdb.embedded == [("found_items", "F1")]
    assert fr.calls == 1
    assert fdb.status == ["searching", "notified"]                # 15 화면 진행 상태
    assert len(res) <= 3 and all(r["score"] >= 60 for r in res)
    assert ids[0] == "L1" and "L4" not in ids and "L5" not in ids
    for s in fdb.saved:                                           # 저장된 일치율 = 막대 합
        d = s["detail"]
        assert d["attr"] + d["semantic"] + d["place"] + d["time"] == s["score"]
    title, body = fn.sent[0][1], fn.sent[0][2]
    assert title == "내 분실물과 비슷한 물건이 등록됐어요"
    assert body.startswith("검정 에어팟 프로 · 형남공학관 3층 · 일치율 ") and "L1 짧은 이유" in body
    assert len(fdb.inbox) == len(res)                              # 알림함에도 저장
    print("\n결과:", res, "\n푸시:", body)


def test_quiet_hours_keeps_inbox_but_no_push(monkeypatch):
    fdb = FakeDB(found=FOUND, losts=[_lost(1, "검정", ["형남공학관"], 0.93)],
                 settings={"match_alert": False})
    fn = FakeNotify()
    _patch(monkeypatch, fdb, FakeRerank({"L1": 90}), fn)
    pipeline.run_for_found("F1")
    assert fn.sent == [] and len(fdb.inbox) == 1


def test_rejected_pair_is_not_notified_again(monkeypatch):
    fdb = FakeDB(found=FOUND, losts=[_lost(1, "검정", ["형남공학관"], 0.93)], rejected={("F1", "L1")})
    fn = FakeNotify()
    _patch(monkeypatch, fdb, FakeRerank({"L1": 90}), fn)
    assert pipeline.run_for_found("F1") == [] and fn.sent == []
    assert fdb.status[-1] == "no_match"


def test_rerank_failure_falls_back(monkeypatch):
    fdb, fn = FakeDB(found={**FOUND, "embedding": "[1,0]"}, losts=[_lost(1, "검정", ["형남공학관"], 0.93)]), FakeNotify()

    class Broken:
        @staticmethod
        def rerank(a, c): return {}
    _patch(monkeypatch, fdb, Broken, fn)
    res = pipeline.run_for_found("F1")
    assert fdb.embedded == [] and res
    assert res[0]["reason"].startswith("종류·브랜드·색 일치")


def test_lost_flow_returns_results_without_push(monkeypatch):
    lost = {"id": "L9", "owner_id": "u9", "attrs": {"category": "이어폰", "brand": "Apple", "color": "검정"},
            "buildings": ["형남공학관", "중앙도서관"], "lost_from": NOON, "lost_to": NOON + timedelta(hours=3)}
    founds = [{**FOUND, "id": "F1", "similarity": 0.92},
              {**FOUND, "id": "F2", "attrs": {"category": "이어폰", "color": "흰색"}, "building": "베어드홀",
               "similarity": 0.6}]
    fdb, fn = FakeDB(lost=lost, founds=founds), FakeNotify()
    _patch(monkeypatch, fdb, FakeRerank({"F1": 92, "F2": 20}), fn)
    res = pipeline.run_for_lost("L9")
    assert [r["found_item_id"] for r in res] == ["F1"]            # 17 '비슷한 물건 1건을 찾았어요'
    assert res[0]["name"] == "검정 에어팟 프로" and fn.sent == []


# ---------------- 김준희 서버가 저장하는 형식 그대로 ----------------
def test_teammate_attrs_shape(monkeypatch):
    """server/app/schemas.py 의 to_attrs() 결과 모양:
    습득물 {category, subcategory, brand(None 가능), model, color, features[], title}
    분실 신고 {category, brand, model, color, features[]}"""
    found = {"id": "F7", "embedding": None, "building": "형남공학관", "location_detail": "3층 302호 앞",
             "found_at": NOON + timedelta(hours=1),
             "attrs": {"category": "이어폰", "subcategory": "무선 이어폰", "brand": "Apple", "model": "에어팟 프로",
                       "color": "흰색", "features": ["스티커 부착"], "title": "흰색 Apple 에어팟 프로 케이스"}}
    lost = {"id": "L7", "owner_id": "u7", "buildings": ["형남공학관", "중앙도서관"],
            "lost_from": NOON, "lost_to": NOON + timedelta(hours=3), "similarity": 0.9,
            "attrs": {"category": "이어폰", "brand": None, "model": None, "color": "흰색", "features": []}}
    fdb, fn = FakeDB(found=found, losts=[lost]), FakeNotify()
    _patch(monkeypatch, fdb, FakeRerank({"L7": 88}), fn)
    res = pipeline.run_for_found("F7")
    assert res and res[0]["lost_report_id"] == "L7"
    assert fn.sent[0][2].startswith("흰색 에어팟 프로 · 형남공학관 3층 302호 앞 · 일치율 ")


def test_gita_is_not_a_match():
    """색·종류가 '기타'끼리면 '일치'로 세지 않음."""
    r, keys = attr_ratio({"category": "기타", "color": "기타", "brand": "Monami"},
                         {"category": "기타", "color": "기타", "brand": "모나미"})
    assert keys == [] and r == 0.0
