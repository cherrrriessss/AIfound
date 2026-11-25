package com.aifound.app.ui;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import com.aifound.app.R;
import com.aifound.app.data.FoundDraft;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.MatchModels;
import com.aifound.app.net.Models;
import com.aifound.app.util.Fmt;
import com.aifound.app.util.TabBar;
import com.aifound.app.util.Ui;
import com.google.android.material.chip.Chip;
import com.google.android.material.chip.ChipGroup;

import java.util.List;

/**
 * S18 분실물 매칭 탭 (이민서). 와이어프레임 S18_MatchList.
 * - 내 진행 중 신고(GET /me/lost?tab=open, 김준희 서버) 를 칩으로
 * - 고른 신고의 후보 GET /lost-reports/{id}/matches (주희선 서버) — 일치율 높은 순
 * - 후보를 누르면 S19 매칭 상세
 */
public class MatchListActivity extends AppCompatActivity {

    private static final String EXTRA_LOST_ID = "lost_id";

    /** 탭바에서 */
    public static void open(Activity from) {
        Intent i = new Intent(from, MatchListActivity.class);
        i.addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
        from.startActivity(i);
    }

    /** S17·S23 에서: 이 신고를 먼저 선택 */
    public static void open(Activity from, String lostId) {
        Intent i = new Intent(from, MatchListActivity.class).putExtra(EXTRA_LOST_ID, lostId);
        i.addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
        from.startActivity(i);
    }

    private ChipGroup reportGroup;
    private LinearLayout candidateList;
    private SwipeRefreshLayout refresh;
    private String selectedId;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_match_list);
        TabBar.setup(this, TabBar.MATCH);

        reportGroup = findViewById(R.id.reportGroup);
        candidateList = findViewById(R.id.candidateList);
        refresh = findViewById(R.id.refresh);
        refresh.setOnRefreshListener(this::loadReports);
        selectedId = getIntent().getStringExtra(EXTRA_LOST_ID);

        findViewById(R.id.btnRegister).setOnClickListener(v -> {
            FoundDraft.reset();
            startActivity(new Intent(this, PhotoActivity.class));
        });
        findViewById(R.id.btnLost).setOnClickListener(v -> LostReportActivity.open(this));
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        String id = intent.getStringExtra(EXTRA_LOST_ID);
        if (id != null) selectedId = id;
    }

    @Override
    protected void onResume() {
        super.onResume();
        loadReports();
    }

    private void loadReports() {
        ApiClient.get(this).myLost("open").enqueue(new ApiCallback<List<Models.LostOut>>(this) {
            @Override public void ok(List<Models.LostOut> reports) { showReports(reports); }

            @Override public void fail(String message) {
                super.fail(message);
                refresh.setRefreshing(false);
            }
        });
    }

    private void showReports(List<Models.LostOut> reports) {
        reportGroup.setOnCheckedStateChangeListener(null);
        reportGroup.removeAllViews();
        findViewById(R.id.tvNoReport).setVisibility(reports.isEmpty() ? View.VISIBLE : View.GONE);
        if (reports.isEmpty()) {
            refresh.setRefreshing(false);
            candidateList.removeAllViews();
            candidateList.addView(Ui.empty(this, "분실 신고를 하면 AI가 등록된 습득물과 비교해\n비슷한 후보를 여기에 보여 드려요."));
            return;
        }
        int sel = 0;                       // 고른 신고, 없으면 첫 번째
        for (int i = 0; i < reports.size(); i++) {
            Models.LostOut l = reports.get(i);
            Ui.choiceChip(this, reportGroup, LostDoneActivity.title(l) + " · " + l.matchCount).setTag(l.id);
            if (l.id.equals(selectedId)) sel = i;
        }
        Chip toCheck = (Chip) reportGroup.getChildAt(sel);
        toCheck.setChecked(true);
        selectedId = (String) toCheck.getTag();
        reportGroup.setOnCheckedStateChangeListener((g, ids) -> {
            if (ids.isEmpty()) return;
            Chip c = g.findViewById(ids.get(0));
            selectedId = (String) c.getTag();
            loadMatches();
        });
        loadMatches();
    }

    private void loadMatches() {
        if (selectedId == null) return;
        refresh.setRefreshing(true);
        ApiClient.match(this).matchesForLost(selectedId).enqueue(new ApiCallback<MatchModels.MatchList>(this) {
            @Override public void ok(MatchModels.MatchList body) {
                refresh.setRefreshing(false);
                showMatches(body.matches);
            }

            @Override public void fail(String message) {
                refresh.setRefreshing(false);
                candidateList.removeAllViews();
                candidateList.addView(Ui.empty(MatchListActivity.this,
                        "매칭 서버(8000)에 연결하지 못했어요.\n" + message));
            }
        });
    }

    private void showMatches(List<MatchModels.MatchItem> items) {
        candidateList.removeAllViews();
        if (items.isEmpty()) {
            candidateList.addView(Ui.empty(this, "아직 비슷한 습득물이 없어요.\n새로 등록되면 바로 알려드릴게요."));
            return;
        }
        LayoutInflater inf = LayoutInflater.from(this);
        for (int i = 0; i < items.size(); i++) {
            MatchModels.MatchItem m = items.get(i);
            View card = inf.inflate(R.layout.item_match, candidateList, false);
            bind(card, m, i == 0);
            candidateList.addView(card);
        }
    }

    static void bind(View card, MatchModels.MatchItem m, boolean top) {
        Activity a = (Activity) card.getContext();
        MatchModels.FoundInfo f = m.foundItem;
        card.setBackgroundResource(top ? R.drawable.bg_card_selected : R.drawable.bg_card);
        Fmt.photo(card.findViewById(R.id.ivPhoto), f != null ? f.photoUrl : null);
        ((TextView) card.findViewById(R.id.tvName)).setText(f != null ? Fmt.itemName(f.attrs) : "습득물");

        TextView score = card.findViewById(R.id.tvScore);
        if ("claimed".equals(m.status)) score.setText("수령 대기");
        else if ("received".equals(m.status)) score.setText("수령 완료");
        else score.setText(m.score + "%");
        score.setTextColor(a.getColor(top ? R.color.accent : R.color.ink));

        String place = f != null ? Fmt.place(f.building, f.locationDetail) : "";
        String when = f != null ? Fmt.dateTimePlain(f.foundAt) : "";
        ((TextView) card.findViewById(R.id.tvSub)).setText(place.isEmpty() ? when : place + " · " + when);
        TextView reason = card.findViewById(R.id.tvReason);
        reason.setText(m.shortReason != null ? "\"" + m.shortReason + "\"" : "");
        reason.setVisibility(m.shortReason != null ? View.VISIBLE : View.GONE);
        card.setOnClickListener(v -> MatchDetailActivity.open(a, m.matchId));
    }
}
