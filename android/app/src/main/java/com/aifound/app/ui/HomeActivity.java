package com.aifound.app.ui;

import android.content.Intent;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.data.FoundDraft;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.MatchModels;
import com.aifound.app.net.Models;
import com.aifound.app.util.Fmt;
import com.aifound.app.util.TabBar;

import java.util.List;

/**
 * S06 홈 메인 (이민서). 와이어프레임 S06_Home.
 * - 습득물 등록(S10) / 분실 신고(S16) 큰 버튼
 * - 새 매칭 후보 배너 (매칭 서버 GET /matches/summary) → S19 / S18
 * - 알림함(S27) 아이콘 + 안 읽은 알림 점
 * - 최근 등록된 습득물 5개 (GET /found?size=5) → 전체보기(S07), 누르면 상세(S08)
 */
public class HomeActivity extends AppCompatActivity {

    private static final int RECENT_COUNT = 5;

    private LinearLayout recentList;
    private TextView tvRecentEmpty;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_home);
        TabBar.setup(this, TabBar.HOME);

        recentList = findViewById(R.id.recentList);
        tvRecentEmpty = findViewById(R.id.tvRecentEmpty);

        findViewById(R.id.cardRegister).setOnClickListener(v -> {
            FoundDraft.reset();
            startActivity(new Intent(this, PhotoActivity.class));
        });
        findViewById(R.id.cardLost).setOnClickListener(v -> LostReportActivity.open(this));
        findViewById(R.id.btnInbox).setOnClickListener(v -> startActivity(new Intent(this, InboxActivity.class)));
        findViewById(R.id.tvSeeAll).setOnClickListener(v ->
                startActivity(new Intent(this, FoundListActivity.class)));
    }

    @Override
    protected void onResume() {
        super.onResume();
        // 프로필(이름)이 없으면 S03 으로 (예전 임시 홈에 있던 확인을 그대로 옮김)
        ApiClient.get(this).me().enqueue(new ApiCallback<Models.Profile>(this) {
            @Override public void ok(Models.Profile body) {
                if (body.name == null || body.name.isEmpty()) {
                    startActivity(new Intent(HomeActivity.this, ProfileActivity.class));
                }
            }
        });
        loadRecent();
        loadMatchBanner();
        loadInboxDot();
    }

    /** S06 배너: 매칭 서버 GET /matches/summary (안 본 후보 수). 서버가 꺼져 있으면 배너만 숨김 */
    private void loadMatchBanner() {
        ApiClient.match(this).summary().enqueue(new ApiCallback<MatchModels.Summary>(this) {
            @Override public void ok(MatchModels.Summary s) {
                String title = s.top != null ? Fmt.itemName(s.top.lostAttrs) : "";
                showMatchBanner(s.newCount, title, s.top);
            }

            @Override public void fail(String message) { showMatchBanner(0, "", null); }
        });
    }

    /** 알림함 아이콘의 파란 점: 안 읽은 알림이 있으면 */
    private void loadInboxDot() {
        ApiClient.match(this).notifications().enqueue(new ApiCallback<MatchModels.NotificationList>(this) {
            @Override public void ok(MatchModels.NotificationList body) {
                findViewById(R.id.inboxDot).setVisibility(
                        InboxActivity.unread(body.notifications) > 0 ? View.VISIBLE : View.GONE);
            }

            @Override public void fail(String message) { findViewById(R.id.inboxDot).setVisibility(View.GONE); }
        });
    }

    private void loadRecent() {
        ApiClient.get(this).listFound(null, null, null, null, null, null, 1, RECENT_COUNT)
                .enqueue(new ApiCallback<Models.FoundListOut>(this) {
                    @Override public void ok(Models.FoundListOut body) { showRecent(body.items); }
                });
    }

    private void showRecent(List<Models.FoundOut> items) {
        recentList.removeAllViews();
        tvRecentEmpty.setVisibility(items.isEmpty() ? View.VISIBLE : View.GONE);
        LayoutInflater inf = LayoutInflater.from(this);
        for (int i = 0; i < items.size(); i++) {
            Models.FoundOut f = items.get(i);
            View row = inf.inflate(R.layout.item_found_row, recentList, false);
            bindRow(row, f, i == items.size() - 1);
            recentList.addView(row);
        }
    }

    /** 한 줄: 사진 · 제목 · '중앙도서관 1층 · 30분 전' · 태그(종류, 브랜드 또는 색) */
    private void bindRow(View row, Models.FoundOut f, boolean last) {
        Fmt.photo(row.findViewById(R.id.ivPhoto), f.photoUrl);
        ((TextView) row.findViewById(R.id.tvTitle)).setText(f.title);
        String place = Fmt.place(f);
        String ago = Fmt.ago(f.foundAt);
        ((TextView) row.findViewById(R.id.tvSub)).setText(place.isEmpty() ? ago : place + " · " + ago);

        LinearLayout tags = row.findViewById(R.id.tags);
        tags.removeAllViews();
        if (f.category != null) tags.addView(Fmt.tag(this, f.category));
        String brand = Fmt.attr(f, "brand");
        String second = brand != null ? brand : Fmt.attr(f, "color");
        if (second != null) tags.addView(Fmt.tag(this, second));

        row.findViewById(R.id.divider).setVisibility(last ? View.GONE : View.VISIBLE);
        row.setOnClickListener(v -> FoundDetailActivity.open(this, f.id));
    }

    /** S18 배너. 1건이면 바로 S19, 여러 건이면 그 신고의 S18 목록 */
    private void showMatchBanner(int count, String reportTitle, MatchModels.SummaryTop top) {
        View banner = findViewById(R.id.matchBanner);
        if (count <= 0 || top == null) {
            banner.setVisibility(View.GONE);
            return;
        }
        ((TextView) findViewById(R.id.tvMatchCount)).setText(String.valueOf(count));
        ((TextView) findViewById(R.id.tvMatchTitle)).setText("새 매칭 후보 " + count + "건");
        ((TextView) findViewById(R.id.tvMatchSub)).setText("'" + reportTitle + "' 신고와 비슷해요");
        banner.setVisibility(View.VISIBLE);
        banner.setOnClickListener(v -> {
            if (count == 1) MatchDetailActivity.open(this, top.matchId);
            else MatchListActivity.open(this, top.lostReportId);
        });
    }
}
