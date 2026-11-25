"""실제 Supabase + Gemini + 켜져 있는 매칭 서버(8000)로 전체 기능을 한 번에 점검.

사용법 (match-server 폴더, 서버를 다른 터미널에서 켜 둔 상태):
    python tools/e2e_check.py          # 점검 후 테스트 데이터 삭제
    python tools/e2e_check.py --keep   # 테스트 데이터 남겨 두기 (/docs 로 직접 눌러 보고 싶을 때)

하는 일
  0) 테이블이 다 있는지
  1) 테스트 계정 3개(분실자 / 습득자 / 행정실 담당) + 테스트 보관함 생성
  2) 분실 신고(에어팟 프로 2, 흰색, 정보과학관) -> 임베딩
  3) 비슷한 습득물 등록 -> 매칭 -> 분실자 알림
  4) 분실자 후보 목록 -> 일치율, AI 이유
  5) 앱 화면 API: 요약, 후보 목록, 상세, 알림, 알림 설정
  6) '내 물건이에요' -> 수령 안내 -> 수령 코드 -> 행정실 확인 -> 수령 기록
  7) 정리
비밀번호·키는 화면에 출력하지 않음.
"""
import os
import sys
import time
import secrets
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from supabase import create_client

from app import config

BASE = os.getenv("MATCH_URL", "http://localhost:8000")
KEEP = "--keep" in sys.argv
OK, FAIL = "✅", "❌"
results = []


def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(f"{OK if cond else FAIL} {name}" + (f"  — {info}" if info else ""))
    return cond


def admin():
    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)


sb = admin()
tag = secrets.token_hex(3)
created = {"users": [], "lost": None, "found": None, "locker": None}


def make_user(role):
    email = f"e2e-{role}-{tag}@aifound.test"
    pw = secrets.token_urlsafe(16)
    u = sb.auth.admin.create_user({"email": email, "password": pw, "email_confirm": True})
    created["users"].append(u.user.id)
    s = admin().auth.sign_in_with_password({"email": email, "password": pw})
    return u.user.id, s.session.access_token


def call(method, path, token=None, internal=False, **kw):
    h = {}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if internal:
        h["X-Internal-Key"] = config.INTERNAL_KEY
    r = httpx.request(method, BASE + path, headers=h, timeout=90, **kw)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text


def cleanup():
    if KEEP:
        print("\n(--keep) 테스트 데이터를 남겨 뒀어요. 계정 태그:", tag)
        return
    try:
        if created["found"]:
            sb.table("pickups").delete().eq("found_item_id", created["found"]).execute()
            sb.table("matches").delete().eq("found_item_id", created["found"]).execute()
            sb.table("found_items").delete().eq("id", created["found"]).execute()
        if created["lost"]:
            sb.table("lost_reports").delete().eq("id", created["lost"]).execute()
        for uid in created["users"]:
            sb.table("locker_staff").delete().eq("user_id", uid).execute()
            sb.auth.admin.delete_user(uid)
        if created["locker"]:
            sb.table("lockers").delete().eq("id", created["locker"]).execute()
        print("\n🧹 테스트 데이터 정리 완료")
    except Exception as e:
        print("\n⚠️ 정리 중 오류(직접 지워야 할 수 있음):", e)


