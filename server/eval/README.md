# 정확도 측정

1. `photos/` 에 사진을 넣는다 (20장 정도, 학생증·이름표 등 개인정보 사진 3~5장 포함)
2. `labels_example.csv` 를 `labels.csv` 로 복사해서 사진마다 정답을 적는다
   - category: 이어폰, 지갑, 학생증·카드, 휴대폰, 기타
   - color: 검정, 흰색, 회색, 은색, 금색, 빨강, 주황, 노랑, 초록, 파랑, 남색, 보라, 분홍, 갈색, 베이지, 투명, 기타
   - brand: 모르면 비우기 / has_pii: 개인정보가 보이면 1, 아니면 0
   - 엑셀로 편집했으면 'CSV UTF-8' 형식으로 저장
3. `aifound-backend` 폴더에서 실행 (`.env` 의 MOCK=false)
   ```
   python -m tools.eval_attributes
   ```
4. `result.csv`(사진별), `summary.md`(발표용 표)가 생긴다

사진은 개인정보가 있을 수 있으니 깃허브에 올리지 않는다 (.gitignore 에 등록됨).
