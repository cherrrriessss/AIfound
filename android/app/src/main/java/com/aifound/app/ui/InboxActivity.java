package com.aifound.app.ui;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import com.aifound.app.R;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.MatchModels;
import com.aifound.app.net.Models;
import com.aifound.app.util.Fmt;
import com.aifound.app.util.Push;
import com.aifound.app.util.Ui;

import java.util.List;
import java.util.Map;

/**
 * S27 알림함 (이민서). 와이어프레임 S27_Inbox.
 * 매칭 서버 GET /notifications, '모두 읽음' POST /notifications/read-all.
 * 누르면: match → S19, owner_found → S24, received → S25, reminder → S20.
 */
public class InboxActivity extends AppCompatActivity {

    private LinearLayout list;
    private SwipeRefreshLayout refresh;

    public static int unread(List<MatchModels.Notification> items) {
        int n = 0;
        for (MatchModels.Notification x : items) if (!x.read) n++;
        return n;
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_list_tabs);
        Ui.header(this, "알림함");
        Ui.hideTabBar(this);
        list = findViewById(R.id.list);
        refresh = findViewById(R.id.refresh);
        refresh.setOnRefreshListener(this::load);

        TextView readAll = findViewById(R.id.tvStep);     // 헤더 오른쪽 자리
        readAll.setText("모두 읽음");
        readAll.setTextColor(getColor(R.color.ink));
        readAll.setMinHeight(Fmt.dp(this, 44));
        readAll.setGravity(android.view.Gravity.CENTER);
        readAll.setBackgroundResource(android.R.drawable.list_selector_background);
        readAll.setOnClickListener(v -> ApiClient.match(this).readAll().enqueue(new ApiCallback<Models.Ok>(this) {
            @Override public void ok(Models.Ok body) { load(); }
        }));
    }

    @Override
    protected void onResume() {
        super.onResume();
        load();
    }

    private void load() {
        refresh.setRefreshing(true);
        ApiClient.match(this).notifications().enqueue(new ApiCallback<MatchModels.NotificationList>(this) {
            @Override public void ok(MatchModels.NotificationList body) {
                refresh.setRefreshing(false);
                show(body.notifications);
            }

            @Override public void fail(String message) {
                super.fail(message);
                refresh.setRefreshing(false);
            }
        });
    }

    private void show(List<MatchModels.Notification> items) {
        list.removeAllViews();
        if (items.isEmpty()) {
            list.addView(Ui.empty(this, "아직 알림이 없어요.\n매칭 후보가 생기거나 물건 소식이 있으면 여기에 쌓여요."));
            return;
        }
        LayoutInflater inf = LayoutInflater.from(this);
        for (int i = 0; i < items.size(); i++) {
            MatchModels.Notification n = items.get(i);
            View row = inf.inflate(R.layout.item_notification, list, false);
            row.findViewById(R.id.dot).setVisibility(n.read ? View.INVISIBLE : View.VISIBLE);
            ((TextView) row.findViewById(R.id.tvTitle)).setText(n.title);
            ((TextView) row.findViewById(R.id.tvBody)).setText(n.body);
            ((TextView) row.findViewById(R.id.tvTime)).setText(Fmt.ago(n.createdAt));
            row.findViewById(R.id.divider).setVisibility(i == items.size() - 1 ? View.GONE : View.VISIBLE);
            row.setOnClickListener(v -> openTarget(n));
            list.addView(row);
        }
    }

    private void openTarget(MatchModels.Notification n) {
        Push.open(this, n.type, str(n.data, "match_id"));   // S05 푸시를 눌렀을 때와 같은 규칙
    }

    private static String str(Map<String, Object> data, String key) {
        if (data == null || data.get(key) == null) return null;
        return String.valueOf(data.get(key));
    }
}