def main():
    print(f"=== AIfound 매칭 서버 점검 ({BASE}) ===\n")

    # 0) 서버 / 테이블
    try:
        st, h = call("GET", "/health")
    except Exception as e:
        check("서버 켜짐", False, f"{BASE} 에 연결 안 됨: 다른 터미널에서 uvicorn 을 켜 주세요 ({e})")
        return
    check("서버 켜짐", st == 200, str(h))
    missing = []
    for t in ["lockers", "found_items", "lost_reports", "matches", "locker_staff", "pickups",
              "notifications", "user_settings", "user_devices", "profiles"]:
        try:
            sb.table(t).select("*").limit(1).execute()
        except Exception as e:
            missing.append(f"{t} ({str(e)[:60]})")
    if not check("Supabase 테이블", not missing, "없음: " + ", ".join(missing) if missing else "10개 모두 있음"):
        print("   -> Supabase SQL Editor 에서 server/supabase/schema.sql 을 실행해야 해요.")
        return

    # 1) 계정, 보관함
    owner, owner_tok = make_user("owner")
    finder, finder_tok = make_user("finder")
    staff, staff_tok = make_user("staff")
    check("테스트 계정 3개 + 로그인 토큰", owner_tok and finder_tok and staff_tok)
    locker = sb.table("lockers").insert({"name": f"E2E 테스트 보관함 {tag}", "code": "T-01",
                                         "building": "정보과학관", "location": "1층 행정실 옆",
                                         "hours": "평일 09:00-18:00"}).execute().data[0]
    created["locker"] = locker["id"]
    sb.table("locker_staff").insert({"user_id": staff, "locker_id": locker["id"]}).execute()

    # 2) 분실 신고 먼저 (아직 비슷한 습득물 없음)
    now = datetime.now(timezone.utc)
    lost = sb.table("lost_reports").insert({
        "owner_id": owner, "category": "이어폰",
        "attrs": {"category": "이어폰", "brand": "Apple", "model": "에어팟 프로 2", "color": "흰색",
                  "features": ["케이스에 곰돌이 스티커"]},
        "description": "흰색 에어팟 프로 2, 케이스에 곰돌이 스티커",
        "buildings": ["정보과학관"],
        "lost_from": (now - timedelta(hours=5)).isoformat(),
        "lost_to": (now - timedelta(hours=2)).isoformat(),
    }).execute().data[0]
    created["lost"] = lost["id"]
    st, r = call("POST", f"/internal/match/lost/{lost['id']}", internal=True)
    if not check("분실 신고 등록 + 임베딩", st == 200, f"응답 {st}"):
        print("   ", r)
        return
    row = sb.table("lost_reports").select("embedding").eq("id", lost["id"]).single().execute().data
    check("분실 신고 임베딩 저장됨 (Gemini)", bool(row.get("embedding")))

    # 3) 나중에 누가 비슷한 물건을 주워 등록 -> 습득물 기준 매칭 -> 분실자에게 알림
    found = sb.table("found_items").insert({
        "finder_id": finder, "category": "이어폰",
        "attrs": {"category": "이어폰", "brand": "Apple", "model": "에어팟 프로 2", "color": "흰색",
                  "features": ["스티커 붙어 있음"]},
        "description": "케이스에 스티커가 붙은 흰색 에어팟",
        "building": "정보과학관", "location_detail": "3층 열람실 책상",
        "found_at": (now - timedelta(hours=1)).isoformat(), "locker_id": locker["id"],
    }).execute().data[0]
    created["found"] = found["id"]
    t0 = time.time()
    st, r = call("POST", f"/internal/match/found/{found['id']}", internal=True)
    check("습득물 등록 -> 매칭 시작 (백그라운드)", st == 200, str(r))
    status = None
    for _ in range(45):
        time.sleep(2)
        _, s = call("GET", f"/found-items/{found['id']}/match-status", finder_tok)
        status = s.get("match_status") if isinstance(s, dict) else None
        if status in ("notified", "no_match"):
            break
    check("습득자 화면: 매칭 상태 = notified", status == "notified",
          f"match_status={status}, {time.time()-t0:.1f}초")

    # 4) 분실자가 후보 목록을 다시 열었을 때
    st, r = call("POST", f"/internal/match/lost/{lost['id']}", internal=True)
    mine = [m for m in (r.get("matches", []) if isinstance(r, dict) else []) if m.get("found_item_id") == found["id"]]
    if not check("분실자 후보 목록에 그 습득물이 나옴", mine, f"후보 {r.get('count') if isinstance(r, dict) else r}개"):
        return
    m = mine[0]
    print(f"   일치율 {m.get('score')}%  |  이름: {m.get('name')}\n   이유: {m.get('reason')}")
    check("일치율 60% 이상", (m.get("score") or 0) >= 60)
    match_id = m["match_id"]

    # 5) 앱 화면 API
    st, r = call("GET", "/notifications", owner_tok)
    items = r.get("notifications", r) if isinstance(r, dict) else r
    check("분실자 알림함에 알림 도착", st == 200 and len(items or []) >= 1,
          (items[0].get("title", "") + " / " + items[0].get("body", "").replace("\n", " ")) if items else str(r))
    st, r = call("GET", "/matches/summary", owner_tok)
    check("홈 배너: 안 본 후보 수", st == 200, str(r)[:120])
    st, r = call("GET", f"/lost-reports/{lost['id']}/matches", owner_tok)
    check("후보 목록 화면", st == 200, str(r)[:120])
    st, r = call("GET", f"/matches/{match_id}", owner_tok)
    check("후보 상세 화면", st == 200, str(r)[:120])
    st, _ = call("GET", f"/matches/{match_id}", finder_tok)
    check("다른 사람은 남의 후보를 못 봄", st == 404, f"응답 {st}")
    st, r = call("PUT", "/settings/notifications", owner_tok,
                 json={"match_alert": True, "quiet_start": "23:00", "quiet_end": "08:00"})
    check("알림 설정 저장", st == 200, str(r)[:120])
    st, r = call("POST", "/notifications/read-all", owner_tok)
    check("알림 모두 읽음", st == 200)

    # 6) 수령
    st, r = call("POST", f"/matches/{match_id}/claim", owner_tok)
    check("'내 물건이에요'", st == 200, str(r))
    _, n = call("GET", "/notifications", finder_tok)
    n = n.get("notifications", n) if isinstance(n, dict) else n
    check("습득자에게 '주인이 확인했어요' 알림", any("주인" in (x.get("title") or "") for x in (n or [])))
    st, g = call("GET", f"/matches/{match_id}/pickup", owner_tok)
    check("수령 안내 화면", st == 200, (g.get("steps", [{}])[1].get("locker") or {}).get("name", "") if st == 200 else str(g))
    st, c = call("GET", f"/matches/{match_id}/pickup/code", owner_tok)
    check("수령 코드 (6자리, 10분)", st == 200 and len(c.get("code", "")) == 6, c.get("display") if st == 200 else str(c))
    st, _ = call("POST", "/staff/pickups/verify", owner_tok, json={"code": c.get("code", "")})
    check("담당자 아닌 사람은 확인 불가", st == 403, f"응답 {st}")
    st, _ = call("POST", "/staff/pickups/verify", staff_tok, json={"code": "000000"})
    check("틀린 코드 거절", st == 404, f"응답 {st}")
    st, r = call("POST", "/staff/pickups/verify", staff_tok, json={"code": c.get("qr", "")})
    check("행정실 QR 확인 -> 수령 완료", st == 200, str(r)[:120])
    st, r = call("GET", f"/matches/{match_id}/pickup/status", owner_tok)
    check("수령 상태 = 완료", st == 200 and r.get("received") is True, str(r)[:120])
    st, r = call("GET", "/pickups?kind=mine", owner_tok)
    check("수령 기록 (내가 찾은 것)", st == 200 and len(r.get("pickups", [])) >= 1)
    st, r = call("GET", "/pickups?kind=given", finder_tok)
    check("수령 기록 (내가 돌려준 것)", st == 200 and len(r.get("pickups", [])) >= 1)


try:
    main()
except Exception as e:
    check("예상 못 한 오류", False, f"{type(e).__name__}: {e}")
finally:
    cleanup()
    ok = sum(1 for _, c in results if c)
    print(f"\n결과: {ok}/{len(results)} 통과")
    bad = [n for n, c in results if not c]
    if bad:
        print("실패:", ", ".join(bad))
