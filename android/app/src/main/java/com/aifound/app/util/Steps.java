package com.aifound.app.util;

import android.app.Activity;
import android.widget.ImageButton;
import android.widget.ProgressBar;
import android.widget.TextView;

import com.aifound.app.R;

/** 등록 단계 화면 공통 헤더 (뒤로가기, 제목, '1 / 5', 진행 막대). */
public final class Steps {
    private Steps() {}

    public static void header(Activity a, String title, int step) {
        ((TextView) a.findViewById(R.id.tvHeaderTitle)).setText(title);
        TextView tvStep = a.findViewById(R.id.tvStep);
        ProgressBar bar = a.findViewById(R.id.stepProgress);
        if (step > 0) {
            tvStep.setText(step + " / 5");
            bar.setMax(5);
            bar.setProgress(step);
        } else {
            tvStep.setText("");
            bar.setVisibility(android.view.View.GONE);
        }
        ImageButton back = a.findViewById(R.id.btnBack);
        back.setOnClickListener(v -> a.finish());
    }
}
