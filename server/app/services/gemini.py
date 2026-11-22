"""Gemini 로 습득물 사진 → 속성 JSON + 개인정보 영역 추출.

호출 1번으로 두 가지를 같이 받는다 (속도·비용 절약):
  1) 종류 / 브랜드 / 모델 / 색 / 특징  → S12 AI 인식 결과
  2) 개인정보 영역 박스                → S11 개인정보 가리기
"""
from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from app.config import settings
from app.schemas import CATEGORIES, COLORS, PII_TYPES, ItemAttributes

log = logging.getLogger(__name__)

PROMPT = f"""너는 대학교 분실물 센터 직원이다. 사진 속 '주운 물건' 하나를 보고 아래 JSON 으로만 답한다.

규칙
- category 는 반드시 다음 중 하나: {", ".join(CATEGORIES)}
- color 는 물건 본체에서 가장 넓은 색 하나. 반드시 다음 중에서: {", ".join(COLORS)}
- brand 는 로고·각인·고유 디자인으로 확실할 때만 적고, 아니면 null. 추측 금지.
- model 은 확실할 때만 (예: "에어팟 프로"), 아니면 null.
- subcategory 는 짧은 한국어 (예: "무선 이어폰", "반지갑", "체크카드").
- features 는 주인이 알아볼 만한 눈에 보이는 특징 0~4개, 각 10자 이내 (예: "스티커 부착", "모서리 긁힘").
  카드 번호, 이름, 학번 같은 개인정보 내용은 절대 features 나 title 에 쓰지 않는다.
- title 은 "색 + 브랜드 + 물건" 형태의 20자 이내 한국어 (예: "흰색 Apple 에어팟 프로 케이스").
- confidence 는 각 항목을 얼마나 확신하는지 0~1.
- 개인정보: 사진에 이름, 학번, 얼굴 사진, 전화번호, 카드 번호, 주소, 바코드/QR 이 보이면
  pii_detected=true 로 하고 pii_regions 에 각 영역을 type 과 box 로 적는다.
  box 는 [ymin, xmin, ymax, xmax] 이고 이미지 크기를 0~1000 으로 정규화한 정수다.
  type 은 다음 중 하나: {", ".join(PII_TYPES)}
- 목록에 없는 물건(가방, 우산, 열쇠 등)은 category="기타" 로 하고 subcategory 에 이름을 적는다.
- 사진에 물건이 없거나 알아볼 수 없으면 is_item=false, category="기타" 로 답한다.
"""

# Gemini response_schema (OpenAPI 부분집합). 결과는 아래 pydantic 으로 한 번 더 검증한다.
RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "is_item": {"type": "BOOLEAN"},
        "title": {"type": "STRING"},
        "category": {"type": "STRING", "enum": CATEGORIES},
        "subcategory": {"type": "STRING", "nullable": True},
        "brand": {"type": "STRING", "nullable": True},
        "model": {"type": "STRING", "nullable": True},
        "color": {"type": "STRING", "enum": COLORS},
        "features": {"type": "ARRAY", "items": {"type": "STRING"}},
        "confidence": {
            "type": "OBJECT",
            "properties": {
                "category": {"type": "NUMBER"},
                "brand": {"type": "NUMBER"},
                "color": {"type": "NUMBER"},
            },
            "required": ["category", "brand", "color"],
        },
        "pii_detected": {"type": "BOOLEAN"},
        "pii_regions": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "type": {"type": "STRING", "enum": PII_TYPES},
                    "box": {"type": "ARRAY", "items": {"type": "INTEGER"}},
                },
                "required": ["type", "box"],
            },
        },
    },
    "required": ["is_item", "title", "category", "color", "confidence", "pii_detected", "pii_regions"],
    "propertyOrdering": [
        "is_item", "title", "category", "subcategory", "brand", "model",
        "color", "features", "confidence", "pii_detected", "pii_regions",
    ],
}


class GeminiError(RuntimeError):
    pass


