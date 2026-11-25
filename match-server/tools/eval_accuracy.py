"""매칭 정확도 측정 (제안서 9쪽 'Top-3 적중률') + 알림 기준 점수(60) 근거 만들기.

사용법 (match-server 폴더, 가상환경 켠 상태. 서버는 안 켜도 됨):
    python tools/eval_accuracy.py            # 측정 후 테스트 데이터 삭제
    python tools/eval_accuracy.py --keep     # 데이터 남기기

하는 일
  1) 정답이 있는 분실 신고 20건 + 그 정답 습득물 20건 + 헷갈리게 하는 습득물 8건을 Supabase에 넣음
     (분실자가 쓴 말과 습득자/AI가 쓴 말이 조금씩 다르게: 모델 생략, 브랜드 '확인불가', 옆 건물 등)
  2) 실제 매칭 코드(임베딩 -> 후보 -> 점수 -> Gemini 재비교)를 그대로 돌림 (알림은 보내지 않음)
  3) 결과
     - Top-1 / Top-3 적중률 (AI 재비교 포함, 규칙 점수만 썼을 때와 비교)
     - 정답 후보 점수 vs 오답 후보 점수 분포
     - 기준 점수 40~80 별: 정답 짝이 기준을 넘는 비율, 기준을 넘는 오답 짝 수  -> 60 을 고른 근거
  4) match-server/eval/accuracy_YYYYMMDD.md 로 저장 (보고서·발표에 그대로 사용)
"""
import os
import sys
import time
import secrets
import statistics
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config, db, pipeline, rerank
from app.scoring import total_score

KEEP = "--keep" in sys.argv
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST).replace(second=0, microsecond=0)
sb = db.sb()
tag = secrets.token_hex(3)


def ago(hours: float) -> str:
    return (NOW - timedelta(hours=hours)).isoformat()


def A(cat, brand, model, color, *features):
    return {"category": cat, "brand": brand, "model": model, "color": color,
            "features": list(features), "eval": True}


