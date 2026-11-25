"""매칭 전체 흐름.

습득물 등록(10~15 화면) -> run_for_found(id)
    비슷한 분실 신고를 찾아 '신고한 사람들'에게 알림 (05 푸시, 27 알림함)
분실 신고(16~17 화면)  -> run_for_lost(id)
    이미 보관 중인 습득물 중 비슷한 것을 바로 찾아 화면에 돌려줌 (17 '비슷한 물건 1건을 찾았어요')

단계: ① 속성 문장 임베딩 -> ② 후보 거르기 + 유사도 점수(속성40·의미25·장소20·시간15)
      -> ③ 상위 후보 AI 재비교·이유 -> ④ 기준 점수 이상 & 상위 3명 -> 저장 + 알림
"""
from . import alerts, config
from . import db as _db
from . import embedding as _embedding
from . import notify as _notify
from . import rerank as _rerank
from .scoring import item_name, total_score
from .sentence import attrs_to_sentence

# 테스트에서 가짜로 바꿔 끼울 수 있게 모듈을 변수로 둠
db, embedding, rerank_mod, notify = _db, _embedding, _rerank, _notify

KEY_LABEL = {"category": "종류", "brand": "브랜드", "model": "모델", "color": "색"}


# ① 임베딩 ----------------------------------------------------------------
def ensure_embedding(table: str, row: dict) -> None:
    if row.get("embedding"):
        return
    sentence = attrs_to_sentence(row.get("attrs") or {}, row.get("description") or "")
    vec = embedding.embed(sentence)
    db.set_embedding(table, row["id"], embedding.to_pgvector(vec))


# ②③ 점수 + AI 재비교 -------------------------------------------------------
def _fallback_reason(detail, same_place: bool) -> str:
    parts = [KEY_LABEL[k] for k in detail.matched_keys if k in KEY_LABEL]
    head = "·".join(parts) + " 일치" if parts else "설명이 비슷해요"
    return head + (", 분실 장소와 같은 건물" if same_place else "")


def _rank(anchor: dict, candidates: list[dict], anchor_is_found: bool) -> list[dict]:
    """일치율(score)은 규칙 점수 그대로 (19 화면 막대 합 = 일치율).
    AI 판단은 순서를 다시 정하고, 같은 물건이 아니라고 본 후보를 걸러 내는 데 씀."""
    items = []
    for c in candidates:
        found, lost = (anchor, c) if anchor_is_found else (c, anchor)
        d = total_score(found, lost, float(c.get("similarity") or 0))
        same_place = (found.get("building") or "") in (lost.get("buildings") or [])
        items.append({"row": c, "detail": d, "score": d.total, "rank": float(d.total),
                      "ai": None, "reason": None, "short": _fallback_reason(d, same_place)})
    items.sort(key=lambda x: x["score"], reverse=True)

    top = items[: config.RERANK_TOP_K]
    judgements = rerank_mod.rerank(anchor, [i["row"] for i in top])
    w = config.RERANK_WEIGHT
    for i in top:
        j = judgements.get(str(i["row"]["id"]))
        if j is not None:
            i["ai"] = j.likelihood
            i["rank"] = (1 - w) * i["score"] + w * j.likelihood
            i["reason"], i["short"] = j.reason, j.short_reason
    for i in items:
        i["reason"] = i["reason"] or i["short"]
    items = [i for i in items if i["ai"] is None or i["ai"] >= config.AI_MIN_LIKELIHOOD]
    items.sort(key=lambda x: x["rank"], reverse=True)
    return items


def _pick(ranked: list[dict]) -> list[dict]:
    """④ 일치율이 기준 점수 이상인 것 중 상위 3개."""
    return [i for i in ranked if i["score"] >= config.NOTIFY_THRESHOLD][: config.NOTIFY_TOP_N]


def _save(found_id: str, lost_id: str, i: dict) -> dict:
    return db.save_match(found_id, lost_id, i["score"], i["detail"].as_dict(),
                         i["reason"], i["short"], i["ai"])


# 알림 ------------------------------------------------------------------------
def notify_user(user_id: str, kind: str, title: str, body: str, data: dict) -> bool:
    """알림함(27)에는 항상 저장, 푸시는 알림 설정(26)을 통과할 때만."""
    db.add_notification(user_id, kind, title, body, data)
    if not alerts.should_push(db.get_settings(user_id), kind=kind):
        return False
    sent = False
    for token in db.get_tokens(user_id):
        if notify.send_match_push(token, title, body, data):
            sent = True
        else:
            db.delete_token(token)
    return sent


def match_push_text(found: dict, i: dict) -> tuple[str, str]:
    """05 화면 형식:
    내 분실물과 비슷한 물건이 등록됐어요
    검정 에어팟 프로 · 형남공학관 3층 · 일치율 92%
    "색·브랜드·장소가 모두 비슷해요\""""
    place = " ".join(p for p in (found.get("building"), found.get("location_detail")) if p)
    line = " · ".join(p for p in (item_name(found.get("attrs")), place, f"일치율 {i['score']}%") if p)
    return "내 분실물과 비슷한 물건이 등록됐어요", f'{line}\n"{i["short"]}"'


# 진입점 ① 습득물이 등록됐을 때 ----------------------------------------------
def run_for_found(found_id: str) -> list[dict]:
    db.set_match_status(found_id, "searching")
    found = db.get_found(found_id)
    ensure_embedding("found_items", found)
    picks = _pick(_rank(found, db.search_lost_for_found(found_id), anchor_is_found=True))

    results = []
    for i in picks:
        lost = i["row"]
        match = _save(found_id, lost["id"], i)
        if match.get("status") == "rejected":
            continue
        if not match.get("notified"):
            title, body = match_push_text(found, i)
            notify_user(lost["owner_id"], "match", title, body,
                        {"type": "match", "match_id": match["id"], "lost_report_id": lost["id"]})
            db.mark_notified(match["id"])
        results.append({"match_id": match["id"], "lost_report_id": lost["id"],
                        "score": i["score"], "reason": i["short"]})
    db.set_match_status(found_id, "notified" if results else "no_match")
    return results


# 진입점 ② 분실 신고가 들어왔을 때 ------------------------------------------
def run_for_lost(lost_id: str) -> list[dict]:
    """신고자는 지금 앱을 보고 있으므로 푸시 대신 결과를 바로 돌려줌 (17 화면)."""
    lost = db.get_lost(lost_id)
    ensure_embedding("lost_reports", lost)
    picks = _pick(_rank(lost, db.search_found_for_lost(lost_id), anchor_is_found=False))

    results = []
    for i in picks:
        found = i["row"]
        match = _save(found["id"], lost_id, i)
        if match.get("status") == "rejected":
            continue
        db.mark_notified(match["id"])
        results.append({"match_id": match["id"], "found_item_id": found["id"],
                        "name": item_name(found.get("attrs")), "score": i["score"], "reason": i["short"]})
    return results
