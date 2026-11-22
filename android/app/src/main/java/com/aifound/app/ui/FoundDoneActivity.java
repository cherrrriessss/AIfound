package com.aifound.app.ui;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.ImageView;
import android.widget.TextView;

import androidx.activity.OnBackPressedCallback;
import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.data.FoundDraft;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.Models;
import com.aifound.app.util.ImageUtils;

/** S15 등록 완료 */
public class FoundDoneActivity extends AppCompatActivity {

    private static final long POLL_MS = 3000;     // 3초마다
    private static final int MAX_POLLS = 20;      // 최대 1분
    private final Handler handler = new Handler(Looper.getMainLooper());
    private TextView tvProgress;
    private int polls = 0;
    private String foundId;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_found_done);
        FoundDraft d = FoundDraft.get();

        if (d.result != null) {
            ((TextView) findViewById(R.id.tvDoneTitle)).setText(d.result.title);
            String storage = d.result.locker != null ? d.result.locker.name : d.lockerName;
            ((TextView) findViewById(R.id.tvDoneStorage)).setText("보관: " + storage);
        }
        if (d.imageFile != null) {
            ((ImageView) findViewById(R.id.ivDone)).setImageBitmap(ImageUtils.masked(ImageUtils.load(d.imageFile), d.masks));
        }

        tvProgress = findViewById(R.id.tvProgress);
        showProgress(d.result != null ? d.result.matchStatus : "pending");
        if (d.result != null) {
            foundId = d.result.id;
            handler.postDelayed(this::poll, POLL_MS);
        }

        findViewById(R.id.btnHome).setOnClickListener(v -> goHome());
        // 뒤로가기로 등록 화면에 돌아가 중복 등록하지 않도록
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override public void handleOnBackPressed() { goHome(); }
        });
    }

    /** S15 체크리스트: 저장 → 비슷한 신고 찾는 중 → 상위 후보에게 알림 (match_status 는 주희선 서버가 바꿈) */
    private void showProgress(String status) {
        boolean done = "notified".equals(status) || "no_match".equals(status);
        String step2 = done ? "✓ 비슷한 분실 신고 찾기 완료" : "… 비슷한 분실 신고 찾는 중";
        String step3;
        if ("notified".equals(status)) step3 = "✓ 상위 후보에게 알림 보냄";
        else if ("no_match".equals(status)) step3 = "– 아직 비슷한 신고가 없어요. 새 신고가 오면 알려요";
        else step3 = "○ 상위 후보 3명에게 알림";
        tvProgress.setText("✓ 사진·AI 태그 저장\n" + step2 + "\n" + step3);
    }

    private void poll() {
        if (isFinishing() || foundId == null || polls++ >= MAX_POLLS) return;
        ApiClient.get(this).getFound(foundId).enqueue(new ApiCallback<Models.FoundOut>(this) {
            @Override public void ok(Models.FoundOut f) {
                showProgress(f.matchStatus);
                if (!"notified".equals(f.matchStatus) && !"no_match".equals(f.matchStatus)) {
                    handler.postDelayed(FoundDoneActivity.this::poll, POLL_MS);
                }
            }

            @Override public void fail(String message) {
                // 진행 표시는 보조 기능이라 실패해도 조용히 넘어간다
            }
        });
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    private void goHome() {
        FoundDraft.reset();
        Intent i = new Intent(this, HomeActivity.class);
        i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        startActivity(i);
        finish();
    }
}