# ---------------------------------------------------------------------------
# 정답 쌍 20개: (설명, 분실 신고, 정답 습득물)
#   분실: attrs, 설명, 건물들, 분실 시작(몇 시간 전), 분실 끝(몇 시간 전)
#   습득: attrs, 설명, 건물, 상세 위치, 습득(몇 시간 전)
# ---------------------------------------------------------------------------
CASES = [
    ("같은 건물, 정보 거의 같음",
     (A("이어폰", "Apple", "에어팟 프로 2", "흰색", "케이스에 곰돌이 스티커"), "흰색 에어팟 프로 2, 케이스에 곰돌이 스티커", ["정보과학관"], 8, 5),
     (A("이어폰", "Apple", "에어팟 프로 2", "흰색", "스티커 붙어 있음"), "스티커 붙은 흰색 에어팟", "정보과학관", "3층 열람실", 4)),
    ("습득 쪽 모델명이 덜 구체적",
     (A("이어폰", "삼성", "갤럭시 버즈2 프로", "검정", "실리콘 케이스"), "검정 버즈2 프로, 실리콘 케이스", ["학생회관"], 30, 27),
     (A("이어폰", "삼성", "갤럭시 버즈", "검정", "케이스 있음"), "검정 갤럭시 버즈", "학생회관", "2층 식당", 26)),
    ("브랜드 표기 다름 (애플 / Apple) + 옆 건물",
     (A("이어폰", "애플", "에어팟 3세대", "흰색", "케이스 모서리 긁힘"), "흰색 에어팟 3세대, 모서리 긁힘", ["베어드홀"], 6, 4),
     (A("이어폰", "Apple", "에어팟", "흰색", "케이스 흠집"), "흠집 있는 흰색 에어팟", "형남공학관", "1층 로비", 3)),
    ("여러 건물 중 하나",
     (A("이어폰", "소니", "WF-1000XM5", "검정"), "소니 무선 이어폰 검정", ["중앙도서관", "신양관"], 20, 16),
     (A("이어폰", "소니", "확인불가", "검정", "타원형 케이스"), "검정 소니 이어폰", "중앙도서관", "4층 열람실", 15)),
    ("습득 쪽 브랜드 확인불가",
     (A("지갑", "닥스", "반지갑", "검정", "가죽", "교통카드 들어 있음"), "검정 가죽 반지갑, 닥스", ["중앙도서관"], 28, 24),
     (A("지갑", "확인불가", "반지갑", "검정", "가죽"), "검정 가죽 반지갑, 안에 카드 있음", "중앙도서관", "2층 노트북 열람실", 23)),
    ("옆 건물 (진리관 / 조만식기념관)",
     (A("지갑", "확인불가", "카드지갑", "갈색", "가죽"), "갈색 카드지갑", ["진리관"], 10, 7),
     (A("지갑", "확인불가", "카드지갑", "갈색"), "갈색 카드지갑", "조만식기념관", "2층 복도", 6)),
    ("브랜드·색 모두 일치",
     (A("지갑", "메종키츠네", "장지갑", "분홍", "여우 로고"), "분홍 메종키츠네 장지갑", ["학생회관"], 5, 3),
     (A("지갑", "메종키츠네", "장지갑", "분홍", "여우 로고"), "분홍 장지갑 여우 로고", "학생회관", "1층 편의점 앞", 2)),
    ("학생증",
     (A("학생증·카드", "숭실대학교", "학생증", "파랑", "투명 카드케이스"), "파란 숭실대 학생증, 투명 케이스", ["형남공학관"], 9, 6),
     (A("학생증·카드", "숭실대학교", "학생증", "파랑", "카드케이스"), "숭실대 학생증 (개인정보 가림)", "형남공학관", "5층 강의실 501호", 5)),
    ("교통카드, 옆 건물 (창의관 / 정보과학관)",
     (A("학생증·카드", "티머니", "교통카드", "노랑", "캐릭터 그림"), "노란 캐릭터 티머니 카드", ["창의관"], 7, 5),
     (A("학생증·카드", "티머니", "교통카드", "노랑", "캐릭터"), "노란 교통카드", "정보과학관", "1층 출입구", 4)),
    ("체크카드",
     (A("학생증·카드", "KB국민", "체크카드", "초록"), "초록색 국민 체크카드", ["웨스트민스터홀"], 12, 10),
     (A("학생증·카드", "KB국민", "체크카드", "초록"), "초록 KB 카드", "웨스트민스터홀", "3층 화장실 앞", 9)),
    ("휴대폰",
     (A("휴대폰", "Apple", "아이폰 15", "파랑", "투명 젤리 케이스"), "파란 아이폰 15, 투명 케이스", ["형남공학관"], 6, 3),
     (A("휴대폰", "Apple", "아이폰 15", "파랑", "투명 케이스"), "파란 아이폰, 잠겨 있음", "형남공학관", "8층 계단", 2)),
    ("휴대폰 2",
     (A("휴대폰", "삼성", "갤럭시 S24", "검정", "검정 케이스"), "검정 갤럭시 S24", ["전산관"], 26, 22),
     (A("휴대폰", "삼성", "갤럭시 S24", "검정", "케이스"), "검정 갤럭시 폰", "전산관", "2층 실습실", 21)),
    ("모델 다르게 기억 + 옆 건물 (중앙도서관 / 미래관)",
     (A("휴대폰", "Apple", "아이폰 13 미니", "흰색"), "흰색 아이폰 13 미니", ["중앙도서관"], 11, 8),
     (A("휴대폰", "Apple", "아이폰 미니", "흰색", "작은 크기"), "작은 흰색 아이폰", "미래관", "1층 라운지", 7)),
    ("기타: 우산",
     (A("기타", "확인불가", "장우산", "남색", "나무 손잡이"), "남색 장우산, 나무 손잡이", ["정보과학관"], 40, 30),
     (A("기타", "확인불가", "장우산", "남색", "나무 손잡이"), "남색 장우산", "정보과학관", "1층 우산꽂이", 29)),
    ("기타: 노트북",
     (A("기타", "Apple", "맥북 에어", "은색", "스티커 여러 개"), "은색 맥북 에어, 스티커 많이 붙어 있음", ["중앙도서관"], 4, 2),
     (A("기타", "Apple", "맥북", "은색", "스티커"), "스티커 붙은 맥북", "중앙도서관", "3층 그룹스터디실", 1)),
    ("기타: 텀블러",
     (A("기타", "스타벅스", "텀블러", "흰색", "로고"), "흰색 스타벅스 텀블러", ["베어드홀"], 9, 7),
     (A("기타", "스타벅스", "텀블러", "흰색"), "스타벅스 텀블러", "베어드홀", "2층 강의실", 6)),
    ("기타: USB",
     (A("기타", "삼성", "USB 메모리", "은색", "64GB"), "삼성 USB 64기가", ["전산관"], 30, 26),
     (A("기타", "삼성", "USB", "은색"), "은색 삼성 USB", "전산관", "1층 실습실 컴퓨터", 25)),
    ("헤드폰 (이어폰 종류로 등록)",
     (A("이어폰", "Apple", "에어팟 맥스", "은색"), "은색 에어팟 맥스 헤드폰", ["학생회관"], 8, 6),
     (A("이어폰", "Apple", "에어팟 맥스", "은색", "헤드폰"), "은색 헤드폰", "학생회관", "3층 동아리방 앞", 5)),
    ("지갑: 비슷한 검정 반지갑이 여럿",
     (A("지갑", "프라다", "반지갑", "검정", "삼각 로고"), "검정 프라다 반지갑", ["형남공학관"], 7, 4),
     (A("지갑", "프라다", "반지갑", "검정", "삼각형 로고"), "검정 프라다 지갑", "형남공학관", "2층 학사지원과 앞", 3)),
    ("기타: 안경",
     (A("기타", "확인불가", "뿔테 안경", "검정"), "검정 뿔테 안경", ["진리관"], 6, 4),
     (A("기타", "확인불가", "안경", "검정", "뿔테"), "검정 안경", "진리관", "4층 강의실", 3)),
]

