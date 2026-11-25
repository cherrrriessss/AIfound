"""상위 후보를 Gemini가 다시 비교해서 '같은 물건일 가능성'과 '비슷한 이유'를 만듭니다.

reason       -> 19 매칭 상세 'AI가 찾은 이유' (한두 문장)
short_reason -> 18 매칭 후보 목록, 05 푸시 알림 (짧게)
"""
import json

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from . import config


class Judgement(BaseModel):
    candidate_id: str
    likelihood: int = Field(description="같은 물건일 가능성 0~100")
    reason: str = Field(description="학생에게 보여 줄 이유 한두 문장")
    short_reason: str = Field(description="25자 안팎의 짧은 이유")


class RerankResult(BaseModel):
    results: list[Judgement]


PROMPT = """너는 대학교 분실물 센터 직원이다.
기준 물건과 후보들을 비교해서, 각 후보가 기준 물건과 '같은 물건'일 가능성을 0~100으로 매겨라.
- 종류, 브랜드, 모델, 색, 고유한 특징(스티커, 흠집, 케이스, 키링 등)을 가장 중요하게 본다.
- 장소와 시간이 자연스러운지도 고려한다. (분실 시간대보다 먼저 주운 것은 같은 물건일 수 없다)
- reason 예: "검정 에어팟 프로로 종류·색·브랜드가 같고, 분실 시간 2시간 뒤 같은 건물에서 습득됐어요."
- short_reason 예: "종류·색·브랜드 일치, 분실 장소와 같은 건물"
- 개인정보(이름, 학번, 전화번호, 카드 번호)는 절대 쓰지 마라.
- 모든 후보에 대해 candidate_id를 그대로 돌려줘라.

[기준 물건]
{anchor}

[후보 목록]
{candidates}
"""

_client = None


def _gemini():
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _summary(row: dict) -> dict:
    """Gemini에 보낼 정보만 추림(개인정보, 사진 주소 제외)."""
    if "found_at" in row:
        place = f'{row.get("building") or ""} {row.get("location_detail") or ""}'.strip()
        when = str(row.get("found_at"))
        kind = "습득물"
    else:
        place = ", ".join(row.get("buildings") or [])
        when = f'{row.get("lost_from")} ~ {row.get("lost_to")}'
        kind = "분실 신고"
    return {"구분": kind, "속성": row.get("attrs") or {}, "설명": row.get("description") or "",
            "장소": place, "시각": when}


def rerank(anchor: dict, candidates: list[dict]) -> dict[str, Judgement]:
    """anchor: 기준(습득물 또는 분실 신고), candidates: [{'id':..., 행 데이터...}, ...]
    반환: {후보 id: Judgement}.  실패하면 빈 dict (규칙 점수만으로 진행)."""
    if not candidates:
        return {}
    prompt = PROMPT.format(
        anchor=json.dumps(_summary(anchor), ensure_ascii=False, default=str),
        candidates=json.dumps(
            [{"candidate_id": str(c["id"]), **_summary(c)} for c in candidates],
            ensure_ascii=False, default=str),
    )
    try:
        resp = _gemini().models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RerankResult,
                temperature=0.2,
            ),
        )
        parsed = resp.parsed if resp.parsed is not None else RerankResult.model_validate_json(resp.text)
    except Exception as e:  # 한도 초과, 네트워크 오류 등
        print(f"[rerank] Gemini 호출 실패, 규칙 점수로만 진행: {e}")
        return {}
    out = {}
    for j in parsed.results:
        j.likelihood = max(0, min(100, int(j.likelihood)))
        out[str(j.candidate_id)] = j
    return out
