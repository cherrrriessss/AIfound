"""26 알림 설정 화면 규칙.
- 매칭 알림 (match_alert)        : 내 신고와 비슷한 습득물이 등록되면
- 내 습득물 소식 (owner_alert)    : 주인 확인·수령 완료 시 (습득자에게)
- 수령 기한 리마인드 (pickup_reminder) : 보관 기한 하루 전
- 방해 금지 시간 (quiet_start ~ quiet_end)
알림함(27)에는 항상 남기고, 푸시는 이 규칙을 통과할 때만 보냅니다."""
from typing import Optional
from datetime import datetime, time
from zoneinfo import ZoneInfo

from . import config

# 알림 종류 -> 설정 키, 기본값 (26 화면 초기 상태: 매칭 ON, 습득물 소식 ON, 리마인드 OFF)
SETTING_FOR = {
    "match": ("match_alert", True),
    "owner_found": ("owner_alert", True),
    "received": ("owner_alert", True),
    "reminder": ("pickup_reminder", False),
}


def _to_time(v) -> Optional[time]:
    if v is None or isinstance(v, time):
        return v
    hh, mm = str(v).split(":")[:2]
    return time(int(hh), int(mm))


def in_quiet_hours(now_local: time, start, end) -> bool:
    start, end = _to_time(start), _to_time(end)
    if not start or not end or start == end:
        return False
    if start < end:                     # 예: 13:00~14:00
        return start <= now_local < end
    return now_local >= start or now_local < end   # 예: 23:00~08:00 (자정 넘김)


def should_push(settings: Optional[dict], now: Optional[datetime] = None, kind: str = "match") -> bool:
    s = settings or {}
    key, default = SETTING_FOR.get(kind, ("match_alert", True))
    enabled = s.get(key)
    if (default if enabled is None else enabled) is False:
        return False
    now = now or datetime.now(ZoneInfo(config.TIMEZONE))
    local = now.astimezone(ZoneInfo(config.TIMEZONE)).time()
    return not in_quiet_hours(local, s.get("quiet_start"), s.get("quiet_end"))