# 정답이 없는 '헷갈리게 하는' 습득물 (같은 종류·비슷한 색, 같은 시간대)
DISTRACTORS = [
    (A("이어폰", "Apple", "에어팟 프로", "검정", "실리콘 케이스"), "검정 케이스 에어팟 프로", "정보과학관", "1층 로비", 4),
    (A("이어폰", "삼성", "갤럭시 버즈", "흰색"), "흰색 버즈", "형남공학관", "3층", 5),
    (A("지갑", "확인불가", "반지갑", "검정"), "검정 반지갑", "학생회관", "2층", 8),
    (A("지갑", "확인불가", "장지갑", "갈색"), "갈색 장지갑", "중앙도서관", "1층", 6),
    (A("학생증·카드", "숭실대학교", "학생증", "파랑"), "숭실대 학생증", "중앙도서관", "2층", 5),
    (A("휴대폰", "Apple", "아이폰 14", "검정"), "검정 아이폰", "학생회관", "1층", 4),
    (A("기타", "확인불가", "장우산", "검정"), "검정 우산", "형남공학관", "1층", 20),
    (A("기타", "확인불가", "텀블러", "흰색"), "흰색 텀블러", "정보과학관", "2층", 6),
]

created = {"users": [], "found": [], "lost": []}


def make_user(role):
    u = sb.auth.admin.create_user({"email": f"eval-{role}-{tag}@aifound.test", "email_confirm": True})
    created["users"].append(u.user.id)
    return u.user.id


def insert_found(finder, attrs, desc, building, detail, hours_ago):
    row = sb.table("found_items").insert({
        "finder_id": finder, "category": attrs["category"], "attrs": attrs, "description": desc,
        "building": building, "location_detail": detail, "found_at": ago(hours_ago),
    }).execute().data[0]
    created["found"].append(row["id"])
    pipeline.ensure_embedding("found_items", row)
    return row["id"]


