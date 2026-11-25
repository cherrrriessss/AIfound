"""Gemini가 뽑은 속성 JSON을 임베딩용 한 문장으로 바꿉니다.

예) {"category": "무선이어폰", "brand": "애플", "model": "에어팟 프로 2",
     "color": "흰색", "features": ["케이스에 곰돌이 스티커"]}
 -> "흰색 애플 에어팟 프로 2 무선이어폰. 특징: 케이스에 곰돌이 스티커"
"""


def _clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(_clean(v) for v in value if _clean(v))
    text = str(value).strip()
    return "" if text.lower() in {"", "unknown", "none", "null", "모름", "알 수 없음"} else text


def attrs_to_sentence(attrs: dict, extra_text: str = "") -> str:
    """속성 dict(+ 사용자가 직접 쓴 설명)를 한 문장으로."""
    attrs = attrs or {}
    head = " ".join(
        part for part in (
            _clean(attrs.get("color")),
            _clean(attrs.get("brand")),
            _clean(attrs.get("model")),
            _clean(attrs.get("category")),
        ) if part
    )
    tail = []
    features = _clean(attrs.get("features"))
    if features:
        tail.append(f"특징: {features}")
    extra = _clean(extra_text)
    if extra:
        tail.append(f"설명: {extra}")
    sentence = ". ".join([p for p in [head] + tail if p])
    return sentence or "정보 없음"
