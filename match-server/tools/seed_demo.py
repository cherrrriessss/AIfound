"""시연용 더미 데이터 만들기 (숭실대 기준).

사용법 (match-server 폴더, 매칭 서버를 다른 터미널에서 켜 둔 상태):
    python tools/seed_demo.py --owner 내학번@soongsil.ac.kr
    python tools/seed_demo.py --owner 내학번@soongsil.ac.kr --finder 팀원학번@soongsil.ac.kr
    python tools/seed_demo.py --reset          # 더미 데이터만 지우기

--owner  : 앱에서 '분실자'로 로그인할 학교 메일. 이 계정에 분실 신고 3건이 생기고,
           그중 2건에 '새 매칭 후보' 알림이 와 있는 상태가 됨.
--finder : (선택) '습득자'로 로그인할 메일. 안 주면 데모 계정(demo-finder@aifound.test)이 습득자.

만드는 것
  - 보관함 4곳 (없을 때만. 앱의 건물 목록도 여기서 나옴. 지우지 않음)
  - 분실자 신고 3건: 흰색 에어팟 프로 2 / 검정 반지갑 / 학생증(아직 후보 없음 -> 시연 때 앱으로 습득물 등록)
  - 다른 학생 신고 2건, 습득물 6건
  - 실제 매칭 서버로 매칭 실행 -> 일치율, AI 이유, 알림까지 진짜로 생성
다시 실행하면 이전 더미 데이터를 지우고 새로 만듦 (attrs.demo = true 인 것만 지움).
"""
import os
import sys
import time
import argparse
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from supabase import create_client

from app import config

BASE = os.getenv("MATCH_URL", "http://localhost:8000")
sb = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
KST = timezone(timedelta(hours=9))

LOCKERS = [
    {"name": "정보과학관 1층 행정실", "code": "A-01", "building": "정보과학관",
     "location": "1층 엘리베이터 오른쪽", "hours": "평일 09:00-18:00"},
    {"name": "형남공학관 1층 행정실", "code": None, "building": "형남공학관",
     "location": "정문 들어와서 오른쪽", "hours": "평일 09:00-18:00"},
    {"name": "중앙도서관 1층 안내데스크", "code": "B-03", "building": "중앙도서관",
     "location": "정문 출입 후 오른쪽 안내데스크", "hours": "매일 09:00-22:00"},
    {"name": "학생회관 분실물 센터", "code": None, "building": "학생회관",
     "location": "1층 학생지원팀 옆", "hours": "평일 10:00-17:00"},
]


_now = datetime.now(KST)
# 오후 4시 전에 실행하면 '오늘' 시각이 미래가 될 수 있어서 하루 앞당김
_base = _now if _now.hour >= 16 else _now - timedelta(days=1)


def at(days_ago: int, hour: int, minute: int = 0) -> str:
    d = _base.replace(hour=hour, minute=minute, second=0, microsecond=0) - timedelta(days=days_ago)
    return d.isoformat()


def A(category, brand, model, color, *features):
    return {"category": category, "brand": brand, "model": model, "color": color,
            "features": list(features), "demo": True}


# ---------- 계정 ----------
def find_user(email):
    page = 1
    while True:
        users = sb.auth.admin.list_users(page=page, per_page=200)
        for u in users:
            if (u.email or "").lower() == email.lower():
                return u.id
        if len(users) < 200:
            return None
        page += 1


def ensure_user(email):
    uid = find_user(email)
    if uid:
        return uid, False
    u = sb.auth.admin.create_user({"email": email, "email_confirm": True})
    return u.user.id, True


# ---------- 정리 ----------
def reset():
    lost_ids = [r["id"] for r in sb.table("lost_reports").select("id").eq("attrs->>demo", "true").execute().data]
    found_ids = [r["id"] for r in sb.table("found_items").select("id").eq("attrs->>demo", "true").execute().data]
    match_ids = []
    if found_ids:
        match_ids += [r["id"] for r in sb.table("matches").select("id").in_("found_item_id", found_ids).execute().data]
    if lost_ids:
        match_ids += [r["id"] for r in sb.table("matches").select("id").in_("lost_report_id", lost_ids).execute().data]
    for key, ids in (("match_id", match_ids), ("lost_report_id", lost_ids), ("found_item_id", found_ids)):
        if ids:
            sb.table("notifications").delete().in_(f"data->>{key}", list(set(ids))).execute()
    if found_ids:
        sb.table("pickups").delete().in_("found_item_id", found_ids).execute()
        sb.table("found_items").delete().in_("id", found_ids).execute()   # matches 는 cascade
    if lost_ids:
        sb.table("lost_reports").delete().in_("id", lost_ids).execute()
    print(f"🧹 이전 더미 데이터 삭제: 분실 신고 {len(lost_ids)}, 습득물 {len(found_ids)}, 매칭 {len(set(match_ids))}")


