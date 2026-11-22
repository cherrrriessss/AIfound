package com.aifound.app.util;

import android.app.Activity;
import android.content.Intent;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import com.aifound.app.R;
import com.aifound.app.ui.HomeActivity;
import com.aifound.app.ui.TempMyPageActivity;

/** 하단 탭바 (layout_tabbar.xml). 홈 / 분실물 매칭 / 마이페이지 */
public final class TabBar {
    private TabBar() {}

    public static final int HOME = 0, MATCH = 1, MY = 2;

    public static void setup(Activity a, int selected) {
        paint(a, R.id.tabHomeIcon, R.id.tabHomeText, selected == HOME);
        paint(a, R.id.tabMatchIcon, R.id.tabMatchText, selected == MATCH);
        paint(a, R.id.tabMyIcon, R.id.tabMyText, selected == MY);

        a.findViewById(R.id.tabHome).setOnClickListener(v -> {
            if (a instanceof HomeActivity) return;
            Intent i = new Intent(a, HomeActivity.class);
            i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            a.startActivity(i);
        });
        // TODO(S18): 주희선 서버(8000) 매칭 목록 API 를 받으면 MatchListActivity 로 연결
        a.findViewById(R.id.tabMatch).setOnClickListener(v ->
                soon(a, "분실물 매칭 화면은 매칭 서버 연결 후 추가돼요"));
        // TODO(S22): 마이페이지를 만들면 TempMyPageActivity 대신 연결
        a.findViewById(R.id.tabMy).setOnClickListener(v ->
                a.startActivity(new Intent(a, TempMyPageActivity.class)));
    }

    private static void paint(Activity a, int iconId, int textId, boolean on) {
        int color = a.getColor(on ? R.color.ink : R.color.tab_off);
        ((ImageView) a.findViewById(iconId)).setColorFilter(color);
        TextView tv = a.findViewById(textId);
        tv.setTextColor(color);
        tv.setTypeface(null, on ? android.graphics.Typeface.BOLD : android.graphics.Typeface.NORMAL);
    }

    /** 아직 없는 화면을 눌렀을 때 */
    public static void soon(Activity a, String msg) {
        Toast.makeText(a, msg, Toast.LENGTH_SHORT).show();
    }
}
