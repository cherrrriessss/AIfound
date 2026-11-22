"""API 요청/응답과 Gemini 결과 JSON 의 모양(스키마). 팀원 간 '약속'.

- DB 의 attrs(jsonb) 모양은 주희선 님 매칭 코드와 같다:
    {category, subcategory, brand, model, color, features[], title}
- 이민서(앱): 아래 Response 모델 모양대로 화면에 뿌린다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# 고정 값 목록 — 팀 합의: 물건 종류 5개 (12 AI 결과, 16 분실 신고 칩, 매칭 모두 이 목록)
# ---------------------------------------------------------------------------
CATEGORIES = ["이어폰", "지갑", "학생증·카드", "휴대폰", "기타"]
COLORS = [
    "검정", "흰색", "회색", "은색", "금색", "빨강", "주황", "노랑",
    "초록", "파랑", "남색", "보라", "분홍", "갈색", "베이지", "투명", "기타",
]
PII_TYPES = ["name", "student_id", "face", "phone", "card_number", "address", "barcode", "other"]
PII_LABEL_KO = {
    "name": "이름", "student_id": "학번", "face": "얼굴 사진", "phone": "전화번호",
    "card_number": "카드 번호", "address": "주소", "barcode": "바코드", "other": "기타 개인정보",
}

Category = Literal[tuple(CATEGORIES)]  # type: ignore[valid-type]
Color = Literal[tuple(COLORS)]  # type: ignore[valid-type]
PiiType = Literal[tuple(PII_TYPES)]  # type: ignore[valid-type]


# ---------------------------------------------------------------------------
# Gemini 속성 추출 결과
# ---------------------------------------------------------------------------
class PiiRegion(BaseModel):
    type: PiiType
    # Gemini 표준 좌표: [ymin, xmin, ymax, xmax], 0~1000 으로 정규화
    box: list[int] = Field(min_length=4, max_length=4)

    @field_validator("box")
    @classmethod
    def _clamp(cls, v: list[int]) -> list[int]:
        v = [max(0, min(1000, int(x))) for x in v]
        ymin, xmin, ymax, xmax = v
        if ymin > ymax:
            ymin, ymax = ymax, ymin
        if xmin > xmax:
            xmin, xmax = xmax, xmin
        return [ymin, xmin, ymax, xmax]


class Confidence(BaseModel):
    category: float = Field(ge=0, le=1)
    brand: float = Field(ge=0, le=1)
    color: float = Field(ge=0, le=1)


class ItemAttributes(BaseModel):
    """S12 'AI 인식 결과' 화면에 그대로 대응."""
    is_item: bool = True
    title: str                               # 예: 흰색 Apple 에어팟 프로 케이스
    category: Category
    subcategory: Optional[str] = None        # 예: 무선 이어폰
    brand: Optional[str] = None              # None = 확인 불가
    model: Optional[str] = None              # 예: 에어팟 프로
    color: Color                             # 주 색 하나 (주희선 매칭과 같은 키)
    features: list[str] = Field(default_factory=list, max_length=6)
    confidence: Confidence
    pii_detected: bool = False
    pii_regions: list[PiiRegion] = Field(default_factory=list)

    def to_attrs(self) -> dict[str, Any]:
        """DB attrs(jsonb) 로 저장할 값 — 매칭에 쓰는 키만."""
        return {
            "category": self.category,
            "subcategory": self.subcategory,
            "brand": self.brand,
            "model": self.model,
            "color": self.color,
            "features": list(self.features),
            "title": self.title,
        }


# ---------------------------------------------------------------------------
# 인증
# ---------------------------------------------------------------------------
class RequestCodeIn(BaseModel):
    email: str = Field(min_length=2, max_length=120)   # "20231234" 또는 "20231234@soongsil.ac.kr"


class RequestCodeOut(BaseModel):
    email: str
    expires_in: int
    resend_after: int


class VerifyIn(BaseModel):
    email: str
    code: str = Field(pattern=r"^\d{6,10}$")   # Supabase 설정에 따라 6~10자리


class TokenOut(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int
    is_new_user: bool        # True 면 앱이 S03 프로필 설정으로 이동
    user: "ProfileOut"


class RefreshIn(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# 프로필 (알림 설정·FCM 토큰은 주희선 서버: /settings/notifications, /devices)
# ---------------------------------------------------------------------------
class ProfileOut(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    department: Optional[str] = None


class ProfileUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=30)
    department: Optional[str] = Field(default=None, max_length=50)


# ---------------------------------------------------------------------------
# 보관함
# ---------------------------------------------------------------------------
class LockerOut(BaseModel):
    id: str
    name: str
    code: Optional[str] = None
    building: str
    location: Optional[str] = None
    hours: Optional[str] = None
    same_building: bool = False   # S14 '가장 가까움' 표시용


# ---------------------------------------------------------------------------
# 습득물
# ---------------------------------------------------------------------------
class AnalyzeOut(BaseModel):
    """POST /found/analyze 응답 → S11(가림) + S12(태그)."""
    attributes: ItemAttributes
    pii_warning: Optional[str] = None
    image_width: int
    image_height: int


class MaskBox(BaseModel):
    box: list[int] = Field(min_length=4, max_length=4)   # [ymin, xmin, ymax, xmax] 0~1000


class FoundCreateIn(BaseModel):
    """POST /found 의 data 필드(JSON 문자열). 사진은 image 파일 필드로 따로."""
    attributes: ItemAttributes            # S12 에서 사용자가 수정한 최종값
    building: str = Field(min_length=1, max_length=50)
    location_detail: Optional[str] = Field(default=None, max_length=100)
    found_at: datetime
    description: Optional[str] = Field(default=None, max_length=300)
    locker_id: str
    # 앱이 이미 /privacy/blur 로 가린 사진을 보내면 비워 둔다
    mask_boxes: list[MaskBox] = Field(default_factory=list)


class FoundOut(BaseModel):
    id: str
    photo_url: Optional[str] = None
    category: str
    attrs: dict[str, Any]
    title: str
    description: Optional[str] = None
    building: Optional[str] = None
    location_detail: Optional[str] = None
    found_at: datetime
    locker: Optional[LockerOut] = None
    status: str
    match_status: str           # 15 진행 상황: pending / searching / notified / no_match
    created_at: datetime
    display_status: str = "stored"      # 24 배지: stored / owner_confirmed / returned
    display_label: str = "보관 중"


class FoundListOut(BaseModel):
    items: list[FoundOut]
    total: int
    page: int
    size: int


# ---------------------------------------------------------------------------
# 분실 신고 (16, 17, 23)
# ---------------------------------------------------------------------------
class LostCreateIn(BaseModel):
    category: Category
    brand: Optional[str] = Field(default=None, max_length=40)
    model: Optional[str] = Field(default=None, max_length=40)
    color: Color
    features: list[str] = Field(default_factory=list, max_length=6)
    description: Optional[str] = Field(default=None, max_length=300)
    buildings: list[str] = Field(min_length=1, max_length=10)
    lost_from: datetime
    lost_to: datetime

    def to_attrs(self) -> dict[str, Any]:
        return {"category": self.category, "brand": self.brand, "model": self.model,
                "color": self.color, "features": list(self.features)}


class LostUpdateIn(BaseModel):
    """23 '수정' — 보낸 항목만 바뀐다."""
    category: Optional[Category] = None
    brand: Optional[str] = Field(default=None, max_length=40)
    model: Optional[str] = Field(default=None, max_length=40)
    color: Optional[Color] = None
    features: Optional[list[str]] = Field(default=None, max_length=6)
    description: Optional[str] = Field(default=None, max_length=300)
    buildings: Optional[list[str]] = Field(default=None, min_length=1, max_length=10)
    lost_from: Optional[datetime] = None
    lost_to: Optional[datetime] = None


class LostOut(BaseModel):
    id: str
    category: str
    attrs: dict[str, Any]
    description: Optional[str] = None
    buildings: list[str]
    lost_from: datetime
    lost_to: datetime
    photo_url: Optional[str] = None
    status: str
    created_at: datetime
    # 23 화면: 매칭 대기 → 후보 있음 → 수령 대기 → 수령 완료 (종료하면 신고 종료)
    stage: str = "waiting"
    stage_label: str = "매칭 대기"
    match_count: int = 0                # '후보 2건' 배지
    # 저장 직후 주희선 서버 /internal/match/lost/{id} 응답 그대로 (17 화면). 실패하면 null
    match: Optional[Any] = None


class SummaryOut(BaseModel):
    """22 마이페이지 숫자 3개 + 24 '지금까지 n명에게 돌려줬어요'."""
    lost_count: int          # 분실 신고 (전체)
    lost_open_count: int     # 그중 진행 중
    found_count: int         # 습득물 등록
    returned_count: int      # 내가 등록한 습득물 중 주인에게 돌아간 수
    received_count: int      # 내가 찾아간 수 (수령 완료)


class OkOut(BaseModel):
    ok: bool = True


TokenOut.model_rebuild()