def cleanup():
    if KEEP:
        print(f"\n(--keep) 테스트 데이터를 남겼어요. 태그: {tag}")
        return
    if created["found"]:
        sb.table("matches").delete().in_("found_item_id", created["found"]).execute()
        sb.table("found_items").delete().in_("id", created["found"]).execute()
    if created["lost"]:
        sb.table("lost_reports").delete().in_("id", created["lost"]).execute()
    for uid in created["users"]:
        sb.auth.admin.delete_user(uid)
    print("\n🧹 테스트 데이터 삭제 완료")


# Gemini 재비교 실패 횟수 세기
_rerank_orig = rerank.rerank
stats = {"rerank_calls": 0, "rerank_fail": 0}


def _counting_rerank(anchor, cands):
    stats["rerank_calls"] += 1
    for attempt in range(3):
        out = _rerank_orig(anchor, cands)
        if out or not cands:
            return out
        time.sleep(5 * (attempt + 1))      # 무료 한도에 걸렸을 때 잠깐 쉬고 다시
    stats["rerank_fail"] += 1
    return {}


pipeline.rerank_mod.rerank = _counting_rerank


def run():
    print(f"=== 매칭 정확도 측정: 정답 {len(CASES)}쌍 + 헷갈리는 습득물 {len(DISTRACTORS)}개 ===\n")
    owner, finder = make_user("owner"), make_user("finder")

    print("📦 습득물 등록 + 임베딩")
    truth = []
    for _, _, f in CASES:
        truth.append(insert_found(finder, *f))
    for d in DISTRACTORS:
        insert_found(finder, *d)
    eval_found = set(created["found"])

    results = []
    print("🔎 분실 신고별 매칭 (Gemini 재비교 때문에 건당 몇 초)")
    for (name, l, _), true_id in zip(CASES, truth):
        attrs, desc, buildings, frm, to = l
        lost = sb.table("lost_reports").insert({
            "owner_id": owner, "category": attrs["category"], "attrs": attrs, "description": desc,
            "buildings": buildings, "lost_from": ago(frm), "lost_to": ago(to),
        }).execute().data[0]
        created["lost"].append(lost["id"])
        pipeline.ensure_embedding("lost_reports", lost)
        lost = db.get_lost(lost["id"])
        cands = [c for c in db.search_found_for_lost(lost["id"]) if c["id"] in eval_found]

        # 규칙 점수만 (AI 없이)
        rule = sorted(((total_score(c, lost, float(c.get("similarity") or 0)).total, c["id"]) for c in cands),
                      reverse=True)
        rule_ids = [cid for _, cid in rule]
        # 실제 매칭 (AI 재비교 포함)
        ranked = pipeline._rank(lost, cands, anchor_is_found=False)
        ids = [str(i["row"]["id"]) for i in ranked]
        t = next((i for i in ranked if str(i["row"]["id"]) == true_id), None)
        wrong = [i["score"] for i in ranked if str(i["row"]["id"]) != true_id]
        results.append({
            "name": name, "n_cand": len(cands),
            "rank": ids.index(true_id) + 1 if true_id in ids else None,
            "rule_rank": rule_ids.index(true_id) + 1 if true_id in rule_ids else None,
            "true_score": t["score"] if t else None, "true_ai": t["ai"] if t else None,
            "true_reason": t["short"] if t else "",
            "wrong_scores": wrong, "ranked": ranked, "true_id": true_id,
        })
        r = results[-1]
        mark = "✅" if r["rank"] and r["rank"] <= 3 else "❌"
        print(f"  {mark} {name}: 정답 {r['rank'] or '-'}위, 일치율 {r['true_score']}, AI {r['true_ai']} (후보 {len(cands)}개)")
    return results


