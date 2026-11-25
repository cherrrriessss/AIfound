"""AIfound 매칭 서버 (주희선) — 포트 8000.
실행: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
괄호 안 번호는 와이어프레임 화면 번호입니다.
로그인·습득물 등록·분실 신고·개인정보 가림·보관함 목록은 김준희 서버(8001) 담당."""
from typing import Optional
from datetime import time

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from . import config, db, pickup, pipeline

app = FastAPI(title="AIfound 매칭 서버")


# ---------- 인증 ----------
def internal_only(x_internal_key: str = Header(default="")):
    """서버 내부(습득물 업로드 API 등)에서만 부를 수 있게."""
    if x_internal_key != config.INTERNAL_KEY:
        raise HTTPException(status_code=403, detail="forbidden")


def current_user(authorization: str = Header(default="")) -> str:
    """앱이 보낸 'Authorization: Bearer <Supabase 로그인 토큰>' 확인."""
    token = authorization.removeprefix("Bearer ").strip()
    uid = db.user_id_from_jwt(token) if token else None
    if not uid:
        raise HTTPException(status_code=401, detail="login required")
    return uid


def _own_match(match_id: str, user_id: str) -> dict:
    m = db.get_match_for_owner(match_id, user_id)
    if not m:
        raise HTTPException(status_code=404, detail="match not found")
    return m


# ---------- 매칭 실행 (서버 내부용) ----------
@app.post("/internal/match/found/{found_id}", dependencies=[Depends(internal_only)])
def match_found(found_id: str, bg: BackgroundTasks):
    """(14 등록하기) 습득물 저장 직후 호출. 매칭은 뒤에서 돌고 바로 응답."""
    bg.add_task(pipeline.run_for_found, found_id)
    return {"found_item_id": found_id, "match_status": "searching"}


@app.post("/internal/match/lost/{lost_id}", dependencies=[Depends(internal_only)])
def match_lost(lost_id: str):
    """(16 신고하기) 분실 신고 저장 직후 호출. 결과를 바로 돌려줌 -> 17 화면."""
    matches = pipeline.run_for_lost(lost_id)
    return {"lost_report_id": lost_id, "count": len(matches), "matches": matches}


# ---------- 습득자 화면 ----------
@app.get("/found-items/{found_id}/match-status")
def found_match_status(found_id: str, user_id: str = Depends(current_user)):
    """(15 등록 완료) 사진·AI 태그 저장 -> 비슷한 분실 신고 찾는 중 -> 상위 후보 3명에게 알림"""
    row = db.get_match_status(found_id)
    if row.get("finder_id") != user_id:
        raise HTTPException(status_code=404)
    return {"match_status": row["match_status"]}


# ---------- 분실자 화면 ----------
@app.get("/matches/summary")
def matches_summary(user_id: str = Depends(current_user)):
    """(06 홈) '새 매칭 후보 2건 · 검정 에어팟 프로 신고와 비슷해요' 배너."""
    rows = db.list_unseen_for_owner(user_id)
    top = rows[0] if rows else None
    return {"new_count": len(rows),
            "top": None if not top else {"match_id": top["id"], "lost_report_id": top["lost_report_id"],
                                         "lost_attrs": top["lost_reports"]["attrs"]}}


@app.get("/lost-reports/{lost_id}/matches")
def lost_matches(lost_id: str, user_id: str = Depends(current_user)):
    """(18 매칭 탭) 기준 점수 이상 후보, 일치율 높은 순."""
    rows = db.list_matches_for_lost(lost_id, user_id)
    return {"matches": [{
        "match_id": r["id"], "score": r["score"], "short_reason": r["short_reason"],
        "status": r["status"], "found_item": r["found_items"],
    } for r in rows]}


@app.get("/matches/{match_id}")
def match_detail(match_id: str, user_id: str = Depends(current_user)):
    """(19 매칭 상세) 내 신고 vs 습득물, 일치율, AI가 찾은 이유, 점수 구성, 보관 위치."""
    m = _own_match(match_id, user_id)
    if not m["seen"]:
        db.update_match(match_id, {"seen": True})
    d = m["detail"] or {}
    return {
        "match_id": m["id"], "score": m["score"], "reason": m["reason"], "status": m["status"],
        "breakdown": [
            {"label": "속성", "max": config.W_ATTR, "value": d.get("attr", 0)},
            {"label": "의미", "max": config.W_SEM, "value": d.get("semantic", 0)},
            {"label": "장소", "max": config.W_PLACE, "value": d.get("place", 0)},
            {"label": "시간", "max": config.W_TIME, "value": d.get("time", 0)},
        ],
        "my_report": m["lost_reports"], "found_item": m["found_items"],
    }


@app.post("/matches/{match_id}/claim")
def claim(match_id: str, user_id: str = Depends(current_user)):
    """(19 '내 물건이에요') 수령 대기 7일 시작 + 습득자에게 '주인이 확인했어요' 알림 -> 20 화면으로."""
    m = _own_match(match_id, user_id)
    if m["status"] in ("claimed", "received"):
        return {"status": m["status"], "pickup_deadline": m.get("pickup_deadline")}
    return pickup.claim(m)


