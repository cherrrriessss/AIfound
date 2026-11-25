package com.aifound.app.util;

import android.app.Activity;
import android.content.Intent;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import com.aifound.app.R;
import com.aifound.app.ui.HomeActivity;
import com.aifound.app.ui.MatchListActivity;
import com.aifound.app.ui.MyPageActivity;

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
        a.findViewById(R.id.tabMatch).setOnClickListener(v -> {
            if (a instanceof MatchListActivity) return;
            MatchListActivity.open(a);
        });
        a.findViewById(R.id.tabMy).setOnClickListener(v -> {
            if (a instanceof MyPageActivity) return;
            MyPageActivity.open(a);
        });
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
