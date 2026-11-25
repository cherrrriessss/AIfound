"""수령 절차 (19 '내 물건이에요' -> 20 수령 안내 -> 25 수령 기록) + 상태 알림(27).

1) claim()       : 분실자가 '내 물건이에요' -> 수령 대기(7일), 습득자에게 '주인이 확인했어요' 알림
2) current_code(): 20 화면 수령 코드 (6자리, 10분마다 바뀜) + QR 문자열
3) verify()      : 행정실 담당자가 코드(또는 QR) 확인 -> 수령 완료 처리, 기록 저장,
                   습득자에게 '수령 완료' 알림, 같은 습득물의 다른 후보는 정리
4) send_reminders(): 수령 기한 하루 전 리마인드 (26 '수령 기한 리마인드' 켠 사람만)
"""
from typing import Optional
import hashlib
import hmac
import time as _time
from datetime import datetime, timedelta, timezone

from . import config, pipeline
from .scoring import item_name

CODE_PERIOD = 600          # 10분
PICKUP_DAYS = 7            # 20 화면: '7일 내 수령'


# ---------- 수령 코드 ----------
def _code_for(match_id: str, window: int) -> str:
    mac = hmac.new(config.PICKUP_SECRET.encode(), f"{match_id}:{window}".encode(), hashlib.sha256).digest()
    return f"{int.from_bytes(mac[:4], 'big') % 1_000_000:06d}"