def normalize(raw: dict[str, Any]) -> ItemAttributes:
    """Gemini 가 가끔 규칙을 어기는 경우를 정리한 뒤 검증한다."""
    data = dict(raw)
    if data.get("category") not in CATEGORIES:
        data["category"] = "기타"
    color = data.get("color")
    if color not in COLORS:   # 옛 형식 colors[] 로 와도 첫 번째를 쓴다
        color = next((c for c in (data.get("colors") or []) if c in COLORS), "기타")
    data["color"] = color
    data.pop("colors", None)
    for key in ("brand", "model", "subcategory"):
        v = data.get(key)
        if isinstance(v, str) and v.strip().lower() in ("", "null", "none", "unknown", "확인 불가", "알 수 없음"):
            data[key] = None
    data["features"] = [str(f)[:15] for f in (data.get("features") or []) if str(f).strip()][:6]
    conf = data.get("confidence") or {}
    data["confidence"] = {k: max(0.0, min(1.0, float(conf.get(k, 0.5)))) for k in ("category", "brand", "color")}
    regions = []
    for r in data.get("pii_regions") or []:
        if isinstance(r, dict) and r.get("type") in PII_TYPES and isinstance(r.get("box"), list) and len(r["box"]) == 4:
            regions.append(r)
    data["pii_regions"] = regions
    data["pii_detected"] = bool(regions) or bool(data.get("pii_detected"))
    data["title"] = (data.get("title") or data["category"])[:30]
    try:
        return ItemAttributes.model_validate(data)
    except ValidationError as e:
        raise GeminiError(f"AI 결과 형식이 올바르지 않아요: {e.errors()[:2]}") from e


def mock_result() -> ItemAttributes:
    """키 없이 개발할 때 쓰는 고정 결과 (와이어프레임 S12 예시와 동일)."""
    return ItemAttributes(
        is_item=True,
        title="흰색 Apple 에어팟 프로 케이스",
        category="이어폰",
        subcategory="무선 이어폰",
        brand="Apple",
        model="에어팟 프로",
        color="흰색",
        features=["스티커 부착", "케이스 스크래치"],
        confidence={"category": 0.97, "brand": 0.9, "color": 0.95},
        pii_detected=False,
        pii_regions=[],
    )


def extract_attributes(jpeg_bytes: bytes) -> ItemAttributes:
    if not settings.mock and not settings.gemini_api_key:
        # 예전에는 조용히 가짜 결과를 돌려줘서 'AI 가 안 불리는' 걸 알아채기 어려웠다
        raise GeminiError("서버에 GEMINI_API_KEY 가 없어요. .env 를 확인하고 서버를 다시 켜 주세요.")
    if settings.mock:
        if settings.mock_pii:
            return ItemAttributes.model_validate({
                **mock_result().model_dump(),
                "title": "학생증", "category": "학생증·카드", "subcategory": "학생증", "brand": None,
                "model": None, "color": "흰색", "features": [],
                "pii_detected": True,
                "pii_regions": [{"type": "face", "box": [250, 80, 650, 330]},
                                {"type": "name", "box": [260, 380, 340, 820]},
                                {"type": "student_id", "box": [400, 380, 470, 760]}],
            })
        return mock_result()

    # 지연 import: MOCK 모드에선 SDK 가 없어도 서버가 뜬다
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    log.info("Gemini 호출: model=%s, 사진 %d KB", settings.gemini_model, len(jpeg_bytes) // 1024)
    try:
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=[types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"), PROMPT],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
                temperature=0.1,
            ),
        )
    except Exception as e:  # 네트워크, 할당량 초과 등
        log.exception("Gemini 호출 실패")
        raise GeminiError("AI 인식 서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.") from e

    try:
        raw = json.loads(resp.text or "{}")
    except json.JSONDecodeError as e:
        raise GeminiError("AI 결과를 읽지 못했어요.") from e
    return normalize(raw)
