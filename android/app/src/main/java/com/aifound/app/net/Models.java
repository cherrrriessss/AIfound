package com.aifound.app.net;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 서버 JSON 과 1:1 로 대응하는 클래스들.
 * 필드 이름은 camelCase 로 쓰고, Gson 이 snake_case(서버) 로 자동 변환한다. (ApiClient.gson 참고)
 */
public final class Models {
    private Models() {}

    // ---------------- 로그인 ----------------
    public static class RequestCodeIn {
        public String email;
        public RequestCodeIn(String email) { this.email = email; }
    }

    public static class RequestCodeOut {
        public String email;
        public int expiresIn;
        public int resendAfter;
    }

    public static class VerifyIn {
        public String email;
        public String code;
        public VerifyIn(String email, String code) { this.email = email; this.code = code; }
    }

    public static class TokenOut {
        public String accessToken;
        public String refreshToken;
        public int expiresIn;
        public boolean isNewUser;
        public Profile user;
    }

    public static class Profile {
        public String id;
        public String email;
        public String name;
        public String department;
    }

    public static class ProfileUpdate {
        public String name;
        public String department;
        public ProfileUpdate(String name, String department) { this.name = name; this.department = department; }
    }

    // ---------------- 보관함 (lockers 표) ----------------
    public static class Locker {
        public String id;            // uuid
        public String name;
        public String code;
        public String building;
        public String location;
        public String hours;
        public boolean sameBuilding;
    }

    // ---------------- AI 속성 (서버 schemas.ItemAttributes) ----------------
    public static class Confidence {
        public double category;
        public double brand;
        public double color;
    }

    public static class PiiRegion {
        public String type;
        public List<Integer> box;      // [ymin, xmin, ymax, xmax], 0~1000
    }

    public static class ItemAttributes {
        public boolean isItem = true;
        public String title;
        public String category;
        public String subcategory;
        public String brand;
        public String model;
        public String color;                 // 주 색 하나 (매칭 서버와 같은 키)
        public List<String> features = new ArrayList<>();
        public Confidence confidence;
        public boolean piiDetected;
        public List<PiiRegion> piiRegions = new ArrayList<>();
    }

    public static class AnalyzeOut {
        public ItemAttributes attributes;
        public String piiWarning;
        public int imageWidth;
        public int imageHeight;
    }

    // ---------------- 습득물 등록 ----------------
    public static class MaskBox {
        public List<Integer> box;
        public MaskBox(List<Integer> box) { this.box = box; }
    }

    public static class FoundCreateIn {
        public ItemAttributes attributes;
        public String building;
        public String locationDetail;
        public String foundAt;          // 예: 2026-11-11T14:00:00+09:00
        public String description;
        public String lockerId;
        public List<MaskBox> maskBoxes = new ArrayList<>();
    }

    public static class FoundOut {
        public String id;
        public String photoUrl;
        public String category;
        public Map<String, Object> attrs;
        public String title;
        public String description;
        public String building;
        public String locationDetail;
        public String foundAt;
        public Locker locker;
        public String status;           // stored / returned
        public String matchStatus;      // pending / searching / notified / no_match
        public String createdAt;
        public String displayStatus;    // stored / owner_confirmed / returned
        public String displayLabel;     // 보관 중 / 주인 확인됨 / 수령 완료
    }

    // ---------------- 분실 신고 (S16, S17, S23) ----------------
    /** POST /lost, PATCH /lost/{id} 공통. 브랜드·모델·특징은 비워도 된다. */
    public static class LostIn {
        public String category;
        public String brand;
        public String model;
        public String color;
        public List<String> features = new ArrayList<>();
        public String description;
        public List<String> buildings = new ArrayList<>();
        public String lostFrom;      // ISO
        public String lostTo;
    }

    /** 신고 직후 매칭 서버가 돌려준 비슷한 습득물 (S17) */
    public static class LostMatch {
        public String matchId;
        public String foundItemId;
        public String name;
        public int score;
        public String reason;
    }

    public static class LostMatchResult {
        public int count;
        public List<LostMatch> matches = new ArrayList<>();
    }

    public static class LostOut {
        public String id;
        public String category;
        public Map<String, Object> attrs;
        public String description;
        public List<String> buildings = new ArrayList<>();
        public String lostFrom;
        public String lostTo;
        public String photoUrl;
        public String status;           // open / closed
        public String createdAt;
        public String stage;            // waiting / candidates / claimed / received / closed
        public String stageLabel;       // 매칭 대기 / 후보 있음 / 수령 대기 / 수령 완료 / 신고 종료
        public int matchCount;
        public LostMatchResult match;   // POST /lost 응답에만 (매칭 서버가 꺼져 있으면 null)
    }

    // ---------------- 마이페이지 숫자 (S22) ----------------
    public static class Summary {
        public int lostCount;
        public int lostOpenCount;
        public int foundCount;
        public int returnedCount;
        public int receivedCount;
    }

    // ---------------- 찾아보기 목록 (S07) ----------------
    public static class FoundListOut {
        public List<FoundOut> items = new ArrayList<>();
        public int total;
        public int page;
        public int size;
    }

    public static class Ok {
        public boolean ok;
    }
}