def ensure_lockers():
    have = {r["name"]: r["id"] for r in sb.table("lockers").select("id, name").execute().data}
    added = 0
    for lk in LOCKERS:
        if lk["name"] not in have:
            have[lk["name"]] = sb.table("lockers").insert(lk).execute().data[0]["id"]
            added += 1
    print(f"🗄  보관함 {len(LOCKERS)}곳 준비 (새로 추가 {added})")
    return {lk["building"]: have[lk["name"]] for lk in LOCKERS}


# ---------- 매칭 서버 호출 ----------
def internal(path):
    r = httpx.post(BASE + path, headers={"X-Internal-Key": config.INTERNAL_KEY}, timeout=120)
    r.raise_for_status()
    return r.json()


def wait_found(found_id, timeout=90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        row = sb.table("found_items").select("match_status").eq("id", found_id).single().execute().data
        if row["match_status"] in ("notified", "no_match"):
            return row["match_status"]
        time.sleep(1.5)
    return "timeout"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", help="분실자로 로그인할 학교 메일")
    ap.add_argument("--finder", help="습득자로 로그인할 메일 (선택)")
    ap.add_argument("--reset", action="store_true", help="더미 데이터만 지우기")
    a = ap.parse_args()

    try:
        httpx.get(BASE + "/health", timeout=5).raise_for_status()
    except Exception:
        print(f"❌ 매칭 서버({BASE})가 꺼져 있어요. 다른 터미널에서 uvicorn 을 먼저 켜 주세요.")
        return

    reset()
    if a.reset:
        return
    if not a.owner:
        print("❌ --owner 내학번@soongsil.ac.kr 을 같이 적어 주세요.")
        return

    owner, new = ensure_user(a.owner)
    print(f"👤 분실자: {a.owner}" + (" (새 계정 생성)" if new else ""))
    finder, new = ensure_user(a.finder or "demo-finder@aifound.test")
    print(f"👤 습득자: {a.finder or 'demo-finder@aifound.test (데모 계정)'}" + (" (새 계정 생성)" if new else ""))
    other, _ = ensure_user("demo-student@aifound.test")
    finder2, _ = ensure_user("demo-finder2@aifound.test")
    locker = ensure_lockers()

    # ---------- 분실 신고 ----------
    lost_rows = [
        dict(owner_id=owner, category="이어폰",
             attrs=A("이어폰", "Apple", "에어팟 프로 2", "흰색", "케이스에 곰돌이 스티커", "왼쪽 유닛 살짝 긁힘"),
             description="흰색 에어팟 프로 2, 케이스 뒷면에 곰돌이 스티커가 있어요",
             buildings=["정보과학관"], lost_from=at(0, 9), lost_to=at(0, 12)),
        dict(owner_id=owner, category="지갑",
             attrs=A("지갑", "닥스", "반지갑", "검정", "가죽", "안에 교통카드와 학생증"),
             description="검정 가죽 반지갑, 안에 교통카드랑 학생증이 있어요",
             buildings=["중앙도서관", "학생회관"], lost_from=at(1, 13), lost_to=at(1, 18)),
        dict(owner_id=owner, category="학생증·카드",
             attrs=A("학생증·카드", "숭실대학교", "모바일 겸용 학생증", "파랑", "투명 카드케이스에 들어 있음"),
             description="파란 숭실대 학생증, 투명 카드케이스",
             buildings=["형남공학관"], lost_from=at(0, 10), lost_to=at(0, 14)),
        dict(owner_id=other, category="이어폰",
             attrs=A("이어폰", "삼성", "갤럭시 버즈2 프로", "보라", "실리콘 케이스"),
             description="보라색 갤럭시 버즈2 프로", buildings=["학생회관"],
             lost_from=at(0, 11), lost_to=at(0, 13)),
        dict(owner_id=other, category="기타",
             attrs=A("기타", "확인불가", "장우산", "남색", "나무 손잡이"),
             description="남색 장우산, 나무 손잡이", buildings=["정보과학관"],
             lost_from=at(2, 9), lost_to=at(2, 18)),
    ]
    lost_ids = []
    print("\n📝 분실 신고 등록 + 임베딩")
    for row in lost_rows:
        lid = sb.table("lost_reports").insert(row).execute().data[0]["id"]
        internal(f"/internal/match/lost/{lid}")
        lost_ids.append(lid)
        print(f"   - {row['attrs']['color']} {row['attrs']['model']} ({', '.join(row['buildings'])})")

    # ---------- 습득물 ----------
    found_rows = [
        dict(finder_id=finder, category="이어폰",
             attrs=A("이어폰", "Apple", "에어팟 프로 2", "흰색", "케이스에 스티커"),
             description="케이스에 곰 모양 스티커가 붙은 흰색 에어팟",
             building="정보과학관", location_detail="3층 열람실 창가 책상", found_at=at(0, 11, 20),
             locker_id=locker["정보과학관"]),
        dict(finder_id=finder2, category="이어폰",
             attrs=A("이어폰", "Apple", "에어팟 프로", "검정", "실리콘 케이스"),
             description="검정 실리콘 케이스에 든 에어팟 프로",
             building="정보과학관", location_detail="1층 로비 소파", found_at=at(0, 12, 40),
             locker_id=locker["정보과학관"]),
        dict(finder_id=finder, category="지갑",
             attrs=A("지갑", "닥스", "반지갑", "검정", "가죽", "교통카드 들어 있음"),
             description="검정 가죽 반지갑. 개인정보는 가렸어요",
             building="중앙도서관", location_detail="2층 노트북 열람실", found_at=at(1, 17, 10),
             locker_id=locker["중앙도서관"]),
        dict(finder_id=finder2, category="이어폰",
             attrs=A("이어폰", "삼성", "갤럭시 버즈2 프로", "보라", "케이스 없음"),
             description="보라색 버즈, 케이스는 없어요",
             building="학생회관", location_detail="2층 식당 앞 테이블", found_at=at(0, 12, 30),
             locker_id=locker["학생회관"]),
        dict(finder_id=finder2, category="휴대폰",
             attrs=A("휴대폰", "Apple", "아이폰 15", "파랑", "투명 젤리 케이스"),
             description="파란 아이폰 15, 화면 잠겨 있음",
             building="형남공학관", location_detail="5층 강의실 501호", found_at=at(0, 15),
             locker_id=locker["형남공학관"]),
        dict(finder_id=finder, category="기타",
             attrs=A("기타", "확인불가", "장우산", "남색", "나무 손잡이"),
             description="남색 장우산",
             building="정보과학관", location_detail="1층 우산꽂이", found_at=at(2, 17),
             locker_id=locker["정보과학관"]),
    ]
    print("\n📦 습득물 등록 -> 매칭 (Gemini 재비교 때문에 건당 5~20초)")
    for row in found_rows:
        fid = sb.table("found_items").insert(row).execute().data[0]["id"]
        internal(f"/internal/match/found/{fid}")
        st = wait_found(fid)
        print(f"   - {row['attrs']['color']} {row['attrs']['model']} @ {row['building']}  ->  {st}")

    # ---------- 결과 ----------
    print("\n📊 분실자 화면에서 보일 것")
    for lid, row in zip(lost_ids[:3], lost_rows[:3]):
        ms = (sb.table("matches").select("score, short_reason").eq("lost_report_id", lid)
              .gte("score", config.NOTIFY_THRESHOLD).order("score", desc=True).execute().data)
        name = f"{row['attrs']['color']} {row['attrs']['model']}"
        if ms:
            print(f"   - {name}: 후보 {len(ms)}개 " + ", ".join(f"{m['score']}%" for m in ms)
                  + f"  \"{ms[0]['short_reason']}\"")
        else:
            print(f"   - {name}: 아직 후보 없음  <- 시연 때 습득자 앱으로 '형남공학관 학생증' 등록")
    n = sb.table("notifications").select("id", count="exact").eq("user_id", owner).eq("read", False).execute().count
    print(f"   - 안 읽은 알림 {n}개")
    print("\n✅ 끝. 앱에서 --owner 메일로 로그인(메일 인증 코드)하면 바로 보여요.")
    print("   다시 처음 상태로 돌리려면 같은 명령을 한 번 더 실행하면 돼요.")


if __name__ == "__main__":
    main()