def current_code(match_id: str, now: Optional[float] = None) -> dict:
    now = now if now is not None else _time.time()
    window = int(now // CODE_PERIOD)
    code = _code_for(match_id, window)
    return {"code": code, "display": f"{code[:3]} {code[3:]}",           # '482 913'
            "qr": f"AIFOUND:{match_id}:{code}",
            "expires_in": int((window + 1) * CODE_PERIOD - now)}


def code_matches(match_id: str, code: str, now: Optional[float] = None) -> bool:
    """지금 코드 또는 직전 코드(바뀌는 순간 대비)까지 인정."""
    now = now if now is not None else _time.time()
    window = int(now // CODE_PERIOD)
    code = code.replace(" ", "")
    return any(hmac.compare_digest(code, _code_for(match_id, w)) for w in (window, window - 1))


# ---------- 1) 내 물건이에요 ----------
def claim(match: dict, now: Optional[datetime] = None) -> dict:
    """match: db.get_match_for_owner 결과 (found_items, lost_reports 포함)"""
    db = pipeline.db
    now = now or datetime.now(timezone.utc)
    deadline = now + timedelta(days=PICKUP_DAYS)
    db.update_match(match["id"], {"status": "claimed", "claimed_at": now.isoformat(),
                                  "pickup_deadline": deadline.isoformat()})
    found = match["found_items"]
    if found.get("finder_id"):
        pipeline.notify_user(found["finder_id"], "owner_found", "주인이 확인했어요",
                             f"등록하신 {item_name(found.get('attrs'))}의 주인을 찾았어요. 감사해요!",
                             {"type": "owner_found", "found_item_id": found["id"]})
    return {"status": "claimed", "pickup_deadline": deadline.isoformat()}


# ---------- 1-2) 08 습득물 상세에서 바로 '내 물건이에요' (매칭 없이) ----------
DIRECT_REASON = "습득물 상세에서 직접 '내 물건이에요'를 눌렀어요"


def direct_claim(found: dict, user_id: str, now: Optional[datetime] = None) -> dict:
    """AI 매칭 결과(match_id)가 없어도 수령을 요청할 수 있게.

    수령 코드·행정실 확인·수령 기록이 모두 matches 기준이라, 여기서 매칭 한 줄을 만들어
    기존 수령 흐름(20 → 25)을 그대로 탄다.
      - 이미 내 신고와 이 습득물 사이에 매칭이 있으면 그걸 claim
      - 없으면 습득물 정보로 '직접 수령 요청' 분실 신고를 만들고 (임베딩 없음 → 다른 매칭엔 안 쓰임)
        score 0, detail.direct=true 인 매칭을 만들어 claim
    본인 확인은 행정실에서 학교 메일 + 수령 코드로 한다 (20 화면).
    돌려줌: {"match_id", "status", "pickup_deadline", "direct"}
    """
    db = pipeline.db
    now = now or datetime.now(timezone.utc)
    match = db.find_owner_match_for_found(found["id"], user_id)
    direct = match is None
    if direct:
        attrs = dict(found.get("attrs") or {})
        attrs["direct_claim"] = True
        found_at = found.get("found_at") or now
        if isinstance(found_at, str):
            found_at = datetime.fromisoformat(found_at.replace("Z", "+00:00"))
        lost = db.create_lost_report({
            "owner_id": user_id,
            "category": found.get("category") or attrs.get("category") or "기타",
            "attrs": attrs,
            "description": DIRECT_REASON,
            "buildings": [found["building"]] if found.get("building") else [],
            "lost_from": (found_at - timedelta(days=1)).isoformat(),
            "lost_to": found_at.isoformat(),
        })
        row = db.create_match({
            "found_item_id": found["id"], "lost_report_id": lost["id"], "score": 0,
            "detail": {"direct": True}, "reason": DIRECT_REASON, "short_reason": "직접 수령 요청",
            "seen": True,
        })
        match = db.get_match_for_owner(row["id"], user_id)
    if match["status"] in ("claimed", "received"):
        return {"match_id": match["id"], "status": match["status"],
                "pickup_deadline": match.get("pickup_deadline"), "direct": direct}
    out = claim(match, now)
    return {"match_id": match["id"], **out, "direct": direct}


def guide(match: dict) -> dict:
    """20 수령 안내 화면 데이터."""
    found, locker = match["found_items"], (match["found_items"].get("lockers") or {})
    return {
        "item": {"id": found.get("id"), "name": item_name(found.get("attrs")), "photo_path": found.get("photo_path")},
        "deadline": match.get("pickup_deadline"),
        "steps": [
            {"no": 1, "title": "학교 메일 본인 확인", "done": True},
            {"no": 2, "title": "보관함으로 가기", "locker": locker},
            {"no": 3, "title": "아래 수령 코드를 보여주세요"},
        ],
        "code": current_code(match["id"]),
    }


# ---------- 3) 행정실 확인 -> 수령 완료 ----------
def verify(staff_user_id: str, code_or_qr: str, now: Optional[datetime] = None) -> Optional[dict]:
    """행정실 담당자 화면에서 입력한 6자리 코드 또는 QR 문자열로 수령 처리.
    담당자가 맡은 보관함의 '수령 대기' 건 중에서만 찾음."""
    db = pipeline.db
    now = now or datetime.now(timezone.utc)
    lockers = db.get_staff_lockers(staff_user_id)
    if not lockers:
        return None
    target_id, code = None, code_or_qr.strip()
    if code.startswith("AIFOUND:"):
        _, target_id, code = code.split(":", 2)
    for m in db.list_claimed_for_lockers(lockers):
        if (target_id is None or m["id"] == target_id) and code_matches(m["id"], code):
            return _complete(m, staff_user_id, code, now)
    return None


def _complete(m: dict, staff_user_id: str, code: str, now: datetime) -> dict:
    db = pipeline.db
    found, lost = m["found_items"], m["lost_reports"]
    pickup = db.create_pickup({
        "match_id": m["id"], "found_item_id": found["id"], "receiver_id": lost["owner_id"],
        "finder_id": found.get("finder_id"), "locker_id": found.get("locker_id"),
        "code": code, "verified_by": staff_user_id, "received_at": now.isoformat(),
    })
    db.update_match(m["id"], {"status": "received"})
    db.set_found_status(found["id"], "returned")
    db.set_lost_status(lost["id"], "closed")
    db.close_other_matches(found["id"], m["id"])
    name = item_name(found.get("attrs"))
    if found.get("finder_id"):
        pipeline.notify_user(found["finder_id"], "received", "수령 완료",
                             f"{name}이(가) 주인에게 전달됐어요.", {"type": "received", "found_item_id": found["id"]})
    pipeline.notify_user(lost["owner_id"], "received", "수령 완료",
                         f"{name} 수령이 기록됐어요.", {"type": "received", "match_id": m["id"]})
    return pickup


def status(match: dict) -> dict:
    """20 '수령 완료 확인' 버튼: 행정실 확인이 끝났는지."""
    return {"received": match.get("status") == "received"}


# ---------- 4) 수령 기한 리마인드 ----------
def send_reminders(now: Optional[datetime] = None) -> int:
    """매일 한 번 호출(예: 오전 10시). 기한이 24시간 안으로 남은 수령 대기 건."""
    db = pipeline.db
    now = now or datetime.now(timezone.utc)
    sent = 0
    for m in db.list_due_reminders(now + timedelta(days=1)):
        found = m["found_items"]
        locker = (found.get("lockers") or {}).get("name", "보관함")
        pipeline.notify_user(m["lost_reports"]["owner_id"], "reminder", "수령 기한이 하루 남았어요",
                             f"{item_name(found.get('attrs'))} · {locker}에서 찾아가세요.",
                             {"type": "reminder", "match_id": m["id"]})
        db.update_match(m["id"], {"reminded": True})
        sent += 1
    return sent
