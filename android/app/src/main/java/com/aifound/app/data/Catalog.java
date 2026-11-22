package com.aifound.app.data;

/** 서버 schemas.py 의 CATEGORIES / COLORS 와 반드시 같아야 한다 (매칭 점수 계산에 쓰임). */
public final class Catalog {
    private Catalog() {}

    // 팀 합의: 5개 (12 AI 결과, 16 분실 신고, 매칭 모두 동일)
    public static final String[] CATEGORIES = {"이어폰", "지갑", "학생증·카드", "휴대폰", "기타"};

    public static final String[] COLORS = {
            "검정", "흰색", "회색", "은색", "금색", "빨강", "주황", "노랑",
            "초록", "파랑", "남색", "보라", "분홍", "갈색", "베이지", "투명", "기타"
    };

    public static int indexOf(String[] list, String value) {
        for (int i = 0; i < list.length; i++) if (list[i].equals(value)) return i;
        return list.length - 1;   // 모르면 '기타'
    }
}
