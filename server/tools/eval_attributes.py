"""AI 속성 정확도 · 개인정보 경고 정확도 측정 (제안서 '정확도 검증 지표').

준비
  1. eval/photos/ 에 분실물 사진을 넣는다 (예: 20장, 학생증 사진 몇 장 포함)
  2. eval/labels.csv 에 사진마다 정답을 적는다 (eval/labels_example.csv 참고)
       file,category,color,brand,has_pii
       airpods1.jpg,이어폰,흰색,Apple,0
       idcard1.jpg,학생증·카드,흰색,,1        ← brand 를 비우면 '브랜드 없음/모름'이 정답
  3. .env 에 GEMINI_API_KEY, MOCK=false (MOCK=true 면 고정 결과라 측정 의미 없음)

실행 (aifound-backend 폴더에서, 가상환경 켠 상태)
  python -m tools.eval_attributes
  python -m tools.eval_attributes --photos eval/photos --labels eval/labels.csv --out eval/result.csv

결과
  eval/result.csv   사진별 정답·AI 결과·맞음 여부
  eval/summary.md   발표 자료에 붙일 요약 표
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Optional

from app.config import settings
from app.schemas import CATEGORIES, COLORS
from app.services import gemini, images


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower().replace(" ", "")


def brand_ok(expected: str, predicted: Optional[str]) -> bool:
    """정답이 비어 있으면 AI 도 '모름(None)'이어야 맞음. 대소문자·띄어쓰기 무시, 한쪽이 다른 쪽을 포함하면 맞음."""
    e, p = _norm(expected), _norm(predicted)
    if not e:
        return not p
    return bool(p) and (e in p or p in e)


def evaluate(photos: Path, labels: Path) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    with labels.open(encoding="utf-8-sig") as f:
        for lab in csv.DictReader(f):
            file = (lab.get("file") or "").strip()
            if not file:
                continue
            exp_cat = (lab.get("category") or "").strip()
            exp_color = (lab.get("color") or "").strip()
            exp_brand = (lab.get("brand") or "").strip()
            exp_pii = (lab.get("has_pii") or "0").strip() in ("1", "true", "y", "yes", "o")
            for name, val, allowed in (("category", exp_cat, CATEGORIES), ("color", exp_color, COLORS)):
                if val and val not in allowed:
                    print(f"[경고] {file}: 정답 {name} '{val}' 이(가) 목록에 없어요 → 항상 틀림으로 계산돼요")
            row = {"file": file, "exp_category": exp_cat, "exp_color": exp_color, "exp_brand": exp_brand,
                   "exp_pii": int(exp_pii)}
            path = photos / file
            t0 = time.perf_counter()
            try:
                img = images.shrink(images.load_image(path.read_bytes(), settings.max_image_bytes),
                                    settings.image_max_side)
                a = gemini.extract_attributes(images.to_jpeg(img))
                row.update(ai_title=a.title, ai_category=a.category, ai_color=a.color, ai_brand=a.brand or "",
                           ai_pii=int(a.pii_detected), error="")
            except Exception as e:  # 파일 없음, AI 오류 등은 그 사진만 '오류'로 남기고 계속
                row.update(ai_title="", ai_category="", ai_color="", ai_brand="", ai_pii="", error=str(e)[:120])
            row["seconds"] = round(time.perf_counter() - t0, 2)
            ok = not row["error"]
            row["ok_category"] = int(ok and row["ai_category"] == exp_cat)
            row["ok_color"] = int(ok and row["ai_color"] == exp_color)
            row["ok_brand"] = int(ok and brand_ok(exp_brand, row["ai_brand"]))
            row["ok_all3"] = row["ok_category"] & row["ok_color"] & row["ok_brand"]
            row["ok_pii"] = int(ok and row["ai_pii"] == int(exp_pii))
            rows.append(row)
            mark = "오류" if row["error"] else ("O" if row["ok_all3"] else "X")
            print(f"{mark:>2}  {file:<24} 종류 {row['ai_category'] or '-':<6} 색 {row['ai_color'] or '-':<4} "
                  f"브랜드 {row['ai_brand'] or '-':<10} 개인정보 {row['ai_pii']}  ({row['seconds']}초)")
    return rows, summarize(rows)


def summarize(rows: list[dict]) -> dict:
    done = [r for r in rows if not r["error"]]
    n = len(done)
    pct = lambda k, rs=done: round(100 * sum(r[k] for r in rs) / len(rs), 1) if rs else 0.0
    pii_pos = [r for r in done if r["exp_pii"] == 1]
    pii_neg = [r for r in done if r["exp_pii"] == 0]
    return {
        "photos": len(rows), "evaluated": n, "errors": len(rows) - n,
        "category": pct("ok_category"), "color": pct("ok_color"), "brand": pct("ok_brand"),
        "all3": pct("ok_all3"), "pii": pct("ok_pii"),
        # 개인정보 경고: 있는 사진에서 잡아낸 비율(놓치면 위험), 없는 사진에서 조용한 비율(오경보)
        "pii_recall": pct("ok_pii", pii_pos), "pii_pos": len(pii_pos),
        "pii_specificity": pct("ok_pii", pii_neg), "pii_neg": len(pii_neg),
        "avg_seconds": round(sum(r["seconds"] for r in done) / n, 2) if n else 0.0,
        "model": settings.gemini_model, "mock": settings.mock,
    }


def summary_markdown(s: dict) -> str:
    return "\n".join([
        f"# AI 속성 인식 정확도 ({s['model']})",
        "",
        f"사진 {s['photos']}장 중 {s['evaluated']}장 측정 (오류 {s['errors']}장), 평균 {s['avg_seconds']}초/장",
        "",
        "| 지표 | 정확도 |",
        "|---|---|",
        f"| 종류 | {s['category']}% |",
        f"| 색 | {s['color']}% |",
        f"| 브랜드 | {s['brand']}% |",
        f"| 종류·색·브랜드 모두 정답 | {s['all3']}% |",
        f"| 개인정보 경고 (전체) | {s['pii']}% |",
        f"| 개인정보 있는 사진에서 경고함 | {s['pii_recall']}% ({s['pii_pos']}장) |",
        f"| 개인정보 없는 사진에서 경고 안 함 | {s['pii_specificity']}% ({s['pii_neg']}장) |",
        "",
    ])


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="AI 속성·개인정보 경고 정확도 측정")
    ap.add_argument("--photos", default="eval/photos")
    ap.add_argument("--labels", default="eval/labels.csv")
    ap.add_argument("--out", default="eval/result.csv")
    args = ap.parse_args(argv)

    photos, labels, out = Path(args.photos), Path(args.labels), Path(args.out)
    if not labels.exists():
        print(f"정답 파일이 없어요: {labels}  (eval/labels_example.csv 를 복사해서 만들어 주세요)")
        return 1
    if settings.mock:
        print("[주의] MOCK=true 라서 AI 가 항상 같은 결과를 내요. 실제 측정은 .env 에서 MOCK=false 로 바꾸세요.\n")

    rows, s = evaluate(photos, labels)
    if not rows:
        print("정답 파일에 사진이 없어요.")
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:   # utf-8-sig: 엑셀에서 한글 안 깨짐
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    md = summary_markdown(s)
    (out.parent / "summary.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    print(f"사진별 결과: {out}\n요약: {out.parent / 'summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
