"""유사도 점수 계산: 속성 40 + 의미 25 + 장소 20 + 시간 15 = 100점 만점 (=일치율 %).

19 매칭 상세 화면의 '점수 구성' 막대가 이 네 숫자이고, 합이 일치율입니다.
외부 서비스를 쓰지 않는 순수 계산이라 테스트하기 쉽습니다.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import config, geo


@dataclass
class ScoreDetail:
    attr: int        # 0~40
    semantic: int    # 0~25
    place: int       # 0~20
    time: int        # 0~15
    total: int       # 0~100 (= 위 네 개의 합)
    matched_keys: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"attr": self.attr, "semantic": self.semantic, "place": self.place,
                "time": self.time, "total": self.total, "matched_keys": self.matched_keys}


# '확인 불가', '기타' 는 정보가 없는 값 -> 그 항목은 비교하지 않음 (기타 vs 기타 를 '일치'로 세지 않기)
UNKNOWN = {"확인불가", "기타", "모름"}


def _norm(v) -> str:
    return str(v or "").strip().lower().replace(" ", "").replace("·", "")


def attr_ratio(found: dict, lost: dict) -> tuple[float, list]:
    """두 물건의 속성(종류, 브랜드, 모델, 색) 일치 비율.
    한쪽이라도 값이 비어 있거나 '확인 불가'인 항목은 비교에서 뺍니다."""
    got = total = 0.0
    matched = []
    for key, weight in config.ATTR_KEYS.items():
        a, b = _norm(found.get(key)), _norm(lost.get(key))
        if not a or not b or UNKNOWN & {a, b}:
            continue
        total += weight
        if a == b or a in b or b in a:      # '에어팟프로2' vs '에어팟프로' 같은 부분 일치 허용
            got += weight
            matched.append(key)
    return (got / total if total else 0.0), matched


def semantic_ratio(cosine_similarity: float) -> float:
    """임베딩 코사인 유사도(보통 0.5~1.0 사이)를 0~1로 펼침."""
    floor = config.SEM_FLOOR
    return max(0.0, min(1.0, (cosine_similarity - floor) / (1.0 - floor)))


def place_ratio(found_building: str, lost_buildings: list[str]) -> float:
    """분실 신고는 건물을 여러 개 고를 수 있음(16 화면) -> 가장 잘 맞는 건물 기준."""
    if not found_building or not lost_buildings:
        return 0.3                      # 장소를 모르면 중간보다 조금 낮게
    best = 0.0
    for b in lost_buildings:
        if b == found_building:
            return 1.0
        if geo.is_nearby(found_building, b):
            best = max(best, 0.5)
    return best


def time_ratio(lost_from: datetime, lost_to: datetime, found_at: datetime) -> float:
    """분실 시간대(예: 12:00~15:00) 안에 주웠으면 만점, 끝난 뒤 늦게 주울수록 감점,
    잃어버리기 전에 주웠으면 0 (1시간 오차 허용)."""
    if not found_at or not lost_from:
        return 0.3
    lost_to = lost_to or lost_from
    if found_at < lost_from - timedelta(hours=1):
        return 0.0
    if found_at <= lost_to:
        return 1.0
    hours_after = (found_at - lost_to).total_seconds() / 3600
    return max(0.0, 1.0 - hours_after / config.TIME_WINDOW_HOURS)


def total_score(found: dict, lost: dict, cosine_similarity: float) -> ScoreDetail:
    """found: 습득물 행 {attrs, building, found_at}
    lost:  분실 신고 행 {attrs, buildings, lost_from, lost_to}"""
    a, matched = attr_ratio(found.get("attrs") or {}, lost.get("attrs") or {})
    pts = [
        round(config.W_ATTR * a),
        round(config.W_SEM * semantic_ratio(cosine_similarity)),
        round(config.W_PLACE * place_ratio(found.get("building"), lost.get("buildings") or [])),
        round(config.W_TIME * time_ratio(lost.get("lost_from"), lost.get("lost_to"), found.get("found_at"))),
    ]
    return ScoreDetail(*pts, total=sum(pts), matched_keys=matched)


def item_name(attrs: dict) -> str:
    """알림/목록에 보여 줄 이름. 예: '검정 에어팟 프로', '검정 Apple 이어폰'"""
    attrs = attrs or {}
    color = attrs.get("color") or ""
    if attrs.get("model"):
        core = attrs["model"]
    else:
        core = " ".join(p for p in (attrs.get("brand"), attrs.get("category")) if p and p != "확인 불가")
    return " ".join(p for p in (color, core) if p).strip() or "물건"