# ---------- 수령 (20, 25) ----------
def _claimed_match(match_id: str, user_id: str) -> dict:
    m = _own_match(match_id, user_id)
    if m["status"] not in ("claimed", "received"):
        raise HTTPException(status_code=409, detail="먼저 '내 물건이에요'를 눌러 주세요")
    return m


@app.get("/matches/{match_id}/pickup")
def pickup_guide(match_id: str, user_id: str = Depends(current_user)):
    """(20 수령 안내) 물건, 수령 기한, 보관함, 수령 코드."""
    return pickup.guide(_claimed_match(match_id, user_id))


@app.get("/matches/{match_id}/pickup/code")
def pickup_code(match_id: str, user_id: str = Depends(current_user)):
    """(20) 10분마다 새 코드. expires_in 초 뒤에 다시 호출."""
    _claimed_match(match_id, user_id)
    return pickup.current_code(match_id)


@app.get("/matches/{match_id}/pickup/status")
def pickup_status(match_id: str, user_id: str = Depends(current_user)):
    """(20 '수령 완료 확인') 행정실 확인이 끝났는지."""
    return pickup.status(_own_match(match_id, user_id))


class VerifyIn(BaseModel):
    code: str          # '482913' 또는 QR 문자열 'AIFOUND:<match_id>:<code>'


@app.post("/staff/pickups/verify")
def staff_verify(body: VerifyIn, user_id: str = Depends(current_user)):
    """행정실 담당자 화면: 학생이 보여 준 코드/QR 확인 -> 수령 완료 + 기록."""
    if not db.get_staff_lockers(user_id):
        raise HTTPException(status_code=403, detail="보관함 담당자만 확인할 수 있어요")
    rec = pickup.verify(user_id, body.code)
    if not rec:
        raise HTTPException(status_code=404, detail="코드가 맞지 않거나 만료됐어요")
    return {"ok": True, "pickup": rec}


@app.get("/pickups")
def pickups(kind: str = "all", user_id: str = Depends(current_user)):
    """(25 수령 기록) kind = all / mine(내가 찾은 것) / given(내가 돌려준 것)"""
    return {"pickups": db.list_pickups(user_id, kind)}


@app.post("/internal/cron/reminders", dependencies=[Depends(internal_only)])
def cron_reminders():
    """하루 한 번 호출 (Supabase Cron, GitHub Actions 등): 수령 기한 하루 전 알림."""
    return {"sent": pickup.send_reminders()}


class RejectIn(BaseModel):
    reasons: list[str] = []      # category / color / brand_model / place_time / other


@app.post("/matches/{match_id}/reject")
def reject(match_id: str, body: RejectIn, user_id: str = Depends(current_user)):
    """(21 '보내고 후보에서 제외' / '건너뛰기') 이 후보는 다시 보여 주거나 알리지 않음.
    고른 이유는 가중치 조정(Top-3 적중률 개선)에 씀."""
    _own_match(match_id, user_id)
    reasons = [r for r in body.reasons if r in config.REJECT_REASONS]
    db.update_match(match_id, {"status": "rejected", "feedback": {"reasons": reasons}})
    return {"ok": True}


# ---------- 알림 ----------
class DeviceIn(BaseModel):
    fcm_token: str


@app.post("/devices")
def register_device(body: DeviceIn, user_id: str = Depends(current_user)):
    """(03 알림 허용하기 / 로그인 후) FCM 토큰 등록."""
    db.save_token(user_id, body.fcm_token)
    return {"ok": True}


@app.get("/notifications")
def notifications(user_id: str = Depends(current_user)):
    """(27 알림함)"""
    return {"notifications": db.list_notifications(user_id)}


@app.post("/notifications/read-all")
def read_all(user_id: str = Depends(current_user)):
    """(27 '모두 읽음')"""
    db.mark_all_read(user_id)
    return {"ok": True}


class SettingsIn(BaseModel):
    match_alert: Optional[bool] = None
    quiet_start: Optional[time] = None      # 예: "23:00"
    quiet_end: Optional[time] = None        # 예: "08:00"
    interest_buildings: Optional[list[str]] = None


@app.get("/settings/notifications")
def get_settings(user_id: str = Depends(current_user)):
    """(26 알림 설정)"""
    return db.get_settings(user_id)


@app.put("/settings/notifications")
def put_settings(body: SettingsIn, user_id: str = Depends(current_user)):
    fields = {k: (v.isoformat(timespec="minutes") if isinstance(v, time) else v)
              for k, v in body.model_dump().items() if v is not None}
    return db.save_settings(user_id, fields)


@app.get("/health")
def health():
    """서버가 켜졌는지 + 키가 들어갔는지 (값은 보여 주지 않음)."""
    return {"ok": True, "server": "match", "port": 8000,
            "supabase": bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY),
            "gemini": bool(config.GEMINI_API_KEY), "model": config.GEMINI_MODEL}
