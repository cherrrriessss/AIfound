package com.aifound.app.ui;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.FrameLayout;
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
import com.aifound.app.util.TabBar;
import com.aifound.app.util.Ui;

/**
 * S25 수령 기록 (이민서). 와이어프레임 S25_History.
 * 매칭 서버 GET /pickups?kind=all|mine|given → 월별로 묶어서 카드. '찾음'(내가 받은 것) / '돌려줌'(내가 주운 것).
 */
public class HistoryActivity extends AppCompatActivity {

    private static final String[] KINDS = {"all", "mine", "given"};

    private LinearLayout list;
    private SwipeRefreshLayout refresh;
    private String myId;
    private int kind;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_list_tabs);
        Ui.header(this, "수령 기록");
        TabBar.setup(this, TabBar.MY);
        list = findViewById(R.id.list);
        refresh = findViewById(R.id.refresh);
        refresh.setOnRefreshListener(this::load);
        Ui.toggles(this, new String[]{"전체", "내가 찾은 것", "내가 돌려준 것"}, 0, i -> {
            kind = i;
            load();
        });
        // '찾음/돌려줌'을 가르려면 내 id 가 필요하다
        ApiClient.get(this).me().enqueue(new ApiCallback<Models.Profile>(this) {
            @Override public void ok(Models.Profile p) {
                myId = p.id;
                load();
            }
        });
    }

    private void load() {
        if (myId == null) return;
        refresh.setRefreshing(true);
        ApiClient.match(this).pickups(KINDS[kind]).enqueue(new ApiCallback<MatchModels.PickupList>(this) {
            @Override public void ok(MatchModels.PickupList body) {
                refresh.setRefreshing(false);
                show(body);
            }

            @Override public void fail(String message) {
                super.fail(message);
                refresh.setRefreshing(false);
            }
        });
    }

    private void show(MatchModels.PickupList body) {
        list.removeAllViews();
        if (body.pickups.isEmpty()) {
            list.addView(Ui.empty(this, "아직 수령 기록이 없어요"));
            return;
        }
        LayoutInflater inf = LayoutInflater.from(this);
        String lastMonth = null;
        for (MatchModels.Pickup p : body.pickups) {
            String month = Fmt.month(p.receivedAt);
            if (!month.equals(lastMonth)) {
                TextView h = new TextView(this, null, 0, R.style.AIfound_Section);
                h.setText(month);
                list.addView(h);
                Ui.topMargin(h, 16);
                lastMonth = month;
            }
            View card = inf.inflate(R.layout.item_pickup, list, false);
            boolean mine = myId.equals(p.receiverId);
            ((TextView) card.findViewById(R.id.tvName)).setText(
                    p.foundItems != null ? Fmt.itemName(p.foundItems.attrs) : "물건");
            ((FrameLayout) card.findViewById(R.id.badgeBox)).addView(Ui.badge(this, mine ? "찾음" : "돌려줌", mine));
            LinearLayout table = card.findViewById(R.id.infoTable);
            addRow(table, "수령일", Fmt.dateTimePlain(p.receivedAt));
            addRow(table, "수령처", p.lockers != null ? p.lockers.name : null);
            if (mine) addRow(table, "확인", "학교 메일 인증" + (p.code != null ? " · 코드 " + p.code : ""));
            if (p.foundItems != null) card.setOnClickListener(v -> FoundDetailActivity.open(this, p.foundItems.id));
            list.addView(card);
        }
    }

    private void addRow(LinearLayout table, String key, String value) {
        if (value == null || value.isEmpty()) return;
        View row = LayoutInflater.from(this).inflate(R.layout.item_info_row, table, false);
        ((TextView) row.findViewById(R.id.tvKey)).setText(key);
        ((TextView) row.findViewById(R.id.tvValue)).setText(value);
        table.addView(row);
    }
}