def report(results):
    n = len(results)
    hit = lambda key, k: sum(1 for r in results if r[key] and r[key] <= k)
    top1, top3 = hit("rank", 1), hit("rank", 3)
    rtop1, rtop3 = hit("rule_rank", 1), hit("rule_rank", 3)
    trues = [r["true_score"] for r in results if r["true_score"] is not None]
    wrongs = [s for r in results for s in r["wrong_scores"]]
    best_wrong = [max(r["wrong_scores"]) for r in results if r["wrong_scores"]]

    lines = [f"# 매칭 정확도 측정 결과 ({NOW:%Y-%m-%d %H:%M})", "",
             f"정답 {n}쌍 + 헷갈리게 하는 습득물 {len(DISTRACTORS)}개, 실제 매칭 코드(임베딩 {config.EMBED_MODEL}, 재비교 {config.GEMINI_MODEL}) 그대로 사용.", "",
             "## Top-k 적중률", "",
             "| 방식 | Top-1 | Top-3 |", "| --- | --- | --- |",
             f"| 규칙 점수만 (AI 없이) | {rtop1}/{n} ({rtop1/n:.0%}) | {rtop3}/{n} ({rtop3/n:.0%}) |",
             f"| 실제 매칭 (AI 재비교 포함) | {top1}/{n} ({top1/n:.0%}) | {top3}/{n} ({top3/n:.0%}) |", "",
             "## 일치율 분포", "",
             "| | 개수 | 최저 | 평균 | 최고 |", "| --- | --- | --- | --- | --- |"]
    if trues:
        lines.append(f"| 정답 후보 | {len(trues)} | {min(trues)} | {statistics.mean(trues):.1f} | {max(trues)} |")
    if wrongs:
        lines.append(f"| 오답 후보 (전체) | {len(wrongs)} | {min(wrongs)} | {statistics.mean(wrongs):.1f} | {max(wrongs)} |")
    if best_wrong:
        lines.append(f"| 신고별 가장 높은 오답 | {len(best_wrong)} | {min(best_wrong)} | {statistics.mean(best_wrong):.1f} | {max(best_wrong)} |")

    lines += ["", "## 알림 기준 점수별 결과", "",
              "알림은 '일치율이 기준 이상이고 AI가 같은 물건 가능성 30 미만으로 보지 않은' 짝에게만 감.",
              "정답 알림 = 정답 짝이 기준을 넘은 비율. 잘못된 알림 = 신고 1건당 기준을 넘은 오답 짝 수 평균.", "",
              "| 기준 점수 | 정답 알림 | 잘못된 알림 / 신고 | 오답 알림이 1개 이상인 신고 |", "| --- | --- | --- | --- |"]
    for thr in (40, 50, 55, 60, 65, 70, 75, 80):
        got = sum(1 for r in results if r["true_score"] is not None and r["true_score"] >= thr)
        wrong_each = [sum(1 for s in r["wrong_scores"] if s >= thr) for r in results]
        star = " ← 현재" if thr == int(config.NOTIFY_THRESHOLD) else ""
        lines.append(f"| {thr}{star} | {got}/{n} ({got/n:.0%}) | {sum(wrong_each)/n:.2f} | {sum(1 for w in wrong_each if w)} |")

    lines += ["", "## 신고별 결과", "",
              "| 상황 | 정답 순위 | 규칙만 순위 | 일치율 | AI 가능성 | 후보 수 | AI 이유 |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in results:
        lines.append(f"| {r['name']} | {r['rank'] or '빠짐'} | {r['rule_rank'] or '빠짐'} | {r['true_score'] if r['true_score'] is not None else '-'} "
                     f"| {r['true_ai'] if r['true_ai'] is not None else '-'} | {r['n_cand']} | {r['true_reason']} |")
    lines += ["", f"Gemini 재비교 {stats['rerank_calls']}번 중 실패 {stats['rerank_fail']}번 (실패하면 규칙 점수 순서 그대로 사용)."]

    text = "\n".join(lines) + "\n"
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"accuracy_{NOW:%Y%m%d_%H%M}.md")
    open(path, "w").write(text)
    print("\n" + text)
    print(f"📄 저장: {os.path.relpath(path)}")


if __name__ == "__main__":
    try:
        report(run())
    finally:
        cleanup()
