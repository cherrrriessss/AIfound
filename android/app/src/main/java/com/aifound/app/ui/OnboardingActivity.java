package com.aifound.app.ui;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.data.TokenStore;
import com.aifound.app.util.Fmt;
import com.google.android.material.button.MaterialButton;

/**
 * S04 온보딩 (이민서). 와이어프레임 S04_Onboarding. 처음 가입(S03 프로필 저장) 직후 한 번만.
 * 1 사진 한 장이면 AI가 먼저 알려줘요 · 2 분실 신고 한 번이면 자동 알림 · 3 보관함 안내 + 학교 메일 본인 확인
 */
public class OnboardingActivity extends AppCompatActivity {

    private static final String[] TITLES = {
            "사진 한 장이면\nAI가 먼저 알려줘요",
            "분실 신고 한 번이면\n매칭되면 자동 알림",
            "보관함 안내와\n학교 메일 본인 확인",
    };
    private static final String[] BODIES = {
            "습득물 사진을 올리면 AI가 종류·브랜드·색을 인식해\n비슷한 분실 신고를 한 사람에게 알림을 보내요.",
            "잃어버린 물건을 한 번만 신고해 두면\n비슷한 습득물이 등록될 때 이유와 함께 알려드려요.",
            "어느 보관함에 있는지 바로 보여주고\n학교 메일 인증 + 수령 코드로 안전하게 찾아가요.",
    };
    private static final int[] ICONS = {R.drawable.ic_camera, R.drawable.ic_bell, R.drawable.ic_pin};

    private int page;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_onboarding);
        findViewById(R.id.btnSkip).setOnClickListener(v -> finishOnboarding());
        findViewById(R.id.btnNext).setOnClickListener(v -> {
            if (page < TITLES.length - 1) {
                page++;
                show();
            } else {
                finishOnboarding();
            }
        });
        show();
    }

    @Override
    public void onBackPressed() {
        if (page > 0) {
            page--;
            show();
        } else {
            super.onBackPressed();
        }
    }

    private void show() {
        ((TextView) findViewById(R.id.tvTitle)).setText(TITLES[page]);
        ((TextView) findViewById(R.id.tvBody)).setText(BODIES[page]);
        ((ImageView) findViewById(R.id.ivArt)).setImageResource(ICONS[page]);
        ((MaterialButton) findViewById(R.id.btnNext)).setText(page == TITLES.length - 1 ? "시작하기" : "다음");
        findViewById(R.id.btnSkip).setVisibility(page == TITLES.length - 1 ? View.INVISIBLE : View.VISIBLE);

        LinearLayout dots = findViewById(R.id.dots);
        dots.removeAllViews();
        for (int i = 0; i < TITLES.length; i++) {
            View d = new View(this);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    Fmt.dp(this, i == page ? 20 : 8), Fmt.dp(this, 8));
            lp.setMarginEnd(Fmt.dp(this, 8));
            d.setLayoutParams(lp);
            d.setBackgroundResource(i == page ? R.drawable.bg_filter_on : R.drawable.bg_tag);
            dots.addView(d);
        }
        dots.setContentDescription(TITLES.length + "장 중 " + (page + 1) + "번째");
    }

    private void finishOnboarding() {
        TokenStore.setOnboarded(this);
        Intent i = new Intent(this, HomeActivity.class);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(i);
    }
}
