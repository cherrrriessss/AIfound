package com.aifound.app.net;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** 매칭 서버(8000) 응답 모양. 필드 이름은 camelCase, Gson 이 snake_case 로 바꾼다. */
public final class MatchModels {
    private MatchModels() {}

    public static class DeviceIn {
        public String fcmToken;
        public DeviceIn(String t) { fcmToken = t; }
    }

    /** category / color / brand_model / place_time / other */
    public static class RejectIn {
        public List<String> reasons = new ArrayList<>();
    }

    // ---------------- 06 홈 배너 ----------------
    public static class SummaryTop {
        public String matchId;
        public String lostReportId;
        public Map<String, Object> lostAttrs;
    }

    public static class Summary {
        public int newCount;
        public SummaryTop top;
    }

    // ---------------- 습득물 / 보관함 (매칭 서버가 붙여 주는 모양) ----------------
    public static class LockerInfo {
        public String id;
        public String name;
        public String building;
        public String location;
        public String hours;
    }

    public static class FoundInfo {
        public String id;
        public String finderId;
        public Map<String, Object> attrs;
        public String building;
        public String locationDetail;
        public String foundAt;
        public String photoPath;
        public String photoUrl;
        public String lockerId;
        public LockerInfo lockers;
    }

    public static class ReportInfo {
        public String id;
        public String ownerId;
        public Map<String, Object> attrs;
        public List<String> buildings = new ArrayList<>();
        public String lostFrom;
        public String lostTo;
        public String photoUrl;
    }

    // ---------------- 18 목록 ----------------
    public static class MatchItem {
        public String matchId;
        public int score;
        public String shortReason;
        public String status;           // candidate / claimed / received / closed
        public FoundInfo foundItem;
    }

    public static class MatchList {
        public List<MatchItem> matches = new ArrayList<>();
    }

    // ---------------- 19 상세 ----------------
    public static class Bar {
        public String label;
        public int max;
        public int value;
    }

    public static class MatchDetail {
        public String matchId;
        public int score;
        public String reason;
        public String status;
        public boolean direct;          // 08 에서 직접 수령 요청한 건 (AI 점수 없음)
        public List<Bar> breakdown = new ArrayList<>();
        public ReportInfo myReport;
        public FoundInfo foundItem;
    }

    // ---------------- 20 수령 ----------------
    public static class ClaimOut {
        public String matchId;          // 08 직접 요청일 때 채워짐
        public String status;
        public String pickupDeadline;
        public boolean direct;
    }

    public static class PickupCode {
        public String code;
        public String display;          // '482 913'
        public String qr;               // 'AIFOUND:<match_id>:<code>'
        public int expiresIn;           // 초
    }

    public static class PickupItem {
        public String id;
        public String name;
        public String photoUrl;
    }

    public static class PickupStep {
        public int no;
        public String title;
        public boolean done;
        public LockerInfo locker;
    }

    public static class PickupGuide {
        public PickupItem item;
        public String deadline;
        public List<PickupStep> steps = new ArrayList<>();
        public PickupCode code;
    }

    public static class PickupStatus {
        public boolean received;
    }

    // ---------------- 25 수령 기록 ----------------
    public static class PickupFound {
        public String id;
        public Map<String, Object> attrs;
        public String photoUrl;
    }

    public static class PickupLocker {
        public String name;
    }

    public static class Pickup {
        public String id;
        public String receivedAt;
        public String code;
        public String receiverId;
        public String finderId;
        public PickupFound foundItems;
        public PickupLocker lockers;
    }

    public static class PickupList {
        public List<Pickup> pickups = new ArrayList<>();
    }

    // ---------------- 27 알림함 ----------------
    public static class Notification {
        public String id;
        public String type;             // match / owner_found / received / reminder
        public String title;
        public String body;
        public Map<String, Object> data;
        public boolean read;
        public String createdAt;
    }

    public static class NotificationList {
        public List<Notification> notifications = new ArrayList<>();
    }

    // ---------------- 26 알림 설정 ----------------
    public static class Settings {
        public Boolean matchAlert;
        public Boolean ownerAlert;
        public Boolean pickupReminder;
        public String quietStart;       // "23:00" (서버는 "23:00:00" 으로 줄 수도 있음)
        public String quietEnd;
        public List<String> interestBuildings;
    }
}
