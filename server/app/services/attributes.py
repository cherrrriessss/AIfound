"""속성 관련 보조 함수.

임베딩·매칭용 문장은 주희선 님 서버가 attrs(jsonb) 로 직접 만든다.
여기서는 S11 경고 문구만 만든다.
"""
from __future__ import annotations

from typing import Optional

from app.schemas import PII_LABEL_KO, ItemAttributes


def pii_warning_text(attrs: ItemAttributes) -> Optional[str]:
    """S11 경고 배너 문구. 예: '개인정보(이름·학번·얼굴 사진)가 감지됐어요. 가린 뒤에 등록돼요.'"""
    if not attrs.pii_detected or not attrs.pii_regions:
        return None
    seen: list[str] = []
    for r in attrs.pii_regions:
        label = PII_LABEL_KO.get(r.type, "개인정보")
        if label not in seen:
            seen.append(label)
    return f"개인정보({'·'.join(seen)})가 감지됐어요. 가린 뒤에 등록돼요."
