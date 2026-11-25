package com.aifound.app.data;

import android.content.Context;
import android.content.SharedPreferences;

import com.aifound.app.BuildConfig;

/** 로그인 토큰과 서버 주소를 폰에 저장. */
public final class TokenStore {
    private static final String PREFS = "aifound";

    private TokenStore() {}

    private static SharedPreferences prefs(Context c) {
        return c.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static String token(Context c) { return prefs(c).getString("token", null); }

    public static void saveToken(Context c, String token) { prefs(c).edit().putString("token", token).apply(); }

    public static void clearToken(Context c) { prefs(c).edit().remove("token").apply(); }

    public static String email(Context c) { return prefs(c).getString("email", ""); }

    public static void saveEmail(Context c, String email) { prefs(c).edit().putString("email", email).apply(); }

    public static String baseUrl(Context c) { return prefs(c).getString("base_url", BuildConfig.DEFAULT_BASE_URL); }

    /** 주희선 매칭 서버(8000). 김준희 서버 주소에서 포트만 바꾼다 (실제 폰도 '서버 설정' 하나로 둘 다 맞춰짐). */
    public static String matchUrl(Context c) {
        String base = baseUrl(c);
        return base.contains(":8001/") ? base.replace(":8001/", ":8000/") : base;
    }

    /** S04 온보딩을 본 적 있는지 */
    public static boolean onboarded(Context c) { return prefs(c).getBoolean("onboarded", false); }

    public static void setOnboarded(Context c) { prefs(c).edit().putBoolean("onboarded", true).apply(); }

    /** '192.168.0.5:8000' 처럼 입력해도 'http://192.168.0.5:8000/' 으로 맞춘다. */
    public static void saveBaseUrl(Context c, String raw) {
        String u = raw.trim();
        if (u.isEmpty()) u = BuildConfig.DEFAULT_BASE_URL;
        if (!u.startsWith("http://") && !u.startsWith("https://")) u = "http://" + u;
        if (!u.endsWith("/")) u = u + "/";
        prefs(c).edit().putString("base_url", u).apply();
    }
}
