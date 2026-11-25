package com.aifound.app.util;

import android.app.Activity;
import android.content.Context;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.aifound.app.R;
import com.google.android.material.chip.Chip;
import com.google.android.material.chip.ChipGroup;

/** 여러 화면에서 같이 쓰는 작은 화면 조각 (S16~S28). */
public final class Ui {
    private Ui() {}

    /** 선택 칩 (layout/chip_choice.xml) */
    public static Chip choiceChip(Context c, ChipGroup group, String text) {
        Chip chip = (Chip) LayoutInflater.from(c).inflate(R.layout.chip_choice, group, false);
        chip.setText(text);
        group.addView(chip);
        return chip;
    }

    /** 상태 배지. strong=true 면 파란 글자 (후보 있음, 보관 중 등) */
    public static TextView badge(Context c, String text, boolean strong) {
        TextView tv = new TextView(c);
        tv.setText(text);
        tv.setTextSize(12);
        tv.setTextColor(c.getColor(strong ? R.color.accent : R.color.ink_quiet));
        tv.setBackgroundResource(strong ? R.drawable.bg_banner : R.drawable.bg_tag);
        tv.setPadding(Fmt.dp(c, 8), Fmt.dp(c, 3), Fmt.dp(c, 8), Fmt.dp(c, 3));
        tv.setTypeface(null, android.graphics.Typeface.BOLD);
        return tv;
    }

    /** 위/아래 토글 버튼 모양 (S23 진행 중/완료, S25 전체/찾은 것/돌려준 것) */
    public static void toggle(TextView tv, boolean on) {
        tv.setBackgroundResource(on ? R.drawable.bg_filter_on : R.drawable.bg_filter_off);
        tv.setTextColor(tv.getContext().getColor(on ? R.color.white : R.color.ink));
    }

    /** 비어 있을 때 안내 한 줄 */
    public static TextView empty(Context c, String text) {
        TextView tv = new TextView(c);
        tv.setText(text);
        tv.setTextSize(14);
        tv.setTextColor(c.getColor(R.color.ink_quiet));
        tv.setGravity(android.view.Gravity.CENTER);
        tv.setLineSpacing(0, 1.3f);
        int pad = Fmt.dp(c, 32);
        tv.setPadding(pad, pad, pad, pad);
        tv.setLayoutParams(new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
        return tv;
    }

    /** 카드 사이 간격 */
    public static void topMargin(View v, int dp) {
        ViewGroup.LayoutParams lp = v.getLayoutParams();
        LinearLayout.LayoutParams l = lp instanceof LinearLayout.LayoutParams
                ? (LinearLayout.LayoutParams) lp
                : new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        l.topMargin = Fmt.dp(v.getContext(), dp);
        v.setLayoutParams(l);
    }

    public interface OnPick { void pick(int index); }

    /**
     * activity_list_tabs.xml 의 위쪽 토글 버튼들. 누르면 모양을 바꾸고 onPick(index).
     * 돌려준 배열로 나중에 글자('진행 중 2')를 바꿀 수 있다.
     */
    public static TextView[] toggles(Activity a, String[] labels, int selected, OnPick onPick) {
        a.findViewById(R.id.toggleScroll).setVisibility(View.VISIBLE);
        LinearLayout box = a.findViewById(R.id.toggles);
        box.removeAllViews();
        TextView[] out = new TextView[labels.length];
        for (int i = 0; i < labels.length; i++) {
            TextView tv = new TextView(a, null, 0, R.style.AIfound_Toggle);
            tv.setLayoutParams(new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Fmt.dp(a, 40)));
            ((LinearLayout.LayoutParams) tv.getLayoutParams()).setMarginEnd(Fmt.dp(a, 8));
            tv.setText(labels[i]);
            toggle(tv, i == selected);
            final int idx = i;
            tv.setOnClickListener(v -> {
                for (int j = 0; j < out.length; j++) toggle(out[j], j == idx);
                onPick.pick(idx);
            });
            out[i] = tv;
            box.addView(tv);
        }
        return out;
    }

    /** 목록 화면에서 탭바를 숨길 때 (S27 알림함) */
    public static void hideTabBar(Activity a) {
        a.findViewById(R.id.tabbar).setVisibility(View.GONE);
    }

    /** 헤더 제목만 있는 화면 (layout_header, 진행 막대 없음) */
    public static void header(Activity a, String title) {
        Steps.header(a, title, 0);
    }
}
