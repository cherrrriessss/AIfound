package com.aifound.app.util;

import android.content.Context;
import android.widget.ImageView;

import com.aifound.app.R;
import com.aifound.app.data.TokenStore;
import com.aifound.app.net.Models;
import com.bumptech.glide.Glide;

import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.Locale;
import java.util.Map;

/** 화면에 보여 줄 글자 만들기 (시간, 장소, 사진 주소). 여러 화면에서 같이 쓴다. */
public final class Fmt {
    private Fmt() {}

    private static final ZoneId KST = ZoneId.of("Asia/Seoul");

    /** 서버 시간 문자열(ISO) → 한국 시간. 실패하면 null. */
    public static ZonedDateTime parse(String iso) {
        if (iso == null) return null;
        try {
            return OffsetDateTime.parse(iso).atZoneSameInstant(KST);
        } catch (DateTimeParseException e) {
            try {   // 시간대 없는 값은 UTC 로 본다
                return LocalDateTime.parse(iso).atOffset(ZoneOffset.UTC).atZoneSameInstant(KST);
            } catch (DateTimeParseException ignored) {
                return null;
            }
        }
    }

    /** '방금 전', '30분 전', '2시간 전', '어제', '3일 전', '10/29' */
    public static String ago(String iso) {
        ZonedDateTime t = parse(iso);
        if (t == null) return "";
        ZonedDateTime now = ZonedDateTime.now(KST);
        long min = Duration.between(t, now).toMinutes();
        if (min < 1) return "방금 전";
        if (min < 60) return min + "분 전";
        if (min < 60 * 24 && t.toLocalDate().equals(now.toLocalDate())) return (min / 60) + "시간 전";
        LocalDate d = t.toLocalDate();
        if (d.equals(now.toLocalDate().minusDays(1))) return "어제";
        long days = Duration.between(d.atStartOfDay(), now.toLocalDate().atStartOfDay()).toDays();
        if (days < 7) return days + "일 전";
        return t.format(DateTimeFormatter.ofPattern("M/d", Locale.KOREAN));
    }

    /** '10/29 (목) 14:00경' (S08 습득 일시) */
    public static String dateTime(String iso) {
        ZonedDateTime t = parse(iso);
        if (t == null) return "";
        return t.format(DateTimeFormatter.ofPattern("M/d (E) HH:mm", Locale.KOREAN)) + "경";
    }

    /**
     * 지금부터 n일 전 0시 (S07 날짜 필터) → 서버로 보낼 ISO 문자열.
     * '+09:00' 의 '+' 가 쿼리에서 공백으로 바뀌는 문제를 피하려고 UTC('...Z')로 보낸다.
     */
    public static String daysAgoIso(int days) {
        return ZonedDateTime.now(KST).toLocalDate().minusDays(days).atStartOfDay(KST)
                .toInstant().toString();
    }

    /** '중앙도서관 1층' */
    public static String place(Models.FoundOut f) {
        StringBuilder sb = new StringBuilder();
        if (f.building != null) sb.append(f.building);
        if (f.locationDetail != null && !f.locationDetail.isEmpty()) {
            if (sb.length() > 0) sb.append(' ');
            sb.append(f.locationDetail);
        }
        return sb.toString();
    }

    /** attrs 안의 글자 값 하나 (brand, color, model ...). 없으면 null */
    public static String attr(Models.FoundOut f, String key) {
        Map<String, Object> a = f.attrs;
        if (a == null) return null;
        Object v = a.get(key);
        if (v == null) return null;
        String s = String.valueOf(v).trim();
        return s.isEmpty() || "null".equals(s) ? null : s;
    }

    /**
     * 사진 표시. Supabase 는 전체 주소(서명 URL), MOCK 서버는 '/mock-photos/...' 처럼
     * 앞부분이 없으므로 서버 주소를 붙인다.
     */
    public static void photo(ImageView iv, String url) {
        if (url == null || url.isEmpty()) {
            iv.setImageDrawable(null);
            return;
        }
        Glide.with(iv).load(absoluteUrl(iv.getContext(), url)).centerCrop().into(iv);
    }

    public static String absoluteUrl(Context c, String url) {
        if (url.startsWith("http://") || url.startsWith("https://")) return url;
        String base = TokenStore.baseUrl(c);
        if (base.endsWith("/")) base = base.substring(0, base.length() - 1);
        return base + (url.startsWith("/") ? url : "/" + url);
    }

    public static int dp(Context c, float v) {
        return Math.round(v * c.getResources().getDisplayMetrics().density);
    }

    /** 작은 회색 태그 (S06 목록의 '지갑', '검정') */
    public static android.widget.TextView tag(Context c, String text) {
        android.widget.TextView tv = new android.widget.TextView(c);
        tv.setText(text);
        tv.setTextSize(11);
        tv.setTextColor(c.getColor(R.color.ink));
        tv.setBackgroundResource(R.drawable.bg_tag);
        tv.setPadding(dp(c, 8), dp(c, 2), dp(c, 8), dp(c, 2));
        android.widget.LinearLayout.LayoutParams lp = new android.widget.LinearLayout.LayoutParams(
                android.view.ViewGroup.LayoutParams.WRAP_CONTENT, android.view.ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMarginEnd(dp(c, 4));
        tv.setLayoutParams(lp);
        return tv;
    }
}
