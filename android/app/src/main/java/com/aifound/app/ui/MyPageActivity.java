package com.aifound.app.ui;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.MatchModels;
import com.aifound.app.net.Models;
import com.aifound.app.util.TabBar;

/**
 * S22 마이페이지 (이민서). 와이어프레임 S22_MyPage.
 * 프로필(GET /me), 숫자 3개(GET /me/summary), 알림함 안 읽은 수(매칭 서버 GET /notifications).
 * 예전 임시 마이페이지의 로그아웃·탈퇴는 S28 설정으로 옮겼다.
 */
public class MyPageActivity extends AppCompatActivity {

    public static void open(Activity from) {
        Intent i = new Intent(from, MyPageActivity.class);
        i.addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
        from.startActivity(i);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_my_page);
        TabBar.setup(this, TabBar.MY);

        findViewById(R.id.btnSettings).setOnClickListener(v -> go(SettingsActivity.class));
        findViewById(R.id.statLost).setOnClickListener(v -> go(MyLostActivity.class));
        findViewById(R.id.statFound).setOnClickListener(v -> go(MyFoundActivity.class));
        findViewById(R.id.statReceived).setOnClickListener(v -> go(HistoryActivity.class));
        findViewById(R.id.menuMyLost).setOnClickListener(v -> go(MyLostActivity.class));
        findViewById(R.id.menuMyFound).setOnClickListener(v -> go(MyFoundActivity.class));
        findViewById(R.id.menuHistory).setOnClickListener(v -> go(HistoryActivity.class));
        findViewById(R.id.menuInbox).setOnClickListener(v -> go(InboxActivity.class));
        findViewById(R.id.menuNotiSetting).setOnClickListener(v -> go(NotiSettingActivity.class));
        findViewById(R.id.menuSettings).setOnClickListener(v -> go(SettingsActivity.class));
    }

    private void go(Class<?> screen) {
        startActivity(new Intent(this, screen));
    }

    @Override
    protected void onResume() {
        super.onResume();
        ApiClient.get(this).me().enqueue(new ApiCallback<Models.Profile>(this) {
            @Override public void ok(Models.Profile p) {
                String name = p.name != null ? p.name : "이름 없음";
                ((TextView) findViewById(R.id.tvName)).setText(
                        p.department != null ? name + "  ·  " + p.department : name);
                ((TextView) findViewById(R.id.tvEmail)).setText("학교 메일 인증 · " + p.email);
            }
        });
        ApiClient.get(this).summary().enqueue(new ApiCallback<Models.Summary>(this) {
            @Override public void ok(Models.Summary s) {
                ((TextView) findViewById(R.id.tvLostCount)).setText(String.valueOf(s.lostCount));
                ((TextView) findViewById(R.id.tvFoundCount)).setText(String.valueOf(s.foundCount));
                ((TextView) findViewById(R.id.tvReceivedCount)).setText(String.valueOf(s.receivedCount));
            }
        });
        // 알림함 배지: 매칭 서버가 꺼져 있어도 조용히 넘어간다
        ApiClient.match(this).notifications().enqueue(new ApiCallback<MatchModels.NotificationList>(this) {
            @Override public void ok(MatchModels.NotificationList body) {
                int unread = InboxActivity.unread(body.notifications);
                TextView badge = findViewById(R.id.tvUnread);
                badge.setText(String.valueOf(unread));
                badge.setVisibility(unread > 0 ? View.VISIBLE : View.GONE);
            }

            @Override public void fail(String message) { /* 배지만 안 보임 */ }
        });
    }
}
